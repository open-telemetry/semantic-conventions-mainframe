"""
Host scenario — exercises all mainframe.host.* and mainframe.cpu.* metrics.

Emits one round of synthetic data for:
  - mainframe.host  entity (CPC metrics: CPU counts, memory, utilization,
                            environmental, power, status, adapter overview)
  - mainframe.cpu   entity (per-physical-processor utilization + SMT metrics)
  - mainframe.channel entity (I/O channel utilization)

Run via:  uv run python scenario.py
"""
import json
import sys
from pathlib import Path

# Add shared framework to path when run directly
sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

from semconv_mainframe import (
    InMemoryMetricRecorder,
    MainframeHostEmitter,
    MainframePartitionEmitter,
)


def run() -> list[dict]:
    recorder = InMemoryMetricRecorder()

    # mainframe.host.* metrics
    host_emitter = MainframeHostEmitter(recorder.meter_provider)
    host_emitter.emit()

    # mainframe.cpu.* and mainframe.channel.utilization
    # (emitted by MainframePartitionEmitter alongside partition metrics)
    partition_emitter = MainframePartitionEmitter(recorder.meter_provider)
    partition_emitter.emit()

    recorder.flush()
    return recorder.as_dict()


def main() -> None:
    results = run()
    out = Path(__file__).parent / "data.json"
    out.write_text(json.dumps(results, indent=2))
    print(f"Wrote {len(results)} data points → {out}")


if __name__ == "__main__":
    main()
