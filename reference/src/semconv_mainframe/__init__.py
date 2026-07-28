"""
semconv_mainframe — shared reference implementation framework.

Provides:
- Deterministic synthetic telemetry emitters keyed to every mainframe
  metric defined in model/mainframe/ and model/zos/.
- A simple in-process MetricExporter that records each emitted data point
  so scenarios can assert correctness without a real Prometheus/OTLP endpoint.
- Prometheus label-name helpers (OTel attribute key → Prometheus label).
"""
from .emitter import (
    MainframeHostEmitter,
    MainframePartitionEmitter,
    MainframeNetworkEmitter,
    MainframeStorageEmitter,
)
from .recorder import InMemoryMetricRecorder
from .labels import attr_to_label

__all__ = [
    "MainframeHostEmitter",
    "MainframePartitionEmitter",
    "MainframeNetworkEmitter",
    "MainframeStorageEmitter",
    "InMemoryMetricRecorder",
    "attr_to_label",
]
