"""Domain-Agnostic, Model-Driven OpenTelemetry Telemetry Simulation Engine (`otel-semconv-sim`).

Ingests Semantic Convention Definition Language v2 YAML files and synthesizes
continuous, high-fidelity OpenTelemetry signals (Metrics, Logs, Traces) via OTLP.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import random
import re
import signal
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    import yaml
except ImportError:
    print("PyYAML is required. Please install it with `pip install pyyaml`", file=sys.stderr)
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("otel-semconv-sim")


# =============================================================================
# 1. Schema Ingestor & Semantic Convention Model AST
# =============================================================================

@dataclass
class AttributeDef:
    id: str
    type: str = "string"
    brief: str = ""
    unit: Optional[str] = None
    members: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class EntityDef:
    type: str
    brief: str = ""
    identity: List[str] = field(default_factory=list)
    description_attributes: List[str] = field(default_factory=list)
    refines: Optional[str] = None


@dataclass
class MetricDef:
    name: str
    instrument: str  # normalised OTel wire name: gauge, sum, histogram
    unit: str
    brief: str = ""
    stability: str = "development"
    entity_associations: List[str] = field(default_factory=list)
    attributes: List[str] = field(default_factory=list)
    monotonic: bool = True
    # Original definition/2 instrument keyword (counter, updowncounter, gauge, …)
    # Preserved so workload profile type: rules can match against the semantic
    # instrument kind before normalization to the OTel wire name.
    original_instrument: str = ""


class SemConvRegistry:
    """Parses and indexes Semantic Convention Definition Language v2 models."""

    def __init__(self) -> None:
        self.attributes: Dict[str, AttributeDef] = {}
        self.entities: Dict[str, EntityDef] = {}
        self.metrics: Dict[str, MetricDef] = {}
        # Upstream v1 metric stubs: name -> {instrument, unit, brief, attributes}
        # Populated by load_upstream_directory(); used to resolve metric_refinements: ref: fields.
        self._upstream_metrics: Dict[str, Dict[str, Any]] = {}
        # Staging list for metric_refinements: entries, processed after all files are loaded.
        self._pending_refinements: List[Dict[str, Any]] = []
        # Staging list for entity_refinements: entries, resolved after all files are loaded.
        self._pending_entity_refinements: List[Dict[str, Any]] = []

    def load_directory(self, root_dir: Union[str, Path]) -> None:
        root = Path(root_dir)
        if not root.exists():
            logger.warning(f"Registry directory '{root}' does not exist.")
            return

        for yaml_file in sorted(root.rglob("*.yaml")):
            self.load_file(yaml_file)

    def load_file(self, file_path: Path) -> None:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = yaml.safe_load(f)
        except Exception as e:
            raise RuntimeError(f"Failed to parse local model file {file_path}: {e}") from e

        if not isinstance(content, dict):
            return

        # Check v2 header
        if content.get("file_format") != "definition/2":
            return

        # Parse Attributes
        for attr in content.get("attributes", []):
            if isinstance(attr, dict) and ("key" in attr or "id" in attr):
                attr_key = attr.get("key") or attr.get("id")
                members = []
                attr_type = "string"
                if isinstance(attr.get("type"), dict):
                    if "members" in attr["type"]:
                        attr_type = "enum"
                        members = attr["type"]["members"]
                elif isinstance(attr.get("type"), str):
                    attr_type = attr["type"]

                self.attributes[attr_key] = AttributeDef(
                    id=attr_key,
                    type=attr_type,
                    brief=attr.get("brief", ""),
                    members=members,
                )

        # Parse Entities
        for ent in content.get("entities", []):
            if isinstance(ent, dict) and "type" in ent:
                ent_type = ent["type"]
                identity = [
                    item["ref"] if isinstance(item, dict) and "ref" in item else item
                    for item in ent.get("identity", [])
                ]
                desc_attrs = [
                    item["ref"] if isinstance(item, dict) and "ref" in item else item
                    for item in ent.get("description", [])
                ]
                self.entities[ent_type] = EntityDef(
                    type=ent_type,
                    brief=ent.get("brief", ""),
                    identity=identity,
                    description_attributes=desc_attrs,
                )

        # Queue entity_refinements for deferred resolution.
        # Files are loaded directory by directory (mainframe before virtualization),
        # so a mainframe refinement of virtualization.* would fail an immediate
        # "refined_type in self.entities" check. Queue them here and resolve after
        # all directories are loaded via resolve_entity_refinements().
        for ref in content.get("entity_refinements", []):
            if isinstance(ref, dict):
                self._pending_entity_refinements.append(ref)

        # Collect metric_refinements: for later resolution (after all files are loaded)
        for ref in content.get("metric_refinements", []):
            if isinstance(ref, dict) and "ref" in ref:
                self._pending_refinements.append(ref)

        # Parse Metrics
        for m in content.get("metrics", []):
            if isinstance(m, dict) and "name" in m:
                m_name = m["name"]
                associations = m.get("entity_associations", [])
                attrs = [
                    item["ref"] if isinstance(item, dict) and "ref" in item else item
                    for item in m.get("attributes", [])
                ]
                orig_inst = m.get("instrument", "gauge").lower()
                # Normalise definition/2 instrument names to OTel wire names.
                # counter → sum (monotonic=True)
                # updowncounter → sum (monotonic=False)
                # gauge / histogram pass through unchanged.
                inst = orig_inst
                monotonic = True
                if inst == "counter":
                    inst = "sum"
                    monotonic = True
                elif inst == "updowncounter":
                    inst = "sum"
                    monotonic = False
                elif inst == "sum":
                    # Legacy/explicit sum — honour the model's monotonic flag.
                    monotonic = m.get("monotonic", True)

                self.metrics[m_name] = MetricDef(
                    name=m_name,
                    instrument=inst,
                    unit=m.get("unit", "1"),
                    brief=m.get("brief", ""),
                    stability=m.get("stability", "development"),
                    entity_associations=associations,
                    attributes=attrs,
                    monotonic=monotonic,
                    original_instrument=orig_inst,
                )

    # ------------------------------------------------------------------
    # Upstream registry loader (v1 groups: format)
    # ------------------------------------------------------------------

    def load_upstream_directory(self, root_dir: Union[str, Path]) -> None:
        """Load upstream OTel Semantic Convention registry (v1 groups: format).

        Reads every YAML file under *root_dir* that uses the v1 ``groups:``
        schema and populates ``self._upstream_metrics`` with the metric name,
        instrument, unit and brief for every group whose ``type`` is
        ``"metric"``.  These stubs are later used by
        ``_resolve_metric_refinements`` to synthesise ``MetricDef`` objects
        without duplicating upstream definitions in the local v2 model.
        """
        root = Path(root_dir)
        if not root.exists():
            logger.warning(f"Upstream registry directory '{root}' does not exist — skipping.")
            return
        count = 0
        for yaml_file in sorted(root.rglob("*.yaml")):
            count += self._load_upstream_file(yaml_file)
        logger.info(f"Upstream registry: loaded {count} metric stubs from {root}")

    def _load_upstream_file(self, file_path: Path) -> int:
        """Parse one v1 upstream YAML file; return number of metric stubs added."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = yaml.safe_load(f)
        except Exception as e:
            logger.debug(f"Skipping upstream file {file_path}: {e}")
            return 0
        if not isinstance(content, dict):
            return 0
        # v1 files use groups: list; v2 files use file_format: definition/2
        # Reject v2 files from this path — they are loaded via load_file()
        if content.get("file_format") == "definition/2":
            return 0
        if "groups" not in content:
            return 0
        added = 0
        for grp in content["groups"]:
            if not isinstance(grp, dict):
                continue
            if grp.get("type") != "metric":
                continue
            metric_name = grp.get("metric_name", "")
            if not metric_name:
                continue
            if metric_name in self._upstream_metrics:
                continue  # first definition wins
            inst_raw = grp.get("instrument", "gauge").lower()
            # v1 uses "counter" for monotonic sums
            inst = "counter" if inst_raw == "counter" else inst_raw
            # Collect upstream attribute names so refined MetricDefs inherit them.
            upstream_attrs = [
                item.get("ref") or item if isinstance(item, dict) else item
                for item in grp.get("attributes", [])
                if item
            ]
            self._upstream_metrics[metric_name] = {
                "instrument": inst,
                "unit": grp.get("unit", "1"),
                "brief": str(grp.get("brief", "")).strip(),
                "attributes": upstream_attrs,
            }
            added += 1
        return added

    # ------------------------------------------------------------------
    # metric_refinements: resolver
    # ------------------------------------------------------------------

    def resolve_entity_refinements(self) -> None:
        """Resolve queued entity_refinements after all model files have been loaded.

        Entity refinements are collected during file loading but resolved here so
        that cross-directory references (e.g. mainframe refinements of
        virtualization.* entities loaded from a different directory) succeed
        regardless of directory load order.
        """
        for ref in self._pending_entity_refinements:
            refined_type = ref.get("ref") or ref.get("refines") or ref.get("type")
            if refined_type and refined_type in self.entities:
                self.entities[refined_type].refines = refined_type
            else:
                logger.debug(
                    f"entity_refinements: ref='{refined_type}' not found in loaded entities — skipping"
                )

    def resolve_metric_refinements(self) -> None:
        """Promote metric_refinements: ref: entries into first-class MetricDef objects.

        A ``metric_refinements:`` block declares that a mainframe-specific
        (or virtualization-specific) context extends an upstream metric with
        additional ``entity_associations`` and attributes.  The simulator
        needs a ``MetricDef`` with the correct ``entity_associations`` so it
        can emit the signal against the right topology nodes.

        Resolution order:
        1. If the ``ref:`` metric is already in ``self.metrics`` (authored as
           a standalone v2 ``metrics:`` entry), the existing entry wins —
           no duplicate is created.
        2. Otherwise look up ``ref:`` in ``self._upstream_metrics``.  If
           found, create a new ``MetricDef`` using the upstream instrument/unit
           merged with the refinement's ``entity_associations`` and attributes.
        3. If neither source has the metric, emit a DEBUG warning and skip.

        Multiple refinements targeting the same upstream metric with *different*
        entity_associations each get their own keyed entry:
        ``{ref_name}#{refinement_id}``. This preserves distinct attribute sets
        (e.g. adapter-port NIC variant vs vSwitch variant of system.network.io).
        """
        for stub in self._pending_refinements:
            ref_name = stub["ref"]
            ref_id = stub.get("id", ref_name)
            ea = stub.get("entity_associations", [])

            # Merge refinement attrs on top of upstream base attrs so inherited
            # dimensions (cpu.mode, network.interface.name, etc.) are not lost.
            upstream_base_attrs: List[str] = []
            if ref_name in self._upstream_metrics:
                upstream_base_attrs = list(self._upstream_metrics[ref_name].get("attributes", []))

            ref_attrs = [
                item["ref"] if isinstance(item, dict) and "ref" in item else item
                for item in stub.get("attributes", [])
            ]
            # Union: upstream base attrs first, then refinement-specific ones.
            merged_attrs = list(upstream_base_attrs)
            for a in ref_attrs:
                if a not in merged_attrs:
                    merged_attrs.append(a)

            if ref_name in self.metrics and not ea:
                # Standalone v2 entry with no new entity_associations — leave it.
                continue

            if ref_name in self.metrics:
                existing = self.metrics[ref_name]
                # If same entity_associations already covered, just extend attrs.
                if set(ea) == set(existing.entity_associations):
                    for a in merged_attrs:
                        if a not in existing.attributes:
                            existing.attributes.append(a)
                    continue
                # Different entity_associations → create a named variant key.
                variant_key = f"{ref_name}#{ref_id}"
                if variant_key not in self.metrics:
                    self.metrics[variant_key] = MetricDef(
                        name=ref_name,  # OTLP wire name stays the upstream name
                        instrument=existing.instrument,
                        unit=existing.unit,
                        brief=stub.get("brief", existing.brief),
                        stability=stub.get("stability", existing.stability),
                        entity_associations=ea,
                        attributes=merged_attrs,
                        monotonic=existing.monotonic,
                        original_instrument=existing.original_instrument,
                    )
                continue

            if ref_name not in self._upstream_metrics:
                logger.debug(
                    f"metric_refinements: ref='{ref_name}' not found in upstream registry "
                    f"— cannot synthesise MetricDef (id={ref_id})"
                )
                continue

            upstream = self._upstream_metrics[ref_name]
            inst = upstream["instrument"]
            monotonic = inst == "counter"
            if inst in ("counter", "updowncounter"):
                monotonic = inst == "counter"
                inst = "sum"  # normalise to OTel wire instrument name

            orig_inst_upstream = upstream["instrument"]  # counter, updowncounter, gauge
            variant_key = ref_name if ref_name not in self.metrics else f"{ref_name}#{ref_id}"
            self.metrics[variant_key] = MetricDef(
                name=ref_name,
                instrument=inst,
                unit=upstream["unit"],
                brief=stub.get("brief", upstream["brief"]),
                stability=stub.get("stability", "development"),
                entity_associations=ea,
                attributes=merged_attrs,
                monotonic=monotonic,
                original_instrument=orig_inst_upstream,
            )

    def summary(self) -> str:
        return (
            f"Loaded {len(self.entities)} entities, {len(self.attributes)} attributes, "
            f"and {len(self.metrics)} metrics "
            f"({len(self._upstream_metrics)} upstream stubs available)."
        )


# =============================================================================
# 2. Dynamic Entity Topology Graph
# =============================================================================

@dataclass
class TopologyNode:
    entity_type: str
    identity: Dict[str, Any]
    attributes: Dict[str, Any]
    children: List[TopologyNode] = field(default_factory=list)

    # Inherited resource context from parent nodes (set by TopologyGraph._build_node).
    parent_context: Dict[str, Any] = field(default_factory=dict)

    def get_all_resource_attributes(self) -> Dict[str, Any]:
        """Merges identity and descriptive attributes for OTLP Resource.

        Parent context (inherited identity/attributes from ancestor nodes) is
        included first so that child nodes satisfy composite identity contracts
        that require attributes from their parent — e.g. a virtualization.partition
        node inheriting virtualization.platform.id from its platform parent.
        """
        res = dict(self.parent_context)
        res.update(self.attributes)
        res.update(self.identity)
        res["otel.entity.type"] = self.entity_type
        return res

    def find_nodes_by_type(self, target_type: str) -> List[TopologyNode]:
        matched = []
        if self.entity_type == target_type:
            matched.append(self)
        for child in self.children:
            matched.extend(child.find_nodes_by_type(target_type))
        return matched


class TopologyGraph:
    """Manages the hierarchical entity topology DAG."""

    def __init__(self) -> None:
        self.roots: List[TopologyNode] = []

    @classmethod
    def from_config(cls, topology_config: List[Dict[str, Any]]) -> TopologyGraph:
        graph = cls()
        for item in topology_config:
            graph.roots.append(cls._build_node(item))
        return graph

    @classmethod
    def _build_node(
        cls,
        node_dict: Dict[str, Any],
        parent_context: Optional[Dict[str, Any]] = None,
    ) -> TopologyNode:
        entity_type = node_dict.get("type", "unknown")
        identity = node_dict.get("identity", {})
        attributes = node_dict.get("attributes", {})
        # Build the context this node exposes to its children: ancestor context
        # plus this node's own identity and attributes (identity wins on conflict).
        own_context: Dict[str, Any] = {}
        if parent_context:
            own_context.update(parent_context)
        own_context.update(attributes)
        own_context.update(identity)
        children = [
            cls._build_node(child, own_context) for child in node_dict.get("children", [])
        ]
        return TopologyNode(
            entity_type=entity_type,
            identity=identity,
            attributes=attributes,
            children=children,
            parent_context=parent_context or {},
        )

    def find_all(self, target_type: str) -> List[TopologyNode]:
        result = []
        for root in self.roots:
            result.extend(root.find_nodes_by_type(target_type))
        return result


# =============================================================================
# 3. Declarative Workload Profile & Math Functions
# =============================================================================

class WorkloadEngine:
    """Evaluates declarative mathematical formulas for metric and signal values."""

    def __init__(self, profile_rules: List[Dict[str, Any]]) -> None:
        self.rules = profile_rules
        # State tracking for monotonic counters: key -> current cumulative value
        self._counter_state: Dict[str, float] = {}
        # Random walk state: key -> current value
        self._walk_state: Dict[str, float] = {}

    def compute_metric_value(
        self,
        metric: MetricDef,
        entity_id_key: str,
        sim_time_sec: float,
        step_delta_sec: float,
    ) -> Union[int, float]:
        rule = self._match_rule(metric)
        key = f"{entity_id_key}:{metric.name}"

        if not rule:
            # Domain-agnostic defaults based on unit and instrument
            return self._default_fallback(metric, key, sim_time_sec, step_delta_sec)

        gen = rule.get("generator", {})
        fn = gen.get("function", "gaussian")
        params = gen.get("params", {})

        if fn == "diurnal":
            min_val = float(params.get("min", 0.0))
            max_val = float(params.get("max", 100.0))
            base = float(params.get("base", (min_val + max_val) / 2.0))
            amplitude = float(params.get("amplitude", (max_val - min_val) / 4.0))
            period = float(params.get("period", 86400.0))
            phase = float(params.get("phase", 0.0))
            sigma = float(params.get("noise_sigma", 0.5))

            val = base + amplitude * math.sin((2 * math.pi * (sim_time_sec - phase)) / period)
            val += random.gauss(0, sigma)
            val = max(min_val, min(max_val, val))
            return val

        elif fn == "gaussian":
            mean = float(params.get("mean", 50.0))
            stddev = float(params.get("stddev", 5.0))
            val = random.gauss(mean, stddev)
            if "clamp_min" in params:
                val = max(float(params["clamp_min"]), val)
            if "clamp_max" in params:
                val = min(float(params["clamp_max"]), val)
            return val

        elif fn == "counter_accumulator":
            rate_gen = params.get("rate_generator", {})
            rate_base = float(rate_gen.get("params", {}).get("base", 100.0))
            rate_amp = float(rate_gen.get("params", {}).get("amplitude", 20.0))
            rate_period = float(rate_gen.get("params", {}).get("period", 86400.0))
            noise_sigma = float(rate_gen.get("params", {}).get("noise_sigma", 5.0))

            inst_rate = rate_base + rate_amp * math.sin((2 * math.pi * sim_time_sec) / rate_period)
            inst_rate = max(0.0, inst_rate + random.gauss(0, noise_sigma))

            delta = inst_rate * step_delta_sec
            current = self._counter_state.get(key, 1000000.0)
            current += delta
            self._counter_state[key] = current
            return current

        elif fn == "pareto_spikes":
            baseline = float(params.get("baseline", 0.0001))
            spike_prob = float(params.get("spike_probability", 0.01))
            spike_mag = float(params.get("spike_magnitude", 0.01))

            if random.random() < spike_prob:
                return baseline + random.expovariate(1.0 / spike_mag)
            return baseline + random.uniform(0, baseline * 0.1)

        return self._default_fallback(metric, key, sim_time_sec, step_delta_sec)

    def _match_rule(self, metric: MetricDef) -> Optional[Dict[str, Any]]:
        for rule in self.rules:
            match = rule.get("match", {})
            # Match regex pattern — if present, only this rule applies when the
            # pattern matches. If it does NOT match, skip to the next rule rather
            # than falling through to the unit/type check below (which would
            # incorrectly match every metric when those fields are absent).
            if "pattern" in match:
                if re.search(match["pattern"], metric.name):
                    return rule
                continue  # pattern present but didn't match — try next rule
            # Match unit and type (only reached when no pattern key is present).
            # type: matches against the original definition/2 instrument keyword
            # (counter, updowncounter, gauge) so profile rules like `type: updowncounter`
            # fire correctly even though MetricDef.instrument has been normalized to "sum".
            unit_match = match.get("unit") is None or match.get("unit") == metric.unit
            rule_type = match.get("type")
            type_match = (
                rule_type is None
                or rule_type == metric.original_instrument
                or rule_type == metric.instrument
            )
            if unit_match and type_match:
                return rule
        return None

    def _default_fallback(
        self,
        metric: MetricDef,
        key: str,
        sim_time_sec: float,
        step_delta_sec: float,
    ) -> float:
        if metric.unit in ("%", "1"):
            # Ratio 0..1 or Percentage 0..100
            scale = 100.0 if metric.unit == "%" else 1.0
            base = 0.45 * scale
            val = base + 0.3 * scale * math.sin((2 * math.pi * sim_time_sec) / 86400.0)
            val += random.gauss(0, 0.02 * scale)
            return max(0.0, min(scale, val))

        elif metric.unit in ("By", "bytes"):
            # Memory / Storage bytes
            return max(0.0, random.gauss(16.0 * 1024**3, 1024**2))

        elif metric.unit in ("s", "ms", "us"):
            # Latencies / times
            return max(0.0, random.gauss(0.005, 0.001))

        elif metric.instrument == "sum" and metric.monotonic:
            curr = self._counter_state.get(key, 500000.0)
            curr += random.uniform(10.0, 50.0) * step_delta_sec
            self._counter_state[key] = curr
            return curr

        # Fallback gauge/scalar
        return random.uniform(1.0, 100.0)


# =============================================================================
# 4. Universal OTLP Protobuf / JSON Multi-Signal Serializer
# =============================================================================

class OTLPJsonClient:
    """Emits OTLP/JSON payloads to an OpenTelemetry Collector HTTP endpoint."""

    def __init__(self, endpoint_url: str) -> None:
        self.endpoint_url = endpoint_url.rstrip("/")

    def export_metrics(self, resource_metrics: List[Dict[str, Any]]) -> bool:
        url = f"{self.endpoint_url}/v1/metrics"
        payload = {"resourceMetrics": resource_metrics}
        return self._post_json(url, payload)

    def export_logs(self, resource_logs: List[Dict[str, Any]]) -> bool:
        url = f"{self.endpoint_url}/v1/logs"
        payload = {"resourceLogs": resource_logs}
        return self._post_json(url, payload)

    def _post_json(self, url: str, data: Dict[str, Any]) -> bool:
        body = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status in (200, 202)
        except urllib.error.URLError as e:
            logger.error(f"OTLP export to {url} failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected export error to {url}: {e}")
            return False


# =============================================================================
# 5. Domain-Agnostic Simulation Engine Coordinator
# =============================================================================

class SemConvSimulator:
    """Core simulation engine driving model-driven telemetry synthesis."""

    def __init__(self, config_path: Union[str, Path]) -> None:
        self.config_path = Path(config_path)
        with open(self.config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

        self.registry = SemConvRegistry()
        self._load_registry()
        self.topology = self._build_topology()
        self.workload = self._build_workload()
        self.filter_patterns = self.config.get("spec", {}).get("selection", {}).get("include_namespaces", [".*"])
        self.sampling_interval = float(
            self.config.get("spec", {}).get("sampling_interval", 10.0)
        )
        self.otlp_client = OTLPJsonClient(
            self.config.get("spec", {}).get("exporter", {}).get("otlp", {}).get("http_endpoint", "http://localhost:4318")
        )
        self._active_metrics = self._filter_metrics()
        self._running = False

    def _load_registry(self) -> None:
        registry_cfg = self.config.get("spec", {}).get("registry", {})
        base_dir = self.config_path.parent

        # Step 1 — load upstream v1 registry (optional; provides instrument/unit stubs
        # that allow metric_refinements: ref: entries to be synthesised into MetricDefs)
        upstream_path = registry_cfg.get("upstream_path", "")
        if upstream_path:
            full_upstream = (base_dir / upstream_path).resolve()
            logger.info(f"Loading upstream registry (v1) from: {full_upstream}")
            self.registry.load_upstream_directory(full_upstream)

        # Step 2 — load local v2 model files
        for rel_path in registry_cfg.get("paths", []):
            full_path = (base_dir / rel_path).resolve()
            logger.info(f"Loading Semantic Convention registry from: {full_path}")
            self.registry.load_directory(full_path)

        # Step 3 — resolve entity_refinements and metric_refinements collected during step 2.
        # Both are deferred so cross-directory references resolve regardless of load order.
        self.registry.resolve_entity_refinements()
        self.registry.resolve_metric_refinements()

        logger.info(self.registry.summary())

    def _build_topology(self) -> TopologyGraph:
        top_cfg = self.config.get("spec", {}).get("topology", {}).get("entities", [])
        return TopologyGraph.from_config(top_cfg)

    def _build_workload(self) -> WorkloadEngine:
        profile_ref = self.config.get("spec", {}).get("workload_profile_ref")
        rules = []
        if profile_ref:
            p_path = (self.config_path.parent / profile_ref).resolve()
            if p_path.exists():
                logger.info(f"Loading Workload Profile: {p_path}")
                with open(p_path, "r", encoding="utf-8") as f:
                    p_content = yaml.safe_load(f)
                    rules = p_content.get("spec", {}).get("rules", [])
        return WorkloadEngine(rules)

    @staticmethod
    def _otlp_value(v: Any) -> Dict[str, Any]:
        """Encode a Python scalar as the appropriate OTLP AnyValue."""
        if isinstance(v, bool):
            return {"boolValue": v}
        if isinstance(v, int):
            return {"intValue": v}
        if isinstance(v, float):
            return {"doubleValue": v}
        return {"stringValue": str(v)}

    def _filter_metrics(self) -> List[MetricDef]:
        active = []
        for name, metric in self.registry.metrics.items():
            matched = any(re.search(pat, name) for pat in self.filter_patterns)
            if matched:
                active.append(metric)
        logger.info(f"Active simulation metrics in scope: {len(active)} / {len(self.registry.metrics)}")
        return active

    def generate_metrics_cycle(self, timestamp_nano: int, sim_time_sec: float) -> List[Dict[str, Any]]:
        resource_metrics_list = []

        # Group metrics emission by matching entity nodes
        for entity_type in self.registry.entities.keys():
            matching_nodes = self.topology.find_all(entity_type)
            if not matching_nodes:
                continue

            # Find metrics associated with this entity type
            associated_metrics = [
                m for m in self._active_metrics if entity_type in m.entity_associations
            ]
            if not associated_metrics:
                continue

            for node in matching_nodes:
                res_attrs = [
                    {"key": k, "value": self._otlp_value(v)}
                    for k, v in node.get_all_resource_attributes().items()
                ]

                scope_metrics = []
                # Build a state key that incorporates the node's full resource
                # context so that nodes sharing the same entity identity but
                # differing on a discriminating dimension (e.g. read vs write for
                # disk.io.direction, receive vs transmit for network.io.direction)
                # maintain independent counter series and don't contaminate each
                # other's cumulative values.
                node_res = node.get_all_resource_attributes()
                node_id_key = str(sorted(node_res.items()))

                # Deduplicate metrics by wire name: when multiple refinement
                # variants share the same upstream metric name (e.g. a
                # virtualization refinement of system.cpu.time associates with
                # the same entity across multiple entity types), emit only the
                # first variant per node to avoid duplicate same-name records
                # in one OTLP scope.
                seen_metric_names: set = set()
                for m in associated_metrics:
                    if m.name in seen_metric_names:
                        continue
                    seen_metric_names.add(m.name)

                    val = self.workload.compute_metric_value(
                        m, node_id_key, sim_time_sec, self.sampling_interval
                    )

                    metric_data: Dict[str, Any] = {
                        "name": m.name,
                        "description": m.brief,
                        "unit": m.unit,
                    }

                    # Build data-point attributes from the node's resource context
                    # and the metric's declared attribute list only. otel.entity.type
                    # is a resource attribute, not a metric dimension — exclude it
                    # from data points so it does not become an undeclared attribute.
                    point_attrs = [
                        {"key": k, "value": self._otlp_value(v)}
                        for k, v in node_res.items()
                        if k in m.attributes
                    ]

                    point = {
                        "timeUnixNano": str(timestamp_nano),
                        "asDouble": float(val),
                        "attributes": point_attrs,
                    }

                    if m.instrument == "gauge":
                        metric_data["gauge"] = {"dataPoints": [point]}
                    elif m.instrument == "sum":
                        metric_data["sum"] = {
                            "dataPoints": [point],
                            "aggregationTemporality": 2,  # AGGREGATION_TEMPORALITY_CUMULATIVE
                            "isMonotonic": m.monotonic,
                        }
                    else:
                        metric_data["gauge"] = {"dataPoints": [point]}

                    scope_metrics.append(metric_data)

                if scope_metrics:
                    resource_metrics_list.append({
                        "resource": {"attributes": res_attrs},
                        "scopeMetrics": [{
                            "scope": {"name": "otel-semconv-sim", "version": "1.0.0"},
                            "metrics": scope_metrics,
                        }],
                    })

        return resource_metrics_list

    def generate_logs_cycle(self, timestamp_nano: int) -> List[Dict[str, Any]]:
        resource_logs_list = []
        for root in self.topology.roots:
            res_attrs = [
                {"key": k, "value": self._otlp_value(v)}
                for k, v in root.get_all_resource_attributes().items()
            ]
            log_record = {
                "timeUnixNano": str(timestamp_nano),
                "severityNumber": 9,  # INFO
                "severityText": "INFO",
                "body": {"stringValue": f"System heartbeat verified on entity {root.entity_type}."},
                "attributes": [
                    {"key": "simulation.status", "value": {"stringValue": "nominal"}}
                ],
            }
            resource_logs_list.append({
                "resource": {"attributes": res_attrs},
                "scopeLogs": [{
                    "scope": {"name": "otel-semconv-sim", "version": "1.0.0"},
                    "logRecords": [log_record],
                }],
            })
        return resource_logs_list

    def run_once(self) -> bool:
        """Emit one telemetry cycle. Returns True if all exports succeeded."""
        now_nano = time.time_ns()
        sim_time = time.time()
        res_metrics = self.generate_metrics_cycle(now_nano, sim_time)
        res_logs = self.generate_logs_cycle(now_nano)

        success = True
        if res_metrics:
            ok_m = self.otlp_client.export_metrics(res_metrics)
            logger.info(f"Emitted {len(res_metrics)} resource metric batches. Status: {'OK' if ok_m else 'FAILED'}")
            if not ok_m:
                success = False
        if res_logs:
            ok_l = self.otlp_client.export_logs(res_logs)
            logger.info(f"Emitted {len(res_logs)} resource log records. Status: {'OK' if ok_l else 'FAILED'}")
            if not ok_l:
                success = False
        return success

    def run_loop(self) -> None:
        self._running = True
        logger.info(f"Starting continuous telemetry simulation loop (Interval: {self.sampling_interval}s)...")
        while self._running:
            try:
                self.run_once()
                time.sleep(self.sampling_interval)
            except KeyboardInterrupt:
                logger.info("Simulation loop interrupted by user.")
                break
            except Exception as e:
                logger.error(f"Error during simulation cycle: {e}", exc_info=True)
                time.sleep(self.sampling_interval)

    def stop(self) -> None:
        self._running = False


# =============================================================================
# 6. CLI Entrypoint
# =============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Domain-Agnostic, Model-Driven OpenTelemetry Telemetry Simulator (otel-semconv-sim)"
    )
    parser.add_argument(
        "--config",
        "-c",
        default="./simulator_config.yaml",
        help="Path to simulator configuration YAML",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single telemetry synthesis iteration and exit",
    )
    parser.add_argument(
        "--namespaces",
        "-n",
        help="Override namespace include filter regex (e.g., 'mainframe.*,virtualization.*')",
    )
    parser.add_argument(
        "--interval",
        "-i",
        type=float,
        help="Override sampling interval in seconds",
    )

    args = parser.parse_args()

    cfg_path = Path(args.config)
    if not cfg_path.exists():
        logger.error(f"Configuration file not found: {cfg_path}")
        sys.exit(1)

    sim = SemConvSimulator(cfg_path)

    if args.namespaces:
        sim.filter_patterns = [p.strip() for p in args.namespaces.split(",")]
        sim._active_metrics = sim._filter_metrics()

    if args.interval:
        sim.sampling_interval = args.interval

    def signal_handler(sig, frame):
        logger.info("Termination signal received. Shutting down simulator...")
        sim.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    if args.once:
        ok = sim.run_once()
        if not ok:
            logger.error("One-shot emission failed; exiting with status 1.")
            sys.exit(1)
    else:
        sim.run_loop()


if __name__ == "__main__":
    main()
