"""
In-process metric recorder.

Collects every metric data point produced by a ``MeterProvider`` so that
reference scenarios can validate emitted values without requiring an external
OTLP collector or Prometheus endpoint.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    InMemoryMetricReader,
    MetricsData,
)


@dataclass
class RecordedPoint:
    """A single observed metric data point."""

    name: str
    """Metric name (e.g. ``mainframe.host.cpu.active.count``)."""

    value: int | float
    """Observed value."""

    attributes: dict[str, Any] = field(default_factory=dict)
    """OTel attribute key/value pairs attached to this data point."""


class InMemoryMetricRecorder:
    """Wraps an :class:`~opentelemetry.sdk.metrics.MeterProvider` and
    captures all emitted data points into :attr:`points`.

    Usage::

        recorder = InMemoryMetricRecorder()
        emitter = MainframeHostEmitter(recorder.meter_provider)
        emitter.emit()
        recorder.flush()

        for pt in recorder.points:
            print(pt.name, pt.value, pt.attributes)
    """

    def __init__(self) -> None:
        self._reader = InMemoryMetricReader()
        self.meter_provider = MeterProvider(metric_readers=[self._reader])
        self.points: list[RecordedPoint] = []

    def flush(self) -> None:
        """Collect all pending data points from the SDK into :attr:`points`."""
        metrics_data: MetricsData = self._reader.get_metrics_data()
        if metrics_data is None:
            return
        for resource_metric in metrics_data.resource_metrics:
            for scope_metric in resource_metric.scope_metrics:
                for metric in scope_metric.metrics:
                    for dp in _data_points(metric.data):
                        self.points.append(
                            RecordedPoint(
                                name=metric.name,
                                value=dp.value,
                                attributes=dict(dp.attributes or {}),
                            )
                        )

    def as_dict(self) -> list[dict]:
        """Return :attr:`points` as plain dicts suitable for JSON serialisation."""
        return [
            {"name": p.name, "value": p.value, "attributes": p.attributes}
            for p in self.points
        ]


def _data_points(data):
    """Yield individual data points regardless of metric data type."""
    # Sum, Gauge, and Histogram all expose .data_points
    if hasattr(data, "data_points"):
        yield from data.data_points
