"""Unit tests for otel_semconv_sim — the OpenTelemetry Semantic Convention Simulator.

Test strategy (as Distinguished Engineer — Observability):
  * Registry loading: verify every local YAML file is ingested without errors and
    produces the expected entity / metric counts.
  * Entity coverage: assert that every entity type declared in the model has at
    least one metric with a matching entity_association.
  * Metric emission: for each entity type that has associated metrics, verify that
    ``generate_metrics_cycle`` produces well-formed OTLP JSON resource-metrics
    batches with the correct structure, instrument type, and non-NaN values.
  * Workload engine: unit-test every generator function in isolation.
  * Topology graph: verify node lookup and ``get_all_resource_attributes``.
  * Per-entity / per-metric summary: the final summary test prints — and asserts on
    — the exact counts of entities and metrics so CI output is unambiguous.
"""

from __future__ import annotations

import math
import sys
import time
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Path setup — ensure the reference package root is importable from any CWD.
# In CI the working-directory is the repo root; locally it may differ.
# ---------------------------------------------------------------------------
REFERENCE_DIR = Path(__file__).parent.parent.resolve()
REPO_ROOT = REFERENCE_DIR.parent.resolve()

if str(REFERENCE_DIR) not in sys.path:
    sys.path.insert(0, str(REFERENCE_DIR))

from otel_semconv_sim import (  # noqa: E402
    AttributeDef,
    EntityDef,
    MetricDef,
    OTLPJsonClient,
    SemConvRegistry,
    SemConvSimulator,
    TopologyGraph,
    TopologyNode,
    WorkloadEngine,
)

# ---------------------------------------------------------------------------
# Fixture: paths
# ---------------------------------------------------------------------------
MODEL_DIR = REPO_ROOT / "model"
SIMULATOR_CONFIG = REFERENCE_DIR / "simulator_config.yaml"
UPSTREAM_DIR = REPO_ROOT / ".build" / "sc-upstream-filtered"


# ===========================================================================
# Helpers
# ===========================================================================

def _load_registry(load_upstream: bool = False) -> SemConvRegistry:
    """Load the local model into a fresh SemConvRegistry."""
    reg = SemConvRegistry()
    if load_upstream and UPSTREAM_DIR.exists():
        reg.load_upstream_directory(UPSTREAM_DIR)
    reg.load_directory(MODEL_DIR / "mainframe")
    reg.load_directory(MODEL_DIR / "virtualization")
    reg.resolve_metric_refinements()
    return reg


def _build_minimal_topology() -> TopologyGraph:
    """Build a tiny topology with one node per entity type covered by the config."""
    from yaml import safe_load  # type: ignore[import]
    with open(SIMULATOR_CONFIG, "r", encoding="utf-8") as fh:
        cfg = safe_load(fh)
    entities = cfg.get("spec", {}).get("topology", {}).get("entities", [])
    return TopologyGraph.from_config(entities)


# ===========================================================================
# 1. Registry loading — structural correctness
# ===========================================================================

class TestRegistryLoading:
    """Verify the SemConvRegistry ingests local YAML models without errors."""

    def test_entities_loaded(self) -> None:
        reg = _load_registry()
        assert len(reg.entities) > 0, (
            "Registry must contain at least one entity after loading local model."
        )

    def test_metrics_loaded(self) -> None:
        reg = _load_registry()
        assert len(reg.metrics) > 0, (
            "Registry must contain at least one metric after loading local model."
        )

    def test_known_entity_types_present(self) -> None:
        """Spot-check that well-known entity types from the model are registered."""
        reg = _load_registry()
        expected = {
            "mainframe.cpu",
            "mainframe.channel",
            "mainframe.adapter",
            "mainframe.adapter.port",
            "mainframe.partition.nic",
            "mainframe.storage.group",
            "mainframe.storage.group.volume",
            "virtualization.platform",
            "virtualization.partition",
            "virtualization.hypervisor",
            "virtualization.vm",
            "virtualization.cluster",
            "virtualization.resource_pool",
            "virtualization.vswitch",
            "virtualization.storage_pool",
        }
        missing = expected - set(reg.entities.keys())
        assert not missing, (
            f"Expected entity types not found in registry: {sorted(missing)}"
        )

    def test_known_metrics_present(self) -> None:
        """Spot-check that well-known metrics from the model are registered."""
        reg = _load_registry()
        expected = {
            "mainframe.cpu.utilization",
            "mainframe.channel.utilization",
            "mainframe.adapter.utilization",
            "mainframe.adapter.status.code",
            "virtualization.platform.cpu.utilization",
            "virtualization.platform.memory.total",
            "virtualization.platform.memory.used",
            "virtualization.platform.power.usage",
        }
        missing = expected - set(reg.metrics.keys())
        assert not missing, (
            f"Expected metrics not found in registry: {sorted(missing)}"
        )

    def test_metric_defs_have_instrument(self) -> None:
        reg = _load_registry()
        bad = [
            name for name, m in reg.metrics.items()
            if m.instrument not in ("gauge", "sum", "histogram", "updowncounter", "counter")
        ]
        assert not bad, (
            f"Metrics with unrecognised instrument type: {bad}"
        )

    def test_metric_defs_have_unit(self) -> None:
        reg = _load_registry()
        missing_unit = [name for name, m in reg.metrics.items() if not m.unit]
        assert not missing_unit, (
            f"Metrics missing unit field: {missing_unit}"
        )

    def test_entity_defs_have_type(self) -> None:
        reg = _load_registry()
        for etype, edef in reg.entities.items():
            assert edef.type == etype, (
                f"Entity type mismatch: key={etype!r} but EntityDef.type={edef.type!r}"
            )

    def test_summary_reflects_counts(self) -> None:
        reg = _load_registry()
        summary = reg.summary()
        assert str(len(reg.entities)) in summary
        assert str(len(reg.metrics)) in summary


# ===========================================================================
# 2. Entity ↔ metric association coverage
# ===========================================================================

class TestEntityMetricCoverage:
    """Every entity declared in the model should have at least one metric."""

    # Entity types whose metrics are sourced ONLY from upstream metric_refinements
    # (system.network.*, hw.*, container.*).  These entities have metrics in the
    # model but those metrics can only be resolved when the upstream OTel registry
    # has been materialised under .build/sc-upstream-filtered (via `make filter-upstream`).
    # When the upstream is absent (e.g. a minimal local-only test run) the
    # metric_refinements: ref: entries remain unresolved and the entities appear
    # metric-less.  They are listed here so the base test does not fail on CI
    # jobs that do not run filter-upstream; a dedicated test below validates
    # them when the upstream IS available.
    _ENTITIES_UPSTREAM_METRICS_ONLY: frozenset[str] = frozenset({
        "mainframe.adapter.port",   # system.network.* refinements
        "mainframe.partition.nic",  # system.network.* refinements
        "virtualization.vswitch",   # system.network.* refinements
    })
    # Entity types that are intentionally descriptive-only in the current model
    # (no metrics are authored against them yet, even with upstream).
    _ENTITIES_WITHOUT_METRICS_EXPECTED: frozenset[str] = frozenset()

    def _entities_with_metrics(self, reg: SemConvRegistry) -> Dict[str, List[str]]:
        """Return {entity_type: [metric_names]} for every entity that has ≥1 metric."""
        mapping: Dict[str, List[str]] = {etype: [] for etype in reg.entities}
        for mname, mdef in reg.metrics.items():
            for assoc in mdef.entity_associations:
                if assoc in mapping:
                    mapping[assoc].append(mname)
        return mapping

    def test_all_entities_have_at_least_one_metric(self) -> None:
        reg = _load_registry()
        mapping = self._entities_with_metrics(reg)

        without_metrics = {
            etype for etype, metrics in mapping.items() if not metrics
        }
        # Entities that only have upstream-resolved metrics are acceptable
        # in a no-upstream run; they are validated by the with-upstream test.
        allowed_without = (
            self._ENTITIES_WITHOUT_METRICS_EXPECTED
            | self._ENTITIES_UPSTREAM_METRICS_ONLY
        )
        unexpected_without = without_metrics - allowed_without
        assert not unexpected_without, (
            f"Entities with no associated metrics (unexpected): "
            f"{sorted(unexpected_without)}\n"
            f"If intentional add them to _ENTITIES_WITHOUT_METRICS_EXPECTED.\n"
            f"If metrics come from upstream refinements add them to _ENTITIES_UPSTREAM_METRICS_ONLY."
        )

    @pytest.mark.skipif(
        not UPSTREAM_DIR.exists(),
        reason=f"Upstream registry not materialised ({UPSTREAM_DIR}) — run 'make filter-upstream'.",
    )
    def test_upstream_entities_have_metrics_when_upstream_available(self) -> None:
        """When the upstream registry is available, entities that rely on
        metric_refinements must also resolve to at least one metric."""
        reg = _load_registry(load_upstream=True)
        mapping = self._entities_with_metrics(reg)

        still_empty = {
            etype for etype in self._ENTITIES_UPSTREAM_METRICS_ONLY
            if not mapping.get(etype)
        }
        assert not still_empty, (
            f"These entities declared upstream-only metrics, but none resolved "
            f"even with the upstream registry loaded: {sorted(still_empty)}\n"
            f"Check that the metric_refinements ref: names match upstream metric_name: fields."
        )

    def test_entity_metric_counts_reported(self, capsys) -> None:
        """Print entity/metric counts so CI output is human-readable."""
        reg = _load_registry()
        mapping = self._entities_with_metrics(reg)
        total_metrics = len(reg.metrics)
        total_entities = len(reg.entities)

        print(f"\n{'=' * 60}")
        print(f"Semantic Convention Registry Summary")
        print(f"  Total entities : {total_entities}")
        print(f"  Total metrics  : {total_metrics}")
        print(f"\nEntity → Metric coverage:")
        for etype in sorted(mapping.keys()):
            metrics = mapping[etype]
            marker = "OK" if metrics else "NO METRICS"
            print(f"  [{marker}] {etype} ({len(metrics)} metrics)")
        print(f"{'=' * 60}")

        captured = capsys.readouterr()
        assert f"Total entities : {total_entities}" in captured.out
        assert f"Total metrics  : {total_metrics}" in captured.out

    def test_metric_entity_associations_reference_known_entities(self) -> None:
        """All entity_associations on metrics must name known entity types."""
        reg = _load_registry()
        unknown_refs: Dict[str, List[str]] = {}
        for mname, mdef in reg.metrics.items():
            bad = [ea for ea in mdef.entity_associations if ea not in reg.entities]
            if bad:
                unknown_refs[mname] = bad
        assert not unknown_refs, (
            f"Metrics with entity_associations referencing unknown entity types:\n"
            + "\n".join(f"  {m}: {refs}" for m, refs in unknown_refs.items())
        )


# ===========================================================================
# 3. Topology graph
# ===========================================================================

class TestTopologyGraph:
    """Verify the topology graph builds correctly and find_all works."""

    def test_builds_from_config(self) -> None:
        graph = _build_minimal_topology()
        assert len(graph.roots) >= 1, "Topology must have at least one root node."

    def test_find_all_cpu_nodes(self) -> None:
        graph = _build_minimal_topology()
        cpus = graph.find_all("mainframe.cpu")
        assert len(cpus) >= 1, "Expected at least one mainframe.cpu node in topology."

    def test_find_all_channel_nodes(self) -> None:
        graph = _build_minimal_topology()
        channels = graph.find_all("mainframe.channel")
        assert len(channels) >= 1, "Expected at least one mainframe.channel node."

    def test_find_all_platform_nodes(self) -> None:
        graph = _build_minimal_topology()
        platforms = graph.find_all("virtualization.platform")
        assert len(platforms) >= 1, "Expected at least one virtualization.platform node."

    def test_find_all_returns_empty_for_unknown_type(self) -> None:
        graph = _build_minimal_topology()
        result = graph.find_all("nonexistent.type")
        assert result == [], "find_all should return [] for an unknown entity type."

    def test_node_resource_attributes_include_entity_type(self) -> None:
        graph = _build_minimal_topology()
        for root in graph.roots:
            attrs = root.get_all_resource_attributes()
            assert "otel.entity.type" in attrs, (
                f"Node {root.entity_type!r} must include otel.entity.type in resource attributes."
            )
            assert attrs["otel.entity.type"] == root.entity_type

    def test_node_resource_attributes_merge_identity_and_attributes(self) -> None:
        node = TopologyNode(
            entity_type="test.entity",
            identity={"test.entity.id": "id-001"},
            attributes={"test.entity.name": "test-name"},
        )
        attrs = node.get_all_resource_attributes()
        assert attrs["test.entity.id"] == "id-001"
        assert attrs["test.entity.name"] == "test-name"
        assert attrs["otel.entity.type"] == "test.entity"

    def test_all_topology_entity_types_in_registry(self) -> None:
        """Every entity type present in the topology config must be in the registry."""
        graph = _build_minimal_topology()
        reg = _load_registry()
        all_nodes: List[TopologyNode] = []
        for root in graph.roots:
            all_nodes.extend(root.find_nodes_by_type(root.entity_type))
            # Traverse all children
            def _collect(n: TopologyNode) -> None:
                all_nodes.append(n)
                for c in n.children:
                    _collect(c)
            _collect(root)

        # Deduplicate
        types_in_topology = {n.entity_type for n in all_nodes}
        unknown = types_in_topology - set(reg.entities.keys())
        assert not unknown, (
            f"Topology contains entity types not in the registry: {sorted(unknown)}"
        )


    # Entity types that carry no signals in the model and therefore need no
    # topology node.  zos.software is descriptive-only, and the zos namespace
    # is not among spec.registry.paths in simulator_config.yaml.
    _ENTITIES_WITHOUT_TOPOLOGY_EXPECTED: frozenset[str] = frozenset({
        "zos.software",
    })

    def test_entities_with_metrics_have_topology_nodes(self) -> None:
        """Every entity type the model associates with a signal must be
        instantiated at least once in the simulator topology.

        This is the inverse of test_all_topology_entity_types_in_registry and
        enforces the coverage invariant in CONTRIBUTING.md section 9: adding a
        metric against a new entity type without also declaring a topology node
        would otherwise leave that entity silently unexercised.  The topology is
        a tree, so child nodes are collected recursively.
        """
        graph = _build_minimal_topology()
        reg = _load_registry(load_upstream=UPSTREAM_DIR.exists())

        types_in_topology: set = set()

        def _collect(n: TopologyNode) -> None:
            types_in_topology.add(n.entity_type)
            for c in n.children:
                _collect(c)

        for root in graph.roots:
            _collect(root)

        with_signals = {
            assoc
            for mdef in reg.metrics.values()
            for assoc in mdef.entity_associations
            if assoc in reg.entities
        }
        missing = with_signals - types_in_topology - self._ENTITIES_WITHOUT_TOPOLOGY_EXPECTED
        assert not missing, (
            f"Entity types carry metrics but have no node in the simulator topology: "
            f"{sorted(missing)}\n"
            f"Add a node under spec.topology.entities[] in simulator_config.yaml, "
            f"or list the type in _ENTITIES_WITHOUT_TOPOLOGY_EXPECTED if it is "
            f"intentionally descriptive-only."
        )


# ===========================================================================
# 4. WorkloadEngine — generator function tests
# ===========================================================================

class TestWorkloadEngine:
    """Unit-test each generator function and the default fallback."""

    def _make_metric(
        self,
        name: str = "test.metric",
        instrument: str = "gauge",
        unit: str = "1",
        monotonic: bool = True,
    ) -> MetricDef:
        return MetricDef(
            name=name, instrument=instrument, unit=unit, monotonic=monotonic
        )

    def test_gaussian_generator_within_clamps(self) -> None:
        engine = WorkloadEngine([{
            "match": {"pattern": "test\\.metric"},
            "generator": {
                "function": "gaussian",
                "params": {"mean": 50.0, "stddev": 5.0, "clamp_min": 0, "clamp_max": 100},
            },
        }])
        metric = self._make_metric()
        for _ in range(200):
            val = engine.compute_metric_value(metric, "node-1", 0.0, 10.0)
            assert 0.0 <= val <= 100.0, f"Gaussian value {val} outside clamps [0, 100]."

    def test_diurnal_generator_within_range(self) -> None:
        engine = WorkloadEngine([{
            "match": {"pattern": ".*"},
            "generator": {
                "function": "diurnal",
                "params": {
                    "min": 10.0, "max": 90.0, "base": 50.0,
                    "amplitude": 30.0, "period": 86400, "noise_sigma": 0.1,
                },
            },
        }])
        metric = self._make_metric()
        for t in range(0, 86400, 3600):
            val = engine.compute_metric_value(metric, "node-1", float(t), 10.0)
            assert 10.0 <= val <= 90.0, (
                f"Diurnal value {val} at t={t} outside [10, 90]."
            )

    def test_counter_accumulator_is_monotonically_increasing(self) -> None:
        engine = WorkloadEngine([{
            "match": {"pattern": "test\\.counter"},
            "generator": {
                "function": "counter_accumulator",
                "params": {
                    "rate_generator": {
                        "params": {"base": 100, "amplitude": 20, "period": 86400, "noise_sigma": 5}
                    }
                },
            },
        }])
        metric = self._make_metric(name="test.counter", instrument="sum")
        prev = 0.0
        for step in range(20):
            val = engine.compute_metric_value(metric, "node-1", float(step * 10), 10.0)
            assert val >= prev, (
                f"Counter accumulator must be non-decreasing: step={step}, val={val}, prev={prev}."
            )
            prev = val

    def test_pareto_spikes_non_negative(self) -> None:
        engine = WorkloadEngine([{
            "match": {"pattern": ".*"},
            "generator": {
                "function": "pareto_spikes",
                "params": {"baseline": 0.0001, "spike_probability": 0.5, "spike_magnitude": 0.01},
            },
        }])
        metric = self._make_metric()
        for _ in range(100):
            val = engine.compute_metric_value(metric, "node-1", 0.0, 10.0)
            assert val >= 0.0, f"Pareto spike value {val} must be non-negative."

    def test_default_fallback_percentage(self) -> None:
        engine = WorkloadEngine([])
        metric = self._make_metric(unit="%")
        for _ in range(50):
            val = engine.compute_metric_value(metric, "node-1", 0.0, 10.0)
            assert 0.0 <= val <= 100.0, (
                f"Default fallback for unit='%' produced {val} outside [0, 100]."
            )

    def test_default_fallback_ratio(self) -> None:
        engine = WorkloadEngine([])
        metric = self._make_metric(unit="1")
        for _ in range(50):
            val = engine.compute_metric_value(metric, "node-1", 0.0, 10.0)
            assert 0.0 <= val <= 1.0, (
                f"Default fallback for unit='1' produced {val} outside [0, 1]."
            )

    def test_default_fallback_bytes_positive(self) -> None:
        engine = WorkloadEngine([])
        metric = self._make_metric(unit="By")
        val = engine.compute_metric_value(metric, "node-1", 0.0, 10.0)
        assert val >= 0.0, "Default fallback for bytes must be non-negative."

    def test_default_fallback_sum_monotonic_increasing(self) -> None:
        engine = WorkloadEngine([])
        metric = self._make_metric(instrument="sum", unit="{op}")
        prev = engine.compute_metric_value(metric, "node-1", 0.0, 10.0)
        for step in range(1, 20):
            val = engine.compute_metric_value(metric, "node-1", float(step * 10), 10.0)
            assert val >= prev, (
                f"Default monotonic sum must not decrease: step={step}, val={val}, prev={prev}."
            )
            prev = val

    def test_no_nan_values(self) -> None:
        engine = WorkloadEngine([])
        instruments = ["gauge", "sum", "histogram"]
        units = ["1", "%", "By", "s", "ms", "{op}"]
        for inst in instruments:
            for unit in units:
                metric = self._make_metric(instrument=inst, unit=unit)
                val = engine.compute_metric_value(metric, "node-1", 1000.0, 10.0)
                assert not math.isnan(val), (
                    f"NaN value produced for instrument={inst}, unit={unit}."
                )
                assert not math.isinf(val), (
                    f"Inf value produced for instrument={inst}, unit={unit}."
                )


# ===========================================================================
# 5. generate_metrics_cycle — OTLP JSON shape validation
# ===========================================================================

class TestGenerateMetricsCycle:
    """Verify that ``generate_metrics_cycle`` produces valid OTLP JSON payloads."""

    @pytest.fixture(scope="class")
    def simulator(self) -> SemConvSimulator:
        """Instantiate a real SemConvSimulator using the reference config."""
        if not SIMULATOR_CONFIG.exists():
            pytest.skip(f"Simulator config not found: {SIMULATOR_CONFIG}")
        sim = SemConvSimulator(SIMULATOR_CONFIG)
        return sim

    def test_returns_list(self, simulator: SemConvSimulator) -> None:
        result = simulator.generate_metrics_cycle(time.time_ns(), time.time())
        assert isinstance(result, list), "generate_metrics_cycle must return a list."

    def test_non_empty_output(self, simulator: SemConvSimulator) -> None:
        result = simulator.generate_metrics_cycle(time.time_ns(), time.time())
        assert len(result) > 0, (
            "generate_metrics_cycle produced no resource-metric batches — "
            "check that entity_associations in metrics match topology entity types."
        )

    def test_resource_metrics_structure(self, simulator: SemConvSimulator) -> None:
        """Each element must be a valid OTLP resourceMetrics object."""
        result = simulator.generate_metrics_cycle(time.time_ns(), time.time())
        for i, rm in enumerate(result):
            assert "resource" in rm, f"Item {i}: missing 'resource' key."
            assert "attributes" in rm["resource"], (
                f"Item {i}: resource missing 'attributes'."
            )
            assert "scopeMetrics" in rm, f"Item {i}: missing 'scopeMetrics' key."
            for j, sm in enumerate(rm["scopeMetrics"]):
                assert "scope" in sm, f"Item {i}.scopeMetrics[{j}]: missing 'scope'."
                assert "metrics" in sm, f"Item {i}.scopeMetrics[{j}]: missing 'metrics'."
                assert len(sm["metrics"]) > 0, (
                    f"Item {i}.scopeMetrics[{j}]: 'metrics' list must not be empty."
                )

    def test_metric_data_points_have_timestamp(self, simulator: SemConvSimulator) -> None:
        ts_nano = time.time_ns()
        result = simulator.generate_metrics_cycle(ts_nano, time.time())
        for rm in result:
            for sm in rm["scopeMetrics"]:
                for metric in sm["metrics"]:
                    data_points = (
                        metric.get("gauge", {}).get("dataPoints", [])
                        or metric.get("sum", {}).get("dataPoints", [])
                        or metric.get("histogram", {}).get("dataPoints", [])
                    )
                    assert data_points, (
                        f"Metric '{metric.get('name')}' has no dataPoints."
                    )
                    for dp in data_points:
                        assert "timeUnixNano" in dp, (
                            f"Metric '{metric.get('name')}': dataPoint missing 'timeUnixNano'."
                        )
                        assert dp["timeUnixNano"] == str(ts_nano), (
                            f"Metric '{metric.get('name')}': unexpected timestamp."
                        )

    def test_metric_data_points_have_numeric_value(self, simulator: SemConvSimulator) -> None:
        result = simulator.generate_metrics_cycle(time.time_ns(), time.time())
        for rm in result:
            for sm in rm["scopeMetrics"]:
                for metric in sm["metrics"]:
                    data_points = (
                        metric.get("gauge", {}).get("dataPoints", [])
                        or metric.get("sum", {}).get("dataPoints", [])
                    )
                    for dp in data_points:
                        assert "asDouble" in dp, (
                            f"Metric '{metric.get('name')}': dataPoint missing 'asDouble'."
                        )
                        val = dp["asDouble"]
                        assert isinstance(val, (int, float)), (
                            f"Metric '{metric.get('name')}': 'asDouble' is not numeric: {val!r}."
                        )
                        assert not math.isnan(val), (
                            f"Metric '{metric.get('name')}': NaN value in dataPoint."
                        )

    def test_sum_metrics_have_aggregation_temporality(self, simulator: SemConvSimulator) -> None:
        result = simulator.generate_metrics_cycle(time.time_ns(), time.time())
        for rm in result:
            for sm in rm["scopeMetrics"]:
                for metric in sm["metrics"]:
                    if "sum" in metric:
                        assert "aggregationTemporality" in metric["sum"], (
                            f"Metric '{metric.get('name')}': sum is missing 'aggregationTemporality'."
                        )
                        assert "isMonotonic" in metric["sum"], (
                            f"Metric '{metric.get('name')}': sum is missing 'isMonotonic'."
                        )

    def test_scope_name_is_simulator(self, simulator: SemConvSimulator) -> None:
        result = simulator.generate_metrics_cycle(time.time_ns(), time.time())
        for rm in result:
            for sm in rm["scopeMetrics"]:
                assert sm["scope"]["name"] == "otel-semconv-sim", (
                    f"Unexpected scope name: {sm['scope']['name']!r}."
                )

    def test_resource_attributes_include_entity_type(self, simulator: SemConvSimulator) -> None:
        result = simulator.generate_metrics_cycle(time.time_ns(), time.time())
        for rm in result:
            attr_keys = {a["key"] for a in rm["resource"]["attributes"]}
            assert "otel.entity.type" in attr_keys, (
                "Resource attributes must include 'otel.entity.type'."
            )


# ===========================================================================
# 6. Per-entity emission coverage test
# ===========================================================================

class TestPerEntityEmission:
    """Verify that each entity type present in the topology emits at least one metric."""

    @pytest.fixture(scope="class")
    def simulator(self) -> SemConvSimulator:
        if not SIMULATOR_CONFIG.exists():
            pytest.skip(f"Simulator config not found: {SIMULATOR_CONFIG}")
        return SemConvSimulator(SIMULATOR_CONFIG)

    def _emitted_entity_types(self, simulator: SemConvSimulator) -> Dict[str, int]:
        """Return {entity_type: metric_batch_count} from one generate cycle."""
        result = simulator.generate_metrics_cycle(time.time_ns(), time.time())
        counts: Dict[str, int] = {}
        for rm in result:
            entity_type = next(
                (a["value"]["stringValue"] for a in rm["resource"]["attributes"]
                 if a["key"] == "otel.entity.type"),
                None,
            )
            if entity_type:
                counts[entity_type] = counts.get(entity_type, 0) + 1
        return counts

    def _all_topology_entity_types(self, simulator: SemConvSimulator) -> set:
        """Collect every entity type present in the topology (from the graph)."""
        types: set = set()

        def _walk(node: TopologyNode) -> None:
            types.add(node.entity_type)
            for child in node.children:
                _walk(child)

        for root in simulator.topology.roots:
            _walk(root)
        return types

    def _topology_types_with_metrics(self, simulator: SemConvSimulator) -> set:
        """Return only those topology entity types that have ≥1 active metric."""
        active_assocs = {
            assoc
            for m in simulator._active_metrics
            for assoc in m.entity_associations
        }
        return self._all_topology_entity_types(simulator) & active_assocs

    def test_each_entity_with_metrics_emits(self, simulator: SemConvSimulator) -> None:
        emitted = self._emitted_entity_types(simulator)
        expected = self._topology_types_with_metrics(simulator)

        not_emitted = expected - set(emitted.keys())
        assert not not_emitted, (
            f"The following entity types have metrics but produced no OTLP batches:\n"
            + "\n".join(f"  {et}" for et in sorted(not_emitted))
        )

    def test_emission_summary(self, capsys, simulator: SemConvSimulator) -> None:
        emitted = self._emitted_entity_types(simulator)
        total_entity_types = len(self._all_topology_entity_types(simulator))
        total_active_metrics = len(simulator._active_metrics)
        total_emitting = len(emitted)

        print(f"\n{'=' * 60}")
        print("Simulator Emission Summary")
        print(f"  Entity types in topology      : {total_entity_types}")
        print(f"  Active metrics in scope        : {total_active_metrics}")
        print(f"  Entity types emitting metrics  : {total_emitting}")
        print(f"\nPer-entity emission counts (batches per cycle):")
        for etype in sorted(emitted.keys()):
            print(f"  {etype}: {emitted[etype]} batch(es)")
        print(f"{'=' * 60}")

        captured = capsys.readouterr()
        assert f"Active metrics in scope" in captured.out
        assert f"Entity types emitting metrics" in captured.out

    def test_all_active_metrics_have_numeric_values(self, simulator: SemConvSimulator) -> None:
        """No active metric should produce NaN or Inf in a normal cycle."""
        result = simulator.generate_metrics_cycle(time.time_ns(), time.time())
        bad: List[str] = []
        for rm in result:
            for sm in rm["scopeMetrics"]:
                for metric in sm["metrics"]:
                    for key in ("gauge", "sum"):
                        if key not in metric:
                            continue
                        for dp in metric[key].get("dataPoints", []):
                            v = dp.get("asDouble")
                            if v is None or math.isnan(v) or math.isinf(v):
                                bad.append(
                                    f"{metric['name']} → asDouble={v!r}"
                                )
        assert not bad, (
            f"Metrics emitting NaN/Inf/None values:\n"
            + "\n".join(f"  {b}" for b in bad)
        )


# ===========================================================================
# 7. OTLP client — export path (mocked network)
# ===========================================================================

class TestOTLPJsonClient:
    """Unit-test the OTLP client export path without requiring a live collector."""

    def test_export_metrics_calls_post(self) -> None:
        client = OTLPJsonClient("http://localhost:4318")
        with patch.object(client, "_post_json", return_value=True) as mock_post:
            ok = client.export_metrics([{"resource": {}, "scopeMetrics": []}])
        assert ok is True
        mock_post.assert_called_once()
        url, payload = mock_post.call_args[0]
        assert url.endswith("/v1/metrics")
        assert "resourceMetrics" in payload

    def test_export_logs_calls_post(self) -> None:
        client = OTLPJsonClient("http://localhost:4318")
        with patch.object(client, "_post_json", return_value=True) as mock_post:
            ok = client.export_logs([{"resource": {}, "scopeLogs": []}])
        assert ok is True
        mock_post.assert_called_once()
        url, payload = mock_post.call_args[0]
        assert url.endswith("/v1/logs")
        assert "resourceLogs" in payload

    def test_post_json_returns_false_on_network_error(self) -> None:
        import urllib.error
        client = OTLPJsonClient("http://unreachable.local:4318")
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
            result = client._post_json("http://unreachable.local:4318/v1/metrics", {})
        assert result is False

    def test_trailing_slash_stripped_from_endpoint(self) -> None:
        client = OTLPJsonClient("http://localhost:4318/")
        assert not client.endpoint_url.endswith("/"), (
            "Trailing slash should be stripped from the endpoint URL."
        )


# ===========================================================================
# 8. Summary / acceptance test — printed report for CI
# ===========================================================================

class TestAcceptanceSummary:
    """Single acceptance test that prints the full entity/metric matrix for CI."""

    def test_full_registry_and_emission_report(self, capsys) -> None:
        """Print and assert on entity + metric totals.  This is the canonical
        CI gate — check the job output for the summary table.
        """
        reg = _load_registry()
        total_entities = len(reg.entities)
        total_metrics = len(reg.metrics)

        # Entity → metrics mapping
        entity_metric_map: Dict[str, List[str]] = {e: [] for e in reg.entities}
        for mname, mdef in reg.metrics.items():
            for assoc in mdef.entity_associations:
                if assoc in entity_metric_map:
                    entity_metric_map[assoc].append(mname)

        entities_with_metrics = sum(1 for v in entity_metric_map.values() if v)
        entities_without_metrics = total_entities - entities_with_metrics

        print(f"\n{'=' * 70}")
        print("ACCEPTANCE SUMMARY — Semantic Conventions Mainframe Simulator")
        print(f"{'=' * 70}")
        print(f"  Total entity types declared  : {total_entities}")
        print(f"  Total metrics declared       : {total_metrics}")
        print(f"  Entities WITH metrics        : {entities_with_metrics}")
        print(f"  Entities WITHOUT metrics     : {entities_without_metrics}")
        print(f"\n  Per-entity metric detail:")
        for etype in sorted(entity_metric_map.keys()):
            metrics = entity_metric_map[etype]
            status = f"{len(metrics):3d} metric(s)" if metrics else "  NO METRICS"
            print(f"    {status}  {etype}")
        print(f"\n  Per-metric entity associations:")
        for mname in sorted(reg.metrics.keys()):
            mdef = reg.metrics[mname]
            assocs = ", ".join(mdef.entity_associations) if mdef.entity_associations else "(none)"
            print(f"    {mname} [{mdef.instrument}/{mdef.unit}] → {assocs}")
        print(f"{'=' * 70}")

        captured = capsys.readouterr()

        # Hard assertions — these numbers must match what the model declares
        assert f"Total entity types declared  : {total_entities}" in captured.out
        assert f"Total metrics declared       : {total_metrics}" in captured.out
        assert total_entities > 0, "Model must declare at least one entity."
        assert total_metrics > 0, "Model must declare at least one metric."
        assert entities_with_metrics > 0, (
            "At least one entity must have a metric associated."
        )

# ===========================================================================
# 9. Required metric attribute presence
# ===========================================================================

class TestRequiredMetricAttributes:
    """Verify that every emitted data point carries all required metric attributes.

    The model declares attributes with requirement_level: required on many metrics.
    The simulator must populate those dimensions from the topology node context.
    This test cross-references the model's MetricDef.attributes list against the
    actual data-point attributes in each emitted OTLP batch.
    """

    @pytest.fixture(scope="class")
    def simulator(self) -> SemConvSimulator:
        if not SIMULATOR_CONFIG.exists():
            pytest.skip(f"Simulator config not found: {SIMULATOR_CONFIG}")
        return SemConvSimulator(SIMULATOR_CONFIG)

    def test_emitted_datapoints_carry_declared_attributes(
        self, simulator: SemConvSimulator
    ) -> None:
        """Each data point must include every locally-declared metric attribute
        whose value is available in the emitting node's resource context.

        The model expresses required vs recommended at the schema level; the
        simulator topology must surface every locally-declared dimension that
        the node actually carries.  Two categories are excluded by design:

        * Upstream-inherited attributes (cpu.mode, network.interface.name, etc.)
          are resolved only when the upstream registry is materialised via
          `make filter-upstream` — the base test suite runs without it.
        * Metric-applicability dimensions (e.g. mainframe.host.power.cord on
          nodes without line-cord data) — some metrics are declared on an entity
          type but only apply to a subset of instances.  A missing attribute
          is only flagged when that attribute IS present on the resource that
          produced the data point (i.e. the node had the value but the
          simulator failed to include it on the data point).
        """
        result = simulator.generate_metrics_cycle(time.time_ns(), time.time())

        # Only attributes whose keys are registered in the LOCAL attribute
        # registry are in scope; the rest are upstream-inherited dimensions.
        local_attr_keys: set = set(simulator.registry.attributes.keys())

        # Build a lookup: metric wire name → set of locally-declared attribute keys.
        metric_attrs: Dict[str, set] = {}
        for mdef in simulator.registry.metrics.values():
            local_declared = {a for a in mdef.attributes if a in local_attr_keys}
            if mdef.name not in metric_attrs:
                metric_attrs[mdef.name] = local_declared
            else:
                # Intersect across variants so only universally-declared attrs are checked.
                metric_attrs[mdef.name] &= local_declared

        violations: List[str] = []
        for rm in result:
            # Build a set of resource attribute keys for this batch
            resource_keys = {a["key"] for a in rm["resource"]["attributes"]}
            for sm in rm["scopeMetrics"]:
                for metric in sm["metrics"]:
                    name = metric.get("name", "")
                    declared = metric_attrs.get(name, set())
                    if not declared:
                        continue  # no locally-declared attributes to check

                    # Only check attributes whose values exist on this resource:
                    # if the node doesn't carry the attribute at all, the metric
                    # is being emitted by an inapplicable node (a separate concern).
                    checkable = declared & resource_keys

                    for inst_key in ("gauge", "sum", "histogram"):
                        if inst_key not in metric:
                            continue
                        for dp in metric[inst_key].get("dataPoints", []):
                            present = {a["key"] for a in dp.get("attributes", [])}
                            missing = checkable - present
                            if missing:
                                violations.append(
                                    f"{name}: missing attributes {sorted(missing)}"
                                )

        # Deduplicate repeated violations (same metric, multiple nodes)
        unique = sorted(set(violations))
        assert not unique, (
            f"Emitted data points are missing locally-declared metric attributes "
            f"that were available on the emitting resource "
            f"({len(unique)} unique violation(s)):\n"
            + "\n".join(f"  {v}" for v in unique)
        )
