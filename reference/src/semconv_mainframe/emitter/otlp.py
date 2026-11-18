"""Turning the planned series into OTLP and sending it.

One resource per topology node, carrying that entity's attributes; one metric
per wire name on it. When several definitions share a wire name on one entity
-- a base metric and its refinement, or two refinements -- their series are
merged into that metric, so each definition's attribute set is emitted.

Export follows the standard SDK environment: ``OTEL_EXPORTER_OTLP_ENDPOINT``
and ``OTEL_EXPORTER_OTLP_PROTOCOL`` (``grpc``, the default, or
``http/protobuf``). Weaver live-check only receives gRPC.
"""

from __future__ import annotations

import os
import time
import urllib.request
from collections.abc import Iterable

import grpc
from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import ExportMetricsServiceRequest
from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2_grpc import MetricsServiceStub
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, ArrayValue, InstrumentationScope, KeyValue
from opentelemetry.proto.metrics.v1.metrics_pb2 import (
    AggregationTemporality,
    Gauge,
    Metric,
    NumberDataPoint,
    ScopeMetrics,
    Sum,
)
from opentelemetry.proto.resource.v1.resource_pb2 import Resource

from semconv_mainframe.emitter.registry import AttributeValue, Registry
from semconv_mainframe.emitter.topology import Node
from semconv_mainframe.emitter.workload import Series, Workload, WorkloadError

SCOPE = InstrumentationScope(name="semconv_mainframe.emitter", version="0.1.0")
EXPORT_TIMEOUT_SECONDS = 30


def _any_value(value: AttributeValue) -> AnyValue:
    if isinstance(value, bool):
        return AnyValue(bool_value=value)
    if isinstance(value, int):
        return AnyValue(int_value=value)
    if isinstance(value, float):
        return AnyValue(double_value=value)
    if isinstance(value, list):
        return AnyValue(array_value=ArrayValue(values=[_any_value(v) for v in value]))
    return AnyValue(string_value=str(value))


def _key_values(attributes: dict[str, AttributeValue]) -> list[KeyValue]:
    return [KeyValue(key=k, value=_any_value(v)) for k, v in sorted(attributes.items())]


class Emitter:
    """Every metric the registry associates with every node of a topology."""

    def __init__(self, registry: Registry, roots: Iterable[Node], workload: Workload) -> None:
        self.registry = registry
        self.start_ns = time.time_ns()
        # (node, wire name) -> series, in topology then name order.
        self.plan: list[tuple[Node, str, list[Series]]] = []
        for node in (n for root in roots for n in root.walk()):
            by_name: dict[str, list[Series]] = {}
            for metric in registry.metrics_for(node.entity_type):
                if metric.instrument not in ("gauge", "counter", "updowncounter"):
                    raise WorkloadError(f"{metric.id}: {metric.instrument} instruments are not supported")
                merged = by_name.setdefault(metric.name, [])
                if merged and (merged[0].metric.instrument, merged[0].metric.unit) != (metric.instrument, metric.unit):
                    raise WorkloadError(f"{metric.id} disagrees with {merged[0].metric.id} on instrument or unit")
                for series in workload.series(metric, node):
                    if all(series.attributes != s.attributes for s in merged):
                        merged.append(series)
            self.plan += [(node, name, series) for name, series in sorted(by_name.items())]

    def emitted_metric_ids(self) -> set[str]:
        """The definitions at least one planned series emits."""
        return {s.metric.id for _, _, series in self.plan for s in series}

    def request(self, now_ns: int, dt: float) -> ExportMetricsServiceRequest:
        """One collection cycle: every series advanced by ``dt`` seconds, sampled at ``now_ns``."""
        request = ExportMetricsServiceRequest()
        current: tuple[Node, ScopeMetrics] | None = None
        for node, name, series in self.plan:
            if current is None or current[0] is not node:
                resource = request.resource_metrics.add(
                    resource=Resource(attributes=_key_values(node.attributes)), schema_url=self.registry.schema_url
                )
                current = (node, resource.scope_metrics.add(scope=SCOPE, schema_url=self.registry.schema_url))
            definition = series[0].metric
            points = []
            for s in series:
                value = s.generator.value(now_ns / 1e9, dt)
                point = NumberDataPoint(attributes=_key_values(s.attributes), time_unix_nano=now_ns)
                if definition.instrument != "gauge":
                    point.start_time_unix_nano = self.start_ns
                if definition.value_type == "int":
                    point.as_int = round(value)
                else:
                    point.as_double = value
                points.append(point)
            metric = Metric(name=name, unit=definition.unit)
            if definition.instrument == "gauge":
                metric.gauge.CopyFrom(Gauge(data_points=points))
            else:
                metric.sum.CopyFrom(
                    Sum(
                        data_points=points,
                        aggregation_temporality=AggregationTemporality.AGGREGATION_TEMPORALITY_CUMULATIVE,
                        is_monotonic=definition.instrument == "counter",
                    )
                )
            current[1].metrics.append(metric)
        return request


def export(request: ExportMetricsServiceRequest, endpoint: str | None = None, protocol: str | None = None) -> None:
    """Send ``request``; raise when the receiver does not accept it."""
    protocol = protocol or os.environ.get("OTEL_EXPORTER_OTLP_PROTOCOL", "grpc")
    default = "http://localhost:4318" if protocol == "http/protobuf" else "http://localhost:4317"
    endpoint = (endpoint or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT") or default).rstrip("/")
    if protocol == "grpc":
        target = endpoint.split("://", 1)[-1]
        with grpc.insecure_channel(target) as channel:
            MetricsServiceStub(channel).Export(request, timeout=EXPORT_TIMEOUT_SECONDS, wait_for_ready=True)
    elif protocol == "http/protobuf":
        post = urllib.request.Request(
            f"{endpoint}/v1/metrics",
            data=request.SerializeToString(),
            headers={"Content-Type": "application/x-protobuf"},
            method="POST",
        )
        with urllib.request.urlopen(post, timeout=EXPORT_TIMEOUT_SECONDS):
            pass
    else:
        raise ValueError(f"unsupported OTLP protocol {protocol!r}; use grpc or http/protobuf")
