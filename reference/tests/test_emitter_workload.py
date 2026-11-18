"""The emitter's workload engine and OTLP output, against small fixtures rather than model/."""

from __future__ import annotations

import random
import threading
from concurrent import futures
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import grpc
import pytest
from opentelemetry.proto.collector.metrics.v1 import metrics_service_pb2, metrics_service_pb2_grpc

from semconv_mainframe.emitter import Emitter, MetricDef, Registry, Workload, WorkloadError, export, load_topology
from semconv_mainframe.emitter.registry import AttributeDef
from semconv_mainframe.emitter.workload import make_generator

FIXTURES = Path(__file__).parent / "fixtures"
NOW = 1_700_000_000 * 10**9


@pytest.fixture(scope="module")
def registry() -> Registry:
    return Registry.load(FIXTURES / "resolved_registry.yaml")


@pytest.fixture
def emitter(registry: Registry) -> Emitter:
    topology = load_topology(FIXTURES / "topology.yaml", registry)
    return Emitter(registry, topology, Workload.load(FIXTURES / "workload.yaml", seed=1))


def _points(request: metrics_service_pb2.ExportMetricsServiceRequest) -> dict[tuple[str, str], list]:
    """(resource identity value, metric name) -> data points."""
    points = {}
    for resource in request.resource_metrics:
        attrs = {kv.key: kv.value for kv in resource.resource.attributes}
        owner = (attrs.get("mainframe.cpu.name") or attrs["virtualization.platform.id"]).string_value
        for metric in resource.scope_metrics[0].metrics:
            points[owner, metric.name] = list(metric.gauge.data_points or metric.sum.data_points)
    return points


def test_series_come_from_rule_resource_and_required_fallbacks(emitter: Emitter) -> None:
    series = {(node.identity_key[1], name): [s.attributes for s in s_list] for node, name, s_list in emitter.plan}
    assert series["3931-45A01", "mainframe.host.cpu.active.count"] == [
        {"mainframe.cpu.type": "cp"},
        {"mainframe.cpu.type": "ifl"},
    ]
    # hw.id is required and nothing sets it: the registry example; hw.name from the rule.
    assert series["3931-45A01", "hw.host.power"] == [{"hw.id": "cpc", "hw.name": "CPC power"}]
    # mainframe.cpu.type is required: first enum member; cpu.mode: one series per rule value.
    assert series["3931-45A01", "system.cpu.utilization"] == [
        {"cpu.mode": "user", "mainframe.cpu.type": "cp"},
        {"cpu.mode": "system", "mainframe.cpu.type": "cp"},
    ]
    assert series["IFL00", "mainframe.cpu.utilization"] == [{"mainframe.cpu.name": "IFL00"}]
    assert emitter.emitted_metric_ids() == set(Registry.load(FIXTURES / "resolved_registry.yaml").metrics)


def test_request_shape(emitter: Emitter, registry: Registry) -> None:
    request = emitter.request(NOW, 10.0)
    assert len(request.resource_metrics) == 3
    resource = request.resource_metrics[0]
    assert resource.schema_url == registry.schema_url
    assert resource.scope_metrics[0].scope.name == "semconv_mainframe.emitter"
    metrics = {m.name: m for m in resource.scope_metrics[0].metrics}
    count = metrics["mainframe.host.cpu.active.count"]
    assert count.unit == "{cpu}" and not count.sum.is_monotonic
    assert [p.as_int for p in count.sum.data_points] == [12, 12]
    assert count.sum.data_points[0].start_time_unix_nano == emitter.start_ns
    power = metrics["hw.host.power"].gauge.data_points[0]
    assert power.WhichOneof("value") == "as_double" and 4500 <= power.as_double <= 8200
    points = _points(request)
    assert 0.0 <= points["IFL00", "mainframe.cpu.utilization"][0].as_double <= 1.0
    assert len(points["CP00", "system.cpu.utilization"]) == 2


def test_definitions_sharing_a_wire_name_on_one_entity_are_merged(registry: Registry) -> None:
    cpu = registry.entities["mainframe.cpu"]
    name_attr = AttributeDef("mainframe.cpu.name", "string", "required")
    mode = AttributeDef("cpu.mode", "enum", "required", members=("user",))
    base = MetricDef("x.weight", "x.weight", "gauge", "1", (cpu.type,), {"mainframe.cpu.name": name_attr})
    refined = MetricDef(
        "refinement.x.weight", "x.weight", "gauge", "1", (cpu.type,), {**base.attributes, "cpu.mode": mode}
    )
    merged = Registry(metrics={m.id: m for m in (base, refined)}, entities=registry.entities)
    topology = load_topology(FIXTURES / "topology.yaml", merged)
    emitter = Emitter(merged, topology, Workload([{"unit": "1", "generator": {"function": "constant", "value": 1}}]))
    weight = next(s for node, name, s in emitter.plan if name == "x.weight")
    assert [s.attributes for s in weight] == [
        {"cpu.mode": "user", "mainframe.cpu.name": "CP00"},
        {"mainframe.cpu.name": "CP00"},
    ]
    assert emitter.emitted_metric_ids() == {"x.weight", "refinement.x.weight"}


def test_a_rule_in_another_unit_than_the_model_fails(registry: Registry) -> None:
    # P13: values in GiBy for a metric declared in By must not pass silently.
    workload = Workload([{"metric": "hw.host.power", "unit": "kW", "generator": {"function": "constant", "value": 6}}])
    with pytest.raises(WorkloadError, match="declared in 'W'"):
        workload.rule_for(registry.metrics["refinement.virtualization.hw.host.power"], "virtualization.platform")


def test_unmatched_metrics_and_non_monotonic_counters_fail(registry: Registry) -> None:
    topology = load_topology(FIXTURES / "topology.yaml", registry)
    with pytest.raises(WorkloadError, match="no rule matches"):
        Emitter(registry, topology, Workload([]))
    counter = MetricDef("c", "c", "counter", "By", ("mainframe.cpu",), {})
    workload = Workload([{"unit": "By", "generator": {"function": "gaussian", "mean": 1}}])
    with pytest.raises(WorkloadError, match="needs a counter generator"):
        workload.series(counter, topology[0].children[0])


def test_generators() -> None:
    rng = random.Random(0)
    gaussian = make_generator({"function": "gaussian", "mean": 0.5, "stddev": 5, "min": 0, "max": 1}, rng)
    assert all(0 <= gaussian.value(t, 1) <= 1 for t in range(100))
    diurnal = make_generator({"function": "diurnal", "base": 50, "amplitude": 30, "period": 100}, rng)
    assert {round(diurnal.value(t, 1)) for t in (25, 75)} == {80, 20}
    counter = make_generator(
        {"function": "counter", "start": 100, "rate": {"function": "gaussian", "mean": 2, "stddev": 5}}, rng
    )
    totals = [counter.value(t, 10) for t in range(50)]
    assert totals[0] >= 100 and totals == sorted(totals)
    spikes = make_generator({"function": "spikes", "baseline": 0.001, "probability": 0.5, "magnitude": 1}, rng)
    assert min(spikes.value(t, 1) for t in range(50)) == 0.001
    with pytest.raises(WorkloadError, match="unknown generator"):
        make_generator({"function": "pareto"}, rng)


def test_export_over_grpc(emitter: Emitter) -> None:
    received = []

    class Service(metrics_service_pb2_grpc.MetricsServiceServicer):
        def Export(self, request, context):
            received.append(request)
            return metrics_service_pb2.ExportMetricsServiceResponse()

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=1))
    metrics_service_pb2_grpc.add_MetricsServiceServicer_to_server(Service(), server)
    port = server.add_insecure_port("127.0.0.1:0")
    server.start()
    try:
        export(emitter.request(NOW, 10.0), f"http://127.0.0.1:{port}", "grpc")
    finally:
        server.stop(None)
    assert len(received[0].resource_metrics) == 3


def test_export_over_http_protobuf(emitter: Emitter) -> None:
    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            body = self.rfile.read(int(self.headers["Content-Length"]))
            received.append((self.path, self.headers["Content-Type"], body))
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args: object) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.handle_request, daemon=True).start()
    export(emitter.request(NOW, 10.0), f"http://127.0.0.1:{server.server_port}/", "http/protobuf")
    server.server_close()
    path, content_type, body = received[0]
    assert (path, content_type) == ("/v1/metrics", "application/x-protobuf")
    assert len(metrics_service_pb2.ExportMetricsServiceRequest.FromString(body).resource_metrics) == 3
