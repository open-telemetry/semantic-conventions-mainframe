# Reference observability stack

A local OpenTelemetry Collector, Prometheus and Grafana for looking at telemetry
that follows the semantic conventions in [../../model/](../../model/). Image
versions are pinned in [versions.env](../../versions.env).

| Component | Purpose | Address (loopback only) |
| --- | --- | --- |
| OpenTelemetry Collector (contrib) | Receives OTLP, exposes metrics for Prometheus | OTLP gRPC `localhost:4317`, OTLP HTTP `localhost:4318`, scrape `localhost:8889` |
| Prometheus | Scrapes the collector | `http://localhost:9090` |
| Grafana | Prometheus data source provisioned, anonymous access | `http://localhost:3000` |

## Usage

Requires Podman with `podman-compose`, or Docker with `docker compose`.

```bash
make stack-up     # start the stack
make stack-emit   # send one synthetic data point per signal in the registry (Weaver)
make stack-down   # stop and remove the containers
```

Any OTLP source can send to `localhost:4317` (gRPC) or `localhost:4318` (HTTP).

## Metric names in Prometheus

The collector's Prometheus exporter uses `translation_strategy: NoTranslation`,
so metric names and attribute keys appear exactly as defined in the registry,
and each metric shows the namespace it comes from: `mainframe.*` and
`virtualization.*` from this repository, `system.*`, `hw.*` and `container.*`
from upstream OpenTelemetry. Dotted names must be quoted in PromQL:

```promql
{"mainframe.cpu.utilization", "mainframe.cpu.name"="AAP0"}
```

This needs a UTF-8 capable Prometheus (3.0 or later, as pinned). The exporter
negotiates the format: Prometheus 3 receives the dotted names, while a plain
`curl localhost:8889/metrics` shows the underscore-escaped legacy form
(`mainframe_cpu_utilization`).

## Forwarding to another backend

`otelcol-config.yaml` defines an `otlp/backend` exporter that is not part of any
pipeline by default. Set `TARGET_OTLP_ENDPOINT` (and `TARGET_OTLP_KEY` if the
backend expects an `x-api-key` header) and add `otlp/backend` to the pipelines.
TLS with certificate verification is on by default; set
`TARGET_OTLP_INSECURE=true` only for a local plaintext receiver.
