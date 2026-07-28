# Semantic Conventions Mainframe — Reference Implementation

Validates the [OpenTelemetry Semantic Conventions for Mainframe](../model/) against
representative, synthetic telemetry. Each scenario emits a deterministic round of
metrics using the OpenTelemetry Python SDK and captures the data points into a
committed `data.json` file. The coverage table below is generated automatically
from those files.

## Structure

```text
pyproject.toml            # Tooling project (semconv-mainframe-reference)
src/
  semconv_mainframe/
    __init__.py           # Public API
    emitter.py            # Synthetic metric emitters for every semconv metric
    recorder.py           # In-process InMemoryMetricReader wrapper
    labels.py             # OTel attribute key → Prometheus label helpers
    cli.py                # run-scenario CLI entry point
    reports.py            # update-reports entry point
scenarios/
  host/                   # mainframe.host, mainframe.cpu, mainframe.channel
  partition/              # mainframe.partition (all sub-metrics)
  network/                # mainframe.partition.nic, mainframe.adapter.port,
  |                       #   mainframe.adapter.utilization
  storage/                # mainframe.storage.group, mainframe.storage.group.volume,
                          #   mainframe.adapter status
```

## Prerequisites

- Python 3.12+
- `pip` (or `uv` — see [uv docs](https://docs.astral.sh/uv/))

## Running scenarios

### With Python / pip

```bash
# one-time setup
cd reference/
python3 -m venv .venv
.venv/bin/pip install "opentelemetry-api>=1.27.0" "opentelemetry-sdk>=1.27.0"

# run all scenarios
PYTHONPATH=src .venv/bin/python scenarios/host/scenario.py
PYTHONPATH=src .venv/bin/python scenarios/partition/scenario.py
PYTHONPATH=src .venv/bin/python scenarios/network/scenario.py
PYTHONPATH=src .venv/bin/python scenarios/storage/scenario.py
```

### With uv

```bash
cd reference/
uv sync                                  # install deps into .venv
uv run run-scenario host                 # one scenario
uv run run-scenario --all                # all scenarios
uv run run-scenario --all --keep-going   # continue past failures
```

## Regenerating the coverage report

After running scenarios (which writes `scenarios/*/data.json`), refresh this
README:

```bash
# with Python
PYTHONPATH=src .venv/bin/python -c "from semconv_mainframe.reports import main; main()"

# with uv
uv run update-reports
```

## Grafana Dashboards

Grafana dashboards for every entity group live under [`../dashboards/mainframe/`](../dashboards/mainframe/).
Import any dashboard JSON into Grafana (≥ 11.0) pointing at a Prometheus datasource
that scrapes an OpenTelemetry Collector with the prometheus exporter enabled.

| Dashboard file | Entities covered | Grafana UID |
| --- | --- | --- |
| [`host.json`](../dashboards/mainframe/host.json) | `mainframe.host`, `mainframe.cpu`, `mainframe.channel` | `mainframe-host` |
| [`partition_usage.json`](../dashboards/mainframe/partition_usage.json) | `mainframe.partition` | `mainframe-partition-usage` |
| [`nic.json`](../dashboards/mainframe/nic.json) | `mainframe.partition.nic` | `mainframe-partition-nic` |
| [`port.json`](../dashboards/mainframe/port.json) | `mainframe.adapter.port` | `mainframe-adapter-port` |
| [`crypto.json`](../dashboards/mainframe/crypto.json) | `mainframe.adapter` (utilization) | `mainframe-adapter-utilization` |
| [`storage.json`](../dashboards/mainframe/storage.json) | `mainframe.storage.group`, `mainframe.storage.group.volume`, `mainframe.adapter` (status) | `mainframe-storage` |

### Prometheus label names

OTel attribute keys (e.g. `mainframe.cpu.type`) are converted to Prometheus label
names by replacing `.` and `-` with `_` (e.g. `mainframe_cpu_type`).  This matches
the default behaviour of the OpenTelemetry Collector Prometheus exporter and is the
convention used in all dashboard `legendFormat` and `expr` strings.

### Importing a dashboard

1. Open Grafana → **Dashboards** → **Import**.
2. Upload the JSON file or paste its contents.
3. Select your Prometheus datasource when prompted for `DS_PROMETHEUS`.

## Reports

Generated from committed `scenarios/*/data.json` files. Do not edit this section by hand.
Run `uv run update-reports` (or the Python equivalent above) to regenerate.

<!-- status:begin -->
### Metrics

| Metric | Scenarios |
| --- | --- |
| `mainframe.adapter.physical_channel.status.code` | `storage` |
| `mainframe.adapter.port.bandwidth.utilization` | `network` |
| `mainframe.adapter.port.broadcast.packets.received` | `network` |
| `mainframe.adapter.port.broadcast.packets.sent` | `network` |
| `mainframe.adapter.port.bytes.received` | `network` |
| `mainframe.adapter.port.bytes.sent` | `network` |
| `mainframe.adapter.port.data.rate.received` | `network` |
| `mainframe.adapter.port.data.rate.sent` | `network` |
| `mainframe.adapter.port.data.received` | `network` |
| `mainframe.adapter.port.data.sent` | `network` |
| `mainframe.adapter.port.multicast.packets.received` | `network` |
| `mainframe.adapter.port.multicast.packets.sent` | `network` |
| `mainframe.adapter.port.packets.discarded` | `network` |
| `mainframe.adapter.port.packets.dropped` | `network` |
| `mainframe.adapter.port.packets.received` | `network` |
| `mainframe.adapter.port.packets.sent` | `network` |
| `mainframe.adapter.status.code` | `storage` |
| `mainframe.adapter.utilization` | `network` |
| `mainframe.channel.utilization` | `host`, `partition` |
| `mainframe.cpu.smt_mode.utilization` | `host`, `partition` |
| `mainframe.cpu.thread0.utilization` | `host`, `partition` |
| `mainframe.cpu.thread1.utilization` | `host`, `partition` |
| `mainframe.cpu.utilization` | `host`, `partition` |
| `mainframe.host.adapter.utilization` | `host` |
| `mainframe.host.channel.utilization` | `host` |
| `mainframe.host.cpu.active.count` | `host` |
| `mainframe.host.cpu.defective.count` | `host` |
| `mainframe.host.cpu.spare.count` | `host` |
| `mainframe.host.cpu.utilization` | `host` |
| `mainframe.host.dewpoint` | `host` |
| `mainframe.host.heatload` | `host` |
| `mainframe.host.humidity` | `host` |
| `mainframe.host.memory.size` | `host` |
| `mainframe.host.memory.vfm.increment.size` | `host` |
| `mainframe.host.memory.vfm.size` | `host` |
| `mainframe.host.power.cord.usage` | `host` |
| `mainframe.host.power.usage` | `host` |
| `mainframe.host.status.code` | `host` |
| `mainframe.host.status.unacceptable` | `host` |
| `mainframe.host.temperature` | `host` |
| `mainframe.partition.adapter.utilization` | `host`, `partition` |
| `mainframe.partition.capacity.defined` | `host`, `partition` |
| `mainframe.partition.cpu.capped.count` | `host`, `partition` |
| `mainframe.partition.cpu.is_capped` | `host`, `partition` |
| `mainframe.partition.cpu.mode` | `host`, `partition` |
| `mainframe.partition.cpu.reserved.count` | `host`, `partition` |
| `mainframe.partition.cpu.threads_per_processor` | `host`, `partition` |
| `mainframe.partition.cpu.utilization` | `host`, `partition` |
| `mainframe.partition.cpu.virtual.count` | `host`, `partition` |
| `mainframe.partition.cpu.weight.is_capped` | `host`, `partition` |
| `mainframe.partition.cpu.weight.value` | `host`, `partition` |
| `mainframe.partition.memory.size` | `host`, `partition` |
| `mainframe.partition.nic.broadcast.packets.received` | `network` |
| `mainframe.partition.nic.broadcast.packets.sent` | `network` |
| `mainframe.partition.nic.bytes.received` | `network` |
| `mainframe.partition.nic.bytes.sent` | `network` |
| `mainframe.partition.nic.data.rate.received` | `network` |
| `mainframe.partition.nic.data.rate.sent` | `network` |
| `mainframe.partition.nic.data.received` | `network` |
| `mainframe.partition.nic.data.sent` | `network` |
| `mainframe.partition.nic.multicast.packets.received` | `network` |
| `mainframe.partition.nic.multicast.packets.sent` | `network` |
| `mainframe.partition.nic.packets.discarded` | `network` |
| `mainframe.partition.nic.packets.dropped` | `network` |
| `mainframe.partition.nic.packets.received` | `network` |
| `mainframe.partition.nic.packets.sent` | `network` |
| `mainframe.partition.power.usage` | `host`, `partition` |
| `mainframe.partition.status.code` | `host`, `partition` |
| `mainframe.partition.status.unacceptable` | `host`, `partition` |
| `mainframe.partition.wlm.enabled` | `host`, `partition` |
| `mainframe.partition.zvm.paging.rate` | `host`, `partition` |
| `mainframe.storage.group.max.partitions` | `storage` |
| `mainframe.storage.group.shared` | `storage` |
| `mainframe.storage.group.status.code` | `storage` |
| `mainframe.storage.group.volume.cylinders` | `storage` |
| `mainframe.storage.group.volume.size` | `storage` |
| `mainframe.storage.group.volume.status.code` | `storage` |

<!-- status:end -->
