"""The HMC scenario against the working tree's model/ (resolved with weaver)."""

from __future__ import annotations

import importlib.util
import time
from collections import defaultdict

import pytest

from semconv_mainframe import SCENARIOS_DIR
from semconv_mainframe.emitter import Emitter, Registry

_spec = importlib.util.spec_from_file_location("hmc_scenario", SCENARIOS_DIR / "hmc" / "scenario.py")
assert _spec is not None and _spec.loader is not None
hmc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hmc)


@pytest.fixture(scope="module")
def registry() -> Registry:
    return Registry.from_model()


@pytest.fixture(scope="module")
def emitter(registry: Registry) -> Emitter:
    return hmc.build_emitter(registry)


def test_every_metric_refinement_in_the_model_emits(registry: Registry, emitter: Emitter) -> None:
    # P12: the system.* and hw.* refinements of upstream metrics -- whichever
    # upstream file format defines them -- must reach the wire.
    refinements = {m.id for m in registry.metrics.values() if m.is_refinement}
    assert any(r.startswith("refinement.virtualization.hw.") for r in refinements)
    assert sorted(refinements - emitter.emitted_metric_ids()) == []


def test_every_metric_in_the_model_emits(registry: Registry, emitter: Emitter) -> None:
    assert hmc.unemitted(registry, emitter) == []
    assert set(registry.metrics) == emitter.emitted_metric_ids()


def test_every_planned_series_is_a_data_point(emitter: Emitter) -> None:
    request = emitter.request(time.time_ns(), 60.0)
    points = sum(
        len(m.gauge.data_points) + len(m.sum.data_points)
        for r in request.resource_metrics
        for s in r.scope_metrics
        for m in s.metrics
    )
    assert points == sum(len(series) for _, _, series in emitter.plan)


def test_values_are_in_the_declared_units(registry: Registry, emitter: Emitter) -> None:
    # P13: byte quantities are declared in By, and the workload must emit bytes.
    assert {m.unit for m in registry.metrics.values()}.isdisjoint({"KiBy", "MiBy", "GiBy", "TiBy"})
    values: dict[str, list[float]] = defaultdict(list)
    for metric in emitter.request(time.time_ns(), 60.0).resource_metrics:
        for m in metric.scope_metrics[0].metrics:
            for p in (*m.gauge.data_points, *m.sum.data_points):
                values[f"{m.name} {m.unit}"].append(p.as_int if p.WhichOneof("value") == "as_int" else p.as_double)
    for key, samples in values.items():
        name, unit = key.split(" ")
        if unit == "1" and name.endswith("utilization"):
            assert all(0.0 <= v <= 1.0 for v in samples), key
        if unit == "By" and name.endswith((".size", ".capacity", ".total", ".allocated", ".available")):
            assert all(v >= 2**20 for v in samples), key  # bytes, not GiB or MiB
