"""The workload profile: which values each metric takes, and on which series.

A profile is an ordered list of rules; the first rule matching a metric
definition decides its values::

    - metric: '^mainframe\\.host\\.heatload$'   # regex on the definition's id or name
      unit: J/h                                # required: the unit the values are in
      generator: {function: diurnal, base: 2.6e7, amplitude: 7.0e6, min: 1.9e7}
      attributes: {mainframe.host.heatload.type: [total, water]}   # one series per value

``unit`` makes a rule state the unit its numbers are in. A rule whose
``metric`` pattern selects a definition declared in another unit is an error,
not a silent mismatch -- the bytes-for-GiBy bug of review finding P13. Rules
may also select by ``instrument`` and ``entity``; a metric no rule matches is
an error too, so a profile covers its topology completely.

Data point attributes come from the rule (lists expand into one series per
value), else from the resource when the metric declares one of its
attributes, else -- only when the attribute is required -- from the first
enum member or example in the registry. Recommended attributes nobody
supplies are left out, so coverage reports stay honest.
"""

from __future__ import annotations

import itertools
import math
import random
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from semconv_mainframe.emitter.registry import AttributeValue, MetricDef
from semconv_mainframe.emitter.topology import Node


class WorkloadError(ValueError):
    """A profile that does not fit the registry or the topology."""


class Generator:
    """One series' values over time; stateful, so every series gets its own."""

    def __init__(self, params: Mapping[str, Any], rng: random.Random) -> None:
        self.params = params
        self.rng = rng
        self.low = float(params.get("min", -math.inf))
        self.high = float(params.get("max", math.inf))

    def value(self, t: float, dt: float) -> float:
        return min(self.high, max(self.low, self.raw(t, dt)))

    def raw(self, t: float, dt: float) -> float:
        raise NotImplementedError


class Constant(Generator):
    def raw(self, t: float, dt: float) -> float:
        return float(self.params["value"])


class Gaussian(Generator):
    def raw(self, t: float, dt: float) -> float:
        return self.rng.gauss(float(self.params["mean"]), float(self.params.get("stddev", 0.0)))


class Diurnal(Generator):
    """A daily sine around ``base``, with gaussian noise."""

    def raw(self, t: float, dt: float) -> float:
        p = self.params
        angle = 2 * math.pi * (t - float(p.get("phase", 0.0))) / float(p.get("period", 86400.0))
        return (
            float(p["base"])
            + float(p.get("amplitude", 0.0)) * math.sin(angle)
            + self.rng.gauss(0, float(p.get("noise", 0.0)))
        )


class Spikes(Generator):
    """A small baseline with rare exponential spikes (latencies, error rates)."""

    def raw(self, t: float, dt: float) -> float:
        p = self.params
        baseline = float(p["baseline"])
        if self.rng.random() < float(p.get("probability", 0.01)):
            return baseline + self.rng.expovariate(1.0 / float(p["magnitude"]))
        return baseline


class Counter(Generator):
    """A cumulative total growing by a non-negative ``rate`` per second."""

    def __init__(self, params: Mapping[str, Any], rng: random.Random) -> None:
        super().__init__(params, rng)
        self.rate = make_generator(params["rate"], rng)
        self.total = float(params.get("start", 0.0))

    def raw(self, t: float, dt: float) -> float:
        self.total += max(0.0, self.rate.value(t, dt)) * dt
        return self.total


GENERATORS: dict[str, type[Generator]] = {
    "constant": Constant,
    "gaussian": Gaussian,
    "diurnal": Diurnal,
    "spikes": Spikes,
    "counter": Counter,
}


def make_generator(params: Mapping[str, Any], rng: random.Random) -> Generator:
    function = params.get("function")
    if function not in GENERATORS:
        raise WorkloadError(f"unknown generator function {function!r}; use one of {sorted(GENERATORS)}")
    return GENERATORS[function](params, rng)


@dataclass(frozen=True)
class Rule:
    index: int
    unit: str
    generator: Mapping[str, Any]
    metric: re.Pattern[str] | None = None
    instrument: str | None = None
    entity: str | None = None
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def selects(self, metric: MetricDef, entity_type: str) -> bool:
        if self.metric is not None and not (self.metric.search(metric.id) or self.metric.search(metric.name)):
            return False
        if self.instrument not in (None, metric.instrument) or self.entity not in (None, entity_type):
            return False
        if self.unit != metric.unit:
            if self.metric is not None:
                raise WorkloadError(
                    f"rule {self.index} produces values in {self.unit!r}, but {metric.id} is declared in {metric.unit!r}"
                )
            return False
        return True


@dataclass
class Series:
    metric: MetricDef
    attributes: dict[str, AttributeValue]
    generator: Generator


class Workload:
    def __init__(self, rules: Sequence[Mapping[str, Any]], *, seed: int = 0) -> None:
        self.rng = random.Random(seed)
        self.rules = []
        for index, rule in enumerate(rules):
            if "unit" not in rule or "generator" not in rule:
                raise WorkloadError(f"rule {index}: unit and generator are required")
            make_generator(rule["generator"], self.rng)  # fail on a bad generator up front
            self.rules.append(
                Rule(
                    index=index,
                    unit=str(rule["unit"]),
                    generator=rule["generator"],
                    metric=re.compile(rule["metric"]) if "metric" in rule else None,
                    instrument=rule.get("instrument"),
                    entity=rule.get("entity"),
                    attributes=rule.get("attributes") or {},
                )
            )

    @classmethod
    def load(cls, path: Path, *, seed: int = 0) -> Workload:
        return cls(yaml.safe_load(path.read_text(encoding="utf-8")) or [], seed=seed)

    def rule_for(self, metric: MetricDef, entity_type: str) -> Rule:
        for rule in self.rules:
            if rule.selects(metric, entity_type):
                return rule
        raise WorkloadError(f"no rule matches {metric.id} ({metric.instrument}, {metric.unit}) on {entity_type}")

    def series(self, metric: MetricDef, node: Node) -> list[Series]:
        """Every series ``metric`` has on ``node``, each with a generator of its own."""
        rule = self.rule_for(metric, node.entity_type)
        if metric.instrument == "counter" and rule.generator["function"] != "counter":
            raise WorkloadError(f"rule {rule.index}: counter {metric.id} needs a counter generator to stay monotonic")
        choices: dict[str, list[AttributeValue]] = {}
        for key, declared in metric.attributes.items():
            if key in rule.attributes:
                values = rule.attributes[key]
                choices[key] = values if isinstance(values, list) and declared.type != "string[]" else [values]
            elif key in node.attributes:
                choices[key] = [node.attributes[key]]
            elif declared.requirement_level == "required":
                fallback = declared.members or declared.examples
                if not fallback:
                    raise WorkloadError(f"{metric.id}: nothing supplies the required attribute {key}")
                choices[key] = [fallback[0]]
            for value in choices.get(key, []):
                if not declared.accepts(value):
                    raise WorkloadError(f"rule {rule.index}: {value!r} is not a valid {declared.type} for {key}")
        keys = sorted(choices)
        return [
            Series(metric, dict(zip(keys, values, strict=True)), make_generator(rule.generator, self.rng))
            for values in itertools.product(*(choices[k] for k in keys))
        ]
