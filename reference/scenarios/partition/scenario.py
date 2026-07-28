"""
Partition scenario — exercises all mainframe.partition.* metrics.

Emits one round of synthetic data for:
  - mainframe.partition  entity (CPU counts/capping/weights, utilization,
                                 memory, status, WLM, DPM mode/threads)

Run via:  uv run python scenario.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

from semconv_mainframe import InMemoryMetricRecorder, MainframePartitionEmitter


def run() -> list[dict]:
    recorder = InMemoryMetricRecorder()
    emitter = MainframePartitionEmitter(recorder.meter_provider)
    emitter.emit()
    recorder.flush()
    return recorder.as_dict()


def main() -> None:
    results = run()
    out = Path(__file__).parent / "data.json"
    out.write_text(json.dumps(results, indent=2))
    print(f"Wrote {len(results)} data points → {out}")


if __name__ == "__main__":
    main()
