# Semantic Conventions Mainframe — Reference Stack

Validates the [OpenTelemetry Semantic Conventions for Mainframe](../model/) by
running a full local observability stack and emitting synthetic IBM Z telemetry
into it.

---

## Components

| File | Purpose |
| --- | --- |
| `demo.sh` | Convenience wrapper — `start`, `stop`, `emit-once`, `emit-continuous`, `weaver-emit` |
| `docker-compose.yaml` | Starts OTel Collector → Prometheus → Grafana |
| `otelcol-config.yaml` | OTel Collector pipeline: OTLP in → Prometheus scrape endpoint |
| `prometheus.yml` | Prometheus scrape config (scrapes collector at port 8889) |
| `grafana-datasources.yaml` | Grafana provisioning: Prometheus data source |
| `otel_semconv_sim.py` | Domain-agnostic, model-driven OTLP telemetry simulator |
| `simulator_config.yaml` | Topology + registry paths + OTLP export destination |
| `workload_profile.yaml` | Declarative math rules mapping metric patterns to signal generators |

---

## Quick Start

### Prerequisites

- Python ≥ 3.12 with `pyyaml` installed (the simulator uses the stdlib `urllib` for HTTP):
  ```bash
  pip install pyyaml
  ```
- Podman ≥ 4 with `podman-compose`, **or** Docker with `docker compose` v2.

### 1. Start the observability stack

```bash
cd reference/
./demo.sh start
```

Services started:
- Grafana Explore: <http://localhost:3000/explore>
- Prometheus Targets: <http://localhost:9090/targets>
- OTLP HTTP Endpoint: <http://localhost:4318>
- OTLP gRPC Endpoint: `localhost:4317`

### 2. Emit a single verification batch

```bash
./demo.sh emit-once
```

### 3. Run continuous telemetry (every 10 s)

```bash
./demo.sh emit-continuous 10
```

### 4. Stop the stack

```bash
./demo.sh stop
```

---

## Running the simulator directly

```bash
# Single batch
python3 otel_semconv_sim.py --config simulator_config.yaml --once

# Continuous (10 s interval)
python3 otel_semconv_sim.py --config simulator_config.yaml --interval 10

# Namespace slice
python3 otel_semconv_sim.py --config simulator_config.yaml \
  --namespaces "mainframe.cpu.*,mainframe.channel.*"
```

---

## How it works

The simulator is **100% domain-agnostic**. At startup it:

1. Reads `simulator_config.yaml` → resolves registry paths relative to this file
2. Parses all `definition/2` YAML files under `../model/mainframe/` and
   `../model/virtualization/`
3. Builds an entity topology graph from `topology:` in the config
4. Evaluates `workload_profile.yaml` rules (pattern / unit / type matching) to
   bind a math generator to every discovered metric
5. Emits OTLP JSON over HTTP to the configured endpoint

The workload profile drives four generator functions:
`gaussian`, `diurnal`, `counter_accumulator`, `pareto_spikes`.

---

## Modifying the topology

Edit `simulator_config.yaml` → `spec.topology.entities[]`.
The entity `type:` values must match types registered in `../model/`.
