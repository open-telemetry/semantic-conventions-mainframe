"""Emit a topology's telemetry over OTLP, once or continuously.

Usage:
    python -m semconv_mainframe.emitter --topology T --workload W [--cycles N] [--interval S]

``--cycles 0`` emits until interrupted. The registry is the working tree's
``model/`` as weaver resolves it, or ``--registry`` for a resolved file.
"""

from __future__ import annotations

import argparse
import contextlib
import logging
import sys
import time
from pathlib import Path

import grpc

from semconv_mainframe.emitter.otlp import Emitter, export
from semconv_mainframe.emitter.registry import Registry
from semconv_mainframe.emitter.topology import load_topology
from semconv_mainframe.emitter.workload import Workload

logger = logging.getLogger(__name__)


def run(emitter: Emitter, *, cycles: int = 1, interval: float = 10.0, endpoint: str | None = None) -> None:
    """Export ``cycles`` collections ``interval`` seconds apart (0: until interrupted)."""
    cycle = 0
    while cycles == 0 or cycle < cycles:
        if cycle:
            time.sleep(interval)
        request = emitter.request(time.time_ns(), interval)
        export(request, endpoint)
        cycle += 1
        points = sum(len(m.gauge.data_points) + len(m.sum.data_points) for r in request.resource_metrics
                     for s in r.scope_metrics for m in s.metrics)  # fmt: skip
        logger.info("cycle %s: %s resources, %s data points", cycle, len(request.resource_metrics), points)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
    parser = argparse.ArgumentParser(prog="python -m semconv_mainframe.emitter", description=__doc__.split("\n")[0])
    parser.add_argument("--topology", type=Path, required=True)
    parser.add_argument("--workload", type=Path, required=True)
    parser.add_argument("--registry", type=Path, help="A resolved registry file (default: resolve model/)")
    parser.add_argument("--cycles", type=int, default=1, help="Collections to export; 0 runs until interrupted")
    parser.add_argument("--interval", type=float, default=10.0, help="Seconds between collections")
    parser.add_argument("--endpoint", help="OTLP endpoint (default: OTEL_EXPORTER_OTLP_ENDPOINT)")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)
    registry = Registry.load(args.registry) if args.registry else Registry.from_model()
    emitter = Emitter(registry, load_topology(args.topology, registry), Workload.load(args.workload, seed=args.seed))
    try:
        with contextlib.suppress(KeyboardInterrupt):
            run(emitter, cycles=args.cycles, interval=args.interval, endpoint=args.endpoint)
    except (grpc.RpcError, OSError) as e:
        logger.error("OTLP export failed: %s", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
