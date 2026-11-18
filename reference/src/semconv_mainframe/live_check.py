"""``conformance.yaml``, and what a Weaver live-check run observed, reduced to ``data.json``.

The keys read here, and the ``data.json`` shape written, follow the shared
conformance runner (open-telemetry/semantic-conventions-conformance) so that
a scenario directory can move to it unchanged once it has a mainframe domain:
``spans``, ``events``, ``metrics``, ``entities`` and ``findings``, each signal
listing which of its declared attributes the run carried.

Two things differ, both because this registry is built from refinements:

- A metric refinement is recorded under its own id. A data point is
  attributed to the refinement whose entity association matches its
  resource, so ``system.network.io`` on a PCHID adapter port and on a z/VM
  guest count as two signals.
- An entity is recognised per resource, by all of its identifying attributes
  being on that one resource.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

RUNNER = "mainframe-conformance"
_PACKAGE_KEYS = {"runner", "instrumented_library", "instrumentation_library", "env", "scenarios", "expected_violations"}
_SCENARIO_KEYS = {"run", "env", "metrics", "events", "expected_violations"}


class SpecError(RuntimeError):
    """A ``conformance.yaml`` this runner cannot run."""


@dataclass(frozen=True)
class ExpectedViolation:
    id: str
    reason: str
    # None accepts every finding with this id; a mapping must match in full.
    context: dict[str, Any] | None = None

    def matches(self, finding: Finding) -> bool:
        return self.id == finding.id and (self.context is None or self.context == finding.context_dict)


@dataclass(frozen=True)
class ScenarioSpec:
    name: str
    run: str
    env: dict[str, str] = field(default_factory=dict)
    # None: not checked. A list is checked exactly, nothing missing, nothing extra.
    metrics: tuple[str, ...] | None = None
    events: tuple[str, ...] | None = None
    expected_violations: tuple[ExpectedViolation, ...] = ()


@dataclass(frozen=True)
class PackageSpec:
    directory: Path
    instrumented_library: str
    instrumentation_library: str
    scenarios: dict[str, ScenarioSpec]
    env: dict[str, str] = field(default_factory=dict)
    expected_violations: tuple[ExpectedViolation, ...] = ()


def _expected(entries: object, where: str) -> tuple[ExpectedViolation, ...]:
    if not isinstance(entries, list) or not all(isinstance(e, dict) and "id" in e and "reason" in e for e in entries):
        raise SpecError(f"{where}: expected_violations must be a list of {{id, reason[, context]}}")
    return tuple(ExpectedViolation(e["id"], e["reason"], e.get("context")) for e in entries)


def _unknown(keys: object, allowed: set[str], where: str) -> None:
    extra = sorted(set(keys) - allowed) if isinstance(keys, dict) else []
    if extra:
        raise SpecError(f"{where}: unsupported keys {extra}; this runner supports {sorted(allowed)}")


def load_spec(directory: Path) -> PackageSpec:
    path = directory / "conformance.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    _unknown(raw, _PACKAGE_KEYS, str(path))
    if raw.get("runner", RUNNER) != RUNNER:
        raise SpecError(f"{path}: runner must be {RUNNER!r}")
    scenarios: dict[str, ScenarioSpec] = {}
    for name, body in (raw.get("scenarios") or {}).items():
        where = f"{path}: scenarios.{name}"
        _unknown(body, _SCENARIO_KEYS, where)
        if not isinstance(body, dict) or not isinstance(body.get("run"), str):
            raise SpecError(f"{where}: a scenario needs a run command")
        scenarios[name] = ScenarioSpec(
            name=name,
            run=body["run"],
            env={k: str(v) for k, v in (body.get("env") or {}).items()},
            metrics=tuple(body["metrics"]) if "metrics" in body else None,
            events=tuple(body["events"]) if "events" in body else None,
            expected_violations=_expected(body.get("expected_violations", []), where),
        )
    if not scenarios:
        raise SpecError(f"{path}: declares no scenarios")
    return PackageSpec(
        directory=directory,
        instrumented_library=raw.get("instrumented_library", directory.name),
        instrumentation_library=raw.get("instrumentation_library", "reference"),
        scenarios=scenarios,
        env={k: str(v) for k, v in (raw.get("env") or {}).items()},
        expected_violations=_expected(raw.get("expected_violations", []), str(path)),
    )


# ── Coverage model ──────────────────────────────────────────────────


def _level(requirement_level: object) -> str:
    # A conditional level is written {conditionally_required: "when ..."}.
    if isinstance(requirement_level, dict):
        return str(next(iter(requirement_level)))
    return str(requirement_level or "recommended")


def _attributes(signal: Mapping[str, Any], key: str = "attributes") -> dict[str, str]:
    return {a["key"]: _level(a.get("requirement_level")) for a in signal.get(key) or []}


def coverage_model(resolved: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """What a ``weaver registry resolve --v2`` of ``model/`` declares, per signal.

    Metrics are keyed by id, so a refinement keeps its own entry beside its base.
    Entities are keyed by type, merging every refinement of that type; identity
    attributes always count as required.
    """
    refinements = resolved.get("refinements", {})
    entities: dict[str, dict[str, dict[str, str]]] = {}
    for entity in refinements.get("entities", []):
        merged = entities.setdefault(entity["type"], {"identity": {}, "description": {}})
        merged["identity"].update(dict.fromkeys(_attributes(entity, "identity"), "required"))
        merged["description"].update(_attributes(entity, "description"))
    for merged in entities.values():
        for key in merged["identity"]:
            merged["description"].pop(key, None)
    return {
        "spans": {s["id"]: {"kind": s.get("kind"), "attributes": _attributes(s)} for s in refinements.get("spans", [])},
        "events": {
            e["name"]: {"attributes": _attributes(e)} for e in refinements.get("events", []) if e["id"] == e["name"]
        },
        "metrics": {
            m["id"]: {
                "name": m["name"],
                "entity_associations": sorted(m.get("entity_associations") or []),
                "attributes": _attributes(m),
            }
            for m in refinements.get("metrics", [])
        },
        "entities": entities,
    }


# ── Reading weaver reports ──────────────────────────────────────────


@dataclass(frozen=True, order=True)
class Finding:
    id: str
    message: str
    signal_type: str = ""
    signal_name: str = ""
    context: str = "{}"  # canonical JSON, so findings hash and sort

    @property
    def context_dict(self) -> dict[str, Any]:
        return json.loads(self.context)

    def as_dict(self) -> dict[str, Any]:
        found: dict[str, Any] = {"id": self.id, "message": self.message}
        if self.signal_type:
            found["signal_type"] = self.signal_type
        if self.signal_name:
            found["signal_name"] = self.signal_name
        if self.context != "{}":
            found["context"] = self.context_dict
        return found


@dataclass
class Observed:
    metric_names: set[str] = field(default_factory=set)
    event_names: set[str] = field(default_factory=set)
    metrics: dict[str, set[str]] = field(default_factory=dict)
    entities: dict[str, dict[str, set[str]]] = field(default_factory=dict)
    findings: set[Finding] = field(default_factory=set)


def _advice(node: object) -> Iterator[dict[str, Any]]:
    """Every piece of advice anywhere under a report sample."""
    if isinstance(node, dict):
        yield from (node.get("live_check_result") or {}).get("all_advice") or []
        for key, value in node.items():
            if key != "live_check_result":
                yield from _advice(value)
    elif isinstance(node, list):
        for item in node:
            yield from _advice(item)


def _names(attributes: list[dict[str, Any]] | None) -> set[str]:
    return {a["name"] for a in attributes or [] if "name" in a}


def classify_metric(name: str, resource: set[str], point: set[str], model: Mapping[str, Any]) -> str | None:
    """The coverage-model metric a data point belongs to, or None if model/ declares none.

    Among the definitions sharing the wire name, the one associated with the
    most specific entity whose identity is on the resource wins, then the one
    declaring most of the data point's attributes, then the base definition.
    """
    entities = model["entities"]

    def score(metric_id: str) -> tuple[int, int, bool]:
        metric = model["metrics"][metric_id]
        identities = [set(entities.get(t, {}).get("identity", {})) for t in metric["entity_associations"]]
        entity = max((len(i) for i in identities if i and i <= resource), default=0)
        return entity, len(point & set(metric["attributes"])), metric_id == name

    candidates = sorted(m for m, metric in model["metrics"].items() if metric["name"] == name)
    return max(candidates, key=score) if candidates else None


def observe(report: Mapping[str, Any], model: Mapping[str, Any], observed: Observed | None = None) -> Observed:
    """Fold one live-check report into ``observed``.

    Weaver lists each resource before the metrics exported under it, which is
    how a data point is paired with its resource.
    """
    observed = observed or Observed()
    resource: set[str] = set()
    for sample in report.get("samples", []):
        if "resource" in sample:
            resource = _names(sample["resource"].get("attributes"))
            for entity_type, entity in model["entities"].items():
                identity = set(entity["identity"])
                if identity and identity <= resource:
                    seen = observed.entities.setdefault(entity_type, {"identity": set(), "description": set()})
                    seen["identity"] |= identity
                    seen["description"] |= resource & set(entity["description"])
        elif "metric" in sample:
            metric = sample["metric"]
            observed.metric_names.add(metric["name"])
            for point in metric.get("data_points") or [{}]:
                keys = _names(point.get("attributes"))
                metric_id = classify_metric(metric["name"], resource, keys, model)
                if metric_id is not None:
                    declared = set(model["metrics"][metric_id]["attributes"])
                    observed.metrics.setdefault(metric_id, set()).update(keys & declared)
        elif "log" in sample and sample["log"].get("event_name"):
            observed.event_names.add(sample["log"]["event_name"])
    for advice in _advice(report.get("samples", [])):
        # Improvement and information advice say what could be better, not
        # what an implementation got wrong.
        if advice.get("level") == "violation":
            observed.findings.add(
                Finding(
                    id=str(advice.get("id")),
                    message=str(advice.get("message", "")),
                    signal_type=str(advice.get("signal_type") or ""),
                    signal_name=str(advice.get("signal_name") or ""),
                    context=json.dumps(advice.get("context") or {}, sort_keys=True),
                )
            )
    return observed


def reduce(observed: Observed, model: Mapping[str, Any]) -> dict[str, Any]:
    """The committed ``data.json``: every key present, every list sorted."""
    return {
        "spans": {},
        "events": {name: [] for name in sorted(observed.event_names) if name in model["events"]},
        "metrics": {metric_id: sorted(attrs) for metric_id, attrs in sorted(observed.metrics.items())},
        "entities": {
            entity_type: {"identity": sorted(seen["identity"]), "description": sorted(seen["description"])}
            for entity_type, seen in sorted(observed.entities.items())
        },
        "findings": [finding.as_dict() for finding in sorted(observed.findings)],
    }


def check(scenario: ScenarioSpec, spec: PackageSpec, observed: Observed) -> tuple[list[str], list[str]]:
    """(failures, violations) of one scenario run against what it declares."""
    failures: list[str] = []
    for kind, declared, seen in (
        ("metric", scenario.metrics, observed.metric_names),
        ("event", scenario.events, observed.event_names),
    ):
        if declared is None:
            continue
        failures += [f"declared {kind} {name} was not emitted" for name in sorted(set(declared) - seen)]
        failures += [f"undeclared {kind} {name} was emitted" for name in sorted(seen - set(declared))]
    violations: list[str] = []
    expected = (*scenario.expected_violations, *spec.expected_violations)
    for finding in sorted(observed.findings):
        if not any(e.matches(finding) for e in expected):
            violations.append(f"{finding.id}: {finding.message}")
    for declared_violation in scenario.expected_violations:
        if not any(declared_violation.matches(f) for f in observed.findings):
            failures.append(
                f"expected violation {declared_violation.id} was not reported ({declared_violation.reason})"
            )
    return failures, violations
