# Semantic Conventions Mainframe Reference Implementations

Validates OpenTelemetry Semantic Conventions for Mainframe <!-- TODO [OpenTelemetry Semantic Conventions for Mainframe](https://opentelemetry.io/docs/specs/semconv/mainframe/) -->
against representative, synthetic telemetry, showing which entities, metrics
and attributes each scenario of the mainframe, its software and infrastructure
supports.

Each scenario under `scenarios/<scenario>/` contains a small reference
implementation (`scenario.py`) that emits OpenTelemetry telemetry, plus a
`conformance.yaml` saying how to run it and what it must produce. The tooling
runs each scenario against [OTel Weaver](https://github.com/open-telemetry/weaver)
live-check, validates the captured telemetry against the semantic conventions
in [../model/](../model/), and writes the per-scenario results to
`scenarios/<scenario>/data.json`, which feed the status reports below.

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to run scenarios and add new ones.

## Reports

Generated from committed `scenarios/*/data.json` files. Do not edit this section by hand.
Run `uv run update-reports` (or `make generate-reference-reports` from the
repository root) to regenerate. Every signal [../model/](../model/) declares is
listed; metric refinements are listed by the entities they are refined for.

<!-- status:begin -->
### Entities

| Entity | Libraries |
| --- | --- |
| host | (none) |
| mainframe.adapter | (none) |
| mainframe.adapter.port | (none) |
| mainframe.channel | (none) |
| mainframe.cpu | (none) |
| mainframe.partition.nic | (none) |
| mainframe.storage.group | (none) |
| mainframe.storage.group.volume | (none) |
| virtualization.cluster | (none) |
| virtualization.hypervisor | (none) |
| virtualization.partition | (none) |
| virtualization.platform | (none) |
| virtualization.resource_pool | (none) |
| virtualization.storage_pool | (none) |
| virtualization.vm | (none) |
| virtualization.vswitch | (none) |
| zos.software | (none) |

### Metrics

| Metric | Libraries |
| --- | --- |
| hw.energy on virtualization.platform | (none) |
| hw.errors on virtualization.platform | (none) |
| hw.host.ambient_temperature on virtualization.platform | (none) |
| hw.host.energy on virtualization.platform | (none) |
| hw.host.heating_margin on virtualization.platform | (none) |
| hw.host.power on virtualization.platform | (none) |
| hw.network.bandwidth.limit on virtualization.vswitch | (none) |
| hw.network.bandwidth.utilization on virtualization.vswitch | (none) |
| hw.network.io on virtualization.vswitch | (none) |
| hw.network.packets on virtualization.vswitch | (none) |
| hw.network.up on virtualization.vswitch | (none) |
| hw.power on virtualization.platform | (none) |
| hw.status on virtualization.platform | (none) |
| hw.temperature on virtualization.platform | (none) |
| mainframe.adapter.physical_channel.status.code | (none) |
| mainframe.adapter.status.code | (none) |
| mainframe.adapter.utilization | (none) |
| mainframe.channel.utilization | (none) |
| mainframe.cpu.smt_mode.utilization | (none) |
| mainframe.cpu.thread0.utilization | (none) |
| mainframe.cpu.thread1.utilization | (none) |
| mainframe.cpu.utilization | (none) |
| mainframe.host.adapter.utilization | (none) |
| mainframe.host.channel.utilization | (none) |
| mainframe.host.cpu.active.count | (none) |
| mainframe.host.cpu.defective.count | (none) |
| mainframe.host.cpu.spare.count | (none) |
| mainframe.host.cpu.utilization | (none) |
| mainframe.host.dewpoint | (none) |
| mainframe.host.heatload | (none) |
| mainframe.host.humidity | (none) |
| mainframe.host.memory.size | (none) |
| mainframe.host.memory.vfm.increment.size | (none) |
| mainframe.host.memory.vfm.size | (none) |
| mainframe.host.power.cord.usage | (none) |
| mainframe.host.power.usage | (none) |
| mainframe.host.status.unacceptable | (none) |
| mainframe.partition.adapter.utilization | (none) |
| mainframe.partition.capacity.defined | (none) |
| mainframe.partition.cpu.capped.count | (none) |
| mainframe.partition.cpu.mode | (none) |
| mainframe.partition.cpu.reserved.count | (none) |
| mainframe.partition.cpu.threads_per_processor | (none) |
| mainframe.partition.cpu.utilization | (none) |
| mainframe.partition.cpu.virtual.count | (none) |
| mainframe.partition.memory.size | (none) |
| mainframe.partition.power.usage | (none) |
| mainframe.partition.status.code | (none) |
| mainframe.partition.status.unacceptable | (none) |
| mainframe.partition.wlm.enabled | (none) |
| mainframe.storage.group.capacity | (none) |
| mainframe.storage.group.usage | (none) |
| mainframe.storage.group.volume.capacity | (none) |
| system.cpu.time on virtualization.partition, virtualization.platform, virtualization.vm | (none) |
| system.cpu.utilization on virtualization.partition, virtualization.platform | (none) |
| system.cpu.utilization on virtualization.partition, virtualization.platform, virtualization.vm | (none) |
| system.disk.limit on virtualization.platform, virtualization.storage_pool | (none) |
| system.filesystem.usage on virtualization.vm | (none) |
| system.filesystem.utilization on virtualization.vm | (none) |
| system.memory.usage on virtualization.vm | (none) |
| system.memory.utilization on virtualization.vm | (none) |
| system.network.errors on mainframe.partition.nic | (none) |
| system.network.errors on mainframe.adapter.port | (none) |
| system.network.errors on virtualization.partition, virtualization.vm, virtualization.vswitch | (none) |
| system.network.io on mainframe.partition.nic | (none) |
| system.network.io on mainframe.adapter.port | (none) |
| system.network.io on virtualization.partition, virtualization.vm, virtualization.vswitch | (none) |
| system.network.packet.count on mainframe.partition.nic | (none) |
| system.network.packet.count on mainframe.adapter.port | (none) |
| system.network.packet.count on virtualization.partition, virtualization.vm, virtualization.vswitch | (none) |
| system.network.packet.dropped on mainframe.partition.nic | (none) |
| system.network.packet.dropped on mainframe.adapter.port | (none) |
| system.network.packet.dropped on virtualization.partition, virtualization.vm, virtualization.vswitch | (none) |
| system.paging.faults on virtualization.vm | (none) |
| system.uptime on virtualization.vm | (none) |
| virtualization.cluster.host.count | (none) |
| virtualization.cluster.vm.count | (none) |
| virtualization.hypervisor.memory.overcommit_ratio | (none) |
| virtualization.partition.cpu.count | (none) |
| virtualization.partition.cpu.is_capped | (none) |
| virtualization.partition.cpu.time | (none) |
| virtualization.partition.cpu.utilization | (none) |
| virtualization.partition.cpu.weight on virtualization.partition | (none) |
| virtualization.partition.cpu.weight | (none) |
| virtualization.partition.memory.size | (none) |
| virtualization.partition.state.code | (none) |
| virtualization.platform.cpu.utilization | (none) |
| virtualization.platform.memory.total | (none) |
| virtualization.platform.memory.used | (none) |
| virtualization.platform.partition.count | (none) |
| virtualization.platform.power.usage | (none) |
| virtualization.platform.vm.count | (none) |
| virtualization.resource_pool.cpu.allocated | (none) |
| virtualization.resource_pool.memory.allocated | (none) |
| virtualization.storage_pool.available | (none) |
| virtualization.storage_pool.used | (none) |
| virtualization.vm.cpu.count | (none) |
| virtualization.vm.cpu.ready_time | (none) |
| virtualization.vm.cpu.steal_time | (none) |
| virtualization.vm.cpu.utilization | (none) |
| virtualization.vm.disk.errors | (none) |
| virtualization.vm.disk.io | (none) |
| virtualization.vm.disk.latency.time | (none) |
| virtualization.vm.disk.operations | (none) |
| virtualization.vm.memory.allocated | (none) |
| virtualization.vm.memory.balloon | (none) |
| virtualization.vm.memory.rss | (none) |
| virtualization.vm.memory.swapped | (none) |
| virtualization.vm.memory.used | (none) |
| virtualization.vm.network.io | (none) |
| virtualization.vm.power.state | (none) |
<!-- status:end -->
