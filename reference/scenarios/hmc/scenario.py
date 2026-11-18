"""HMC reference scenario: what an IBM Z HMC-based collector reports for one CPC.

Emits one collection of every metric ``model/`` associates with the entities
in ``topology.yaml`` -- the mainframe and virtualization metrics and the
``system.*`` and ``hw.*`` refinements -- with values from ``workload.yaml``,
to ``OTEL_EXPORTER_OTLP_ENDPOINT``. The values are synthetic; the resources,
names, units, instruments and attributes are what the conventions prescribe.

It fails rather than emits when a metric definition associated with an entity
of the topology would produce no data point, so a refinement can not drop out
of the run unnoticed (review finding P12).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from semconv_mainframe.emitter import Emitter, Registry, Workload, export, load_topology

HERE = Path(__file__).resolve().parent
INTERVAL_SECONDS = 60.0  # the HMC metrics context sampling interval this collection stands for


def build_emitter(registry: Registry) -> Emitter:
    topology = load_topology(HERE / "topology.yaml", registry)
    return Emitter(registry, topology, Workload.load(HERE / "workload.yaml", seed=42))


def unemitted(registry: Registry, emitter: Emitter) -> list[str]:
    """Metric definitions associated with an entity of the topology that emit nothing."""
    entity_types = {node.entity_type for node, _, _ in emitter.plan}
    expected = {m.id for m in registry.metrics.values() if entity_types & set(m.entity_associations)}
    return sorted(expected - emitter.emitted_metric_ids())


def main() -> int:
    registry = Registry.from_model()
    emitter = build_emitter(registry)
    missing = unemitted(registry, emitter)
    if missing:
        print(f"metric definitions without data points: {', '.join(missing)}", file=sys.stderr)
        return 1
    export(emitter.request(time.time_ns(), INTERVAL_SECONDS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
