# Reference Scenarios

This directory contains demonstration scenarios for the semantic conventions
defined in `model/`. Scenarios show how each entity type and its associated
metrics appear as OTel OTLP payloads in a realistic topology.

## Approved scenario mechanism

This repository uses the **domain-agnostic model-driven simulator**
(`reference/otel_semconv_sim.py`) as the approved scenario mechanism in place
of hand-authored `scenario.py` files. The simulator reads the model at runtime
and generates OTLP telemetry for every entity type declared in
`simulator_config.yaml`.

CONTRIBUTING.md section 9 ("Simulator and test requirements") documents the
mandatory coverage requirements:

- **Topology** (`simulator_config.yaml`) — one or more nodes per entity type
- **Workload rules** (`workload_profile.yaml`) — signal generators per metric pattern
- **Pytest coverage** (`tests/test_simulator.py`) — automated checks that every
  entity type emits at least one signal with all required attributes

## Running a scenario

```bash
cd reference

# Emit one cycle of all mainframe + virtualization signals
python otel_semconv_sim.py --config simulator_config.yaml --once

# Emit only mainframe namespace signals
python otel_semconv_sim.py --config simulator_config.yaml --once \
    --namespaces "mainframe.*"

# Start the full reference stack and emit continuously
./demo.sh start
python otel_semconv_sim.py --config simulator_config.yaml
```

## Namespace scenarios

| Namespace | Entities covered | Simulator topology section |
| --- | --- | --- |
| [mainframe](mainframe/README.md) | `virtualization.platform` (CPC), `mainframe.cpu`, `mainframe.channel`, `mainframe.adapter`, `mainframe.adapter.port`, `mainframe.partition.nic`, `mainframe.storage.group`, `mainframe.storage.group.volume` | `spec.topology.entities[]` in `simulator_config.yaml` |
| virtualization | `virtualization.platform`, `virtualization.partition`, `virtualization.hypervisor`, `virtualization.vm`, `virtualization.vswitch`, `virtualization.storage_pool`, `virtualization.resource_pool`, `virtualization.cluster` | same |
