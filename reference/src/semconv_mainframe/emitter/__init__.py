"""A synthetic, model-driven telemetry emitter for reference scenarios.

Given the resolved registry, an entity topology and a workload profile, it
emits every metric the registry associates with each entity in the topology.
Nothing about mainframes is coded here: a scenario supplies both files.
"""

from semconv_mainframe.emitter.registry import AttributeDef, EntityDef, MetricDef, Registry
from semconv_mainframe.emitter.topology import Node, TopologyError, build_topology, load_topology

__all__ = [
    "AttributeDef",
    "EntityDef",
    "MetricDef",
    "Node",
    "Registry",
    "TopologyError",
    "build_topology",
    "load_topology",
]
