# Mainframe Scenario

This scenario demonstrates all `mainframe.*` entity types and their associated
metrics as defined in `model/mainframe/`.

## Entities demonstrated

| Entity type | Topology nodes | Key metrics |
| --- | --- | --- |
| `virtualization.platform` (CPC) | `CPC01` | `mainframe.host.cpu.active.count`, `mainframe.host.humidity`, `mainframe.host.heatload`, `system.cpu.utilization` |
| `mainframe.cpu` | `CP0`, `IFL0`, `zIIP0`, `ICF0`, `AAP0`, `SAP0` | `mainframe.cpu.utilization`, `mainframe.cpu.smt_mode.utilization`, `mainframe.cpu.thread0.utilization`, `mainframe.cpu.thread1.utilization` |
| `mainframe.channel` | `0.1A`, `0.2A`, `0.3A`, `0.4A` | `mainframe.channel.utilization` |
| `mainframe.adapter` | `CRYPTO01`, `FLASH01`, `NET-OSA01`, `STOR-FCP01` | `mainframe.adapter.utilization`, `mainframe.adapter.status.code` |
| `mainframe.adapter.port` | `NET-OSA01/Port0 rx`, `NET-OSA01/Port0 tx` | `system.network.io`, `system.network.packet.count`, `system.network.errors` |
| `mainframe.partition` (`virtualization.partition`) | `PROD01`, `ZVM01` | `virtualization.partition.cpu.utilization`, `virtualization.partition.cpu.weight`, `mainframe.partition.cpu.reserved.count` |
| `mainframe.partition.nic` | `PROD01-NIC0 rx/tx`, `ZVM01-NIC0 rx/tx` | `system.network.io`, `system.network.packet.count`, `system.network.packet.dropped` |
| `mainframe.storage.group` | `sg-fcp-prod`, `sg-fc-eckd`, `sg-nvme-test` | `mainframe.storage.group.capacity`, `mainframe.storage.group.usage` |
| `mainframe.storage.group.volume` | 8 volumes across 3 groups | `mainframe.storage.group.volume.capacity` |

## Running this scenario

```bash
cd reference

# Emit mainframe signals only (one cycle)
python otel_semconv_sim.py --config simulator_config.yaml --once \
    --namespaces "mainframe.*,virtualization.*"

# Run the full automated test suite
uv run pytest tests/test_simulator.py -v
```

## Topology source

The complete topology configuration for this scenario is in
[`simulator_config.yaml`](../../simulator_config.yaml). The entity nodes under
`spec.topology.entities[]` define the resource attributes for each entity
instance. Workload generators are in [`workload_profile.yaml`](../../workload_profile.yaml).

## HMC API mapping

For the IBM Z HMC Web Services API source for each metric, see
[`docs/hmc-api-signal-mapping.md`](../../../docs/hmc-api-signal-mapping.md).
