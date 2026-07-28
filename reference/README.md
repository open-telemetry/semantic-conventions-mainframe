# Semantic Conventions Mainframe — Reference Stack

Validates the [OpenTelemetry Semantic Conventions for Mainframe](../model/) by
running a full local observability stack and emitting synthetic telemetry into it.

## Overview

The reference stack consists of three containers managed by **podman-compose**:

```
weaver registry emit
        │  OTLP gRPC :4317
        ▼
  ┌─────────────┐
  │ OTel        │  prometheus exporter :8889
  │ Collector   │─────────────────────────────┐
  └─────────────┘                             │
                                              ▼
                                       ┌────────────┐
                                       │ Prometheus │  :9090
                                       └────────────┘
                                              │  PromQL
                                              ▼
                                       ┌────────────┐
                                       │  Grafana   │  :3000
                                       │  (6 pre-   │
                                       │   loaded   │
                                       │ dashboards)│
                                       └────────────┘
```

## Prerequisites

- [Podman](https://podman.io/) ≥ 5.0
- [podman-compose](https://github.com/containers/podman-compose) ≥ 1.0  
  Install: `uv tool install podman-compose`  
  Then: `export PATH="$HOME/.local/bin:$PATH"`

## Quick start (one command)

```bash
make demo
```

This starts the stack, waits for the OTel Collector to be ready, sends one
round of synthetic telemetry for all 77 metrics, then prints the Grafana URL.

Open **http://localhost:3000** → Login: `admin` / `admin` → **Dashboards → Mainframe**.

## Step-by-step

```bash
# 1. Start the stack (background)
make stack-up

# 2. Send synthetic telemetry into the running stack
make stack-emit

# 3. Open Grafana
open http://localhost:3000

# 4. Stop the stack when done
make stack-down
```

## Sending telemetry repeatedly

`weaver registry emit` is stateless — run `make stack-emit` as many times as
you like. The OTel Collector's Prometheus exporter holds the last observed
value for 5 minutes, so Grafana panels show data immediately after the first emit.

## Grafana dashboards

All six dashboards in [`../dashboards/mainframe/`](../dashboards/mainframe/) are
provisioned automatically at startup:

| Dashboard | Entities | Grafana UID |
|---|---|---|
| `host.json` | `mainframe.host`, `mainframe.cpu`, `mainframe.channel` | `mainframe-host` |
| `partition_usage.json` | `mainframe.partition` | `mainframe-partition-usage` |
| `nic.json` | `mainframe.partition.nic` | `mainframe-partition-nic` |
| `port.json` | `mainframe.adapter.port` | `mainframe-adapter-port` |
| `crypto.json` | `mainframe.adapter` (utilization) | `mainframe-adapter-utilization` |
| `storage.json` | `mainframe.storage.group`, `mainframe.storage.group.volume`, `mainframe.adapter` (status) | `mainframe-storage` |

## Stack configuration

| File | Purpose |
|---|---|
| `docker-compose.yaml` | Container definitions (image versions from `versions.env`) |
| `otelcol/config.yaml` | OTel Collector: OTLP receiver → Prometheus exporter |
| `prometheus/prometheus.yml` | Prometheus: scrapes collector every 15 s |
| `grafana/provisioning/datasources/prometheus.yaml` | Auto-provisions Prometheus datasource |
| `grafana/provisioning/dashboards/mainframe.yaml` | Auto-loads all mainframe dashboards |

Image versions are pinned in [`../versions.env`](../versions.env) and kept
up-to-date automatically by Renovate.

## Metric coverage

Every signal defined under `model/mainframe/`:

| File | Metrics |
|---|---|
| `metrics_host.yaml` | 17 |
| `metrics_nic.yaml` | 14 |
| `metrics_port.yaml` | 15 |
| `metrics_partition.yaml` | 6 |
| `metrics_partition_usage.yaml` | 11 |
| `metrics_cpu.yaml` | 4 |
| `metrics_channel.yaml` | 1 |
| `metrics_adapter.yaml` | 1 |
| `metrics_storage.yaml` | 8 |
| **Total** | **77** |
