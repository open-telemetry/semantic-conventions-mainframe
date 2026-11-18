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

## Scenarios

| Scenario | What it stands for |
| --- | --- |
| [hmc](scenarios/hmc/) | An IBM Z HMC-based collector observing one CPC: processors, channels, adapters and ports, a z/OS and a z/VM partition, z/VM guests and VSWITCH, DPM storage groups, processor and storage pools. Every metric the model associates with these entities is emitted, including the `system.*` and `hw.*` refinements. |

The HMC scenario's values are synthetic, produced by a model-driven emitter
([src/semconv_mainframe/emitter/](src/semconv_mainframe/emitter/)) from a
topology and a workload profile; the resources, metric names, units,
instruments and attributes are the ones the conventions prescribe.

## Demo

[demo.sh](demo.sh) sends the HMC scenario's telemetry to the local reference
stack (OpenTelemetry Collector, Prometheus and Grafana, see
[stack/README.md](stack/README.md)), to look at the conventions in a backend:

```bash
reference/demo.sh start               # fetch the upstream registry if needed, start the stack
reference/demo.sh emit-once           # one collection: 35 resources, every metric of the scenario
reference/demo.sh emit-continuous 60  # a collection every 60 s until Ctrl-C
reference/demo.sh stop
```

Then query Prometheus at `http://localhost:9090` or Grafana at
`http://localhost:3000`, for example `{"hw.host.power"}` or
`{"mainframe.cpu.utilization", "mainframe.cpu.name"="IFL00"}`.

## Reports

Generated from committed `scenarios/*/data.json` files. Do not edit this section by hand.
Run `uv run update-reports` (or `make generate-reference-reports` from the
repository root) to regenerate. Every signal [../model/](../model/) declares is
listed; metric refinements are listed by the entities they are refined for.

<!-- status:begin -->
### Entities

| Entity | Libraries |
| --- | --- |
| [host](reports/host-entity.md) | hmc |
| [mainframe.adapter](reports/mainframe-adapter-entity.md) | hmc |
| [mainframe.adapter.port](reports/mainframe-adapter-port-entity.md) | hmc |
| [mainframe.channel](reports/mainframe-channel-entity.md) | hmc |
| [mainframe.cpu](reports/mainframe-cpu-entity.md) | hmc |
| [mainframe.partition.nic](reports/mainframe-partition-nic-entity.md) | hmc |
| [mainframe.storage.group](reports/mainframe-storage-group-entity.md) | hmc |
| [mainframe.storage.group.volume](reports/mainframe-storage-group-volume-entity.md) | hmc |
| [virtualization.cluster](reports/virtualization-cluster-entity.md) | hmc |
| [virtualization.hypervisor](reports/virtualization-hypervisor-entity.md) | hmc |
| [virtualization.partition](reports/virtualization-partition-entity.md) | hmc |
| [virtualization.platform](reports/virtualization-platform-entity.md) | hmc |
| [virtualization.resource_pool](reports/virtualization-resource-pool-entity.md) | hmc |
| [virtualization.storage_pool](reports/virtualization-storage-pool-entity.md) | hmc |
| [virtualization.vm](reports/virtualization-vm-entity.md) | hmc |
| [virtualization.vswitch](reports/virtualization-vswitch-entity.md) | hmc |
| zos.software | (none) |

### Metrics

| Metric | Libraries |
| --- | --- |
| [hw.energy on virtualization.platform](reports/refinement-virtualization-hw-energy-metric.md) | hmc |
| [hw.errors on virtualization.platform](reports/refinement-virtualization-hw-errors-metric.md) | hmc |
| [hw.host.ambient_temperature on virtualization.platform](reports/refinement-virtualization-hw-host-ambient-temperature-metric.md) | hmc |
| [hw.host.energy on virtualization.platform](reports/refinement-virtualization-hw-host-energy-metric.md) | hmc |
| [hw.host.heating_margin on virtualization.platform](reports/refinement-virtualization-hw-host-heating-margin-metric.md) | hmc |
| [hw.host.power on virtualization.platform](reports/refinement-virtualization-hw-host-power-metric.md) | hmc |
| [hw.network.bandwidth.limit on virtualization.vswitch](reports/refinement-virtualization-hw-network-bandwidth-limit-metric.md) | hmc |
| [hw.network.bandwidth.utilization on virtualization.vswitch](reports/refinement-virtualization-hw-network-bandwidth-utilization-metric.md) | hmc |
| [hw.network.io on virtualization.vswitch](reports/refinement-virtualization-hw-network-io-metric.md) | hmc |
| [hw.network.packets on virtualization.vswitch](reports/refinement-virtualization-hw-network-packets-metric.md) | hmc |
| [hw.network.up on virtualization.vswitch](reports/refinement-virtualization-hw-network-up-metric.md) | hmc |
| [hw.power on virtualization.platform](reports/refinement-virtualization-hw-power-metric.md) | hmc |
| [hw.status on virtualization.platform](reports/refinement-virtualization-hw-status-metric.md) | hmc |
| [hw.temperature on virtualization.platform](reports/refinement-virtualization-hw-temperature-metric.md) | hmc |
| [mainframe.adapter.physical_channel.status.code](reports/mainframe-adapter-physical-channel-status-code-metric.md) | hmc |
| [mainframe.adapter.status.code](reports/mainframe-adapter-status-code-metric.md) | hmc |
| [mainframe.adapter.utilization](reports/mainframe-adapter-utilization-metric.md) | hmc |
| [mainframe.channel.utilization](reports/mainframe-channel-utilization-metric.md) | hmc |
| [mainframe.cpu.smt_mode.utilization](reports/mainframe-cpu-smt-mode-utilization-metric.md) | hmc |
| [mainframe.cpu.thread0.utilization](reports/mainframe-cpu-thread0-utilization-metric.md) | hmc |
| [mainframe.cpu.thread1.utilization](reports/mainframe-cpu-thread1-utilization-metric.md) | hmc |
| [mainframe.cpu.utilization](reports/mainframe-cpu-utilization-metric.md) | hmc |
| [mainframe.host.adapter.utilization](reports/mainframe-host-adapter-utilization-metric.md) | hmc |
| [mainframe.host.channel.utilization](reports/mainframe-host-channel-utilization-metric.md) | hmc |
| [mainframe.host.cpu.active.count](reports/mainframe-host-cpu-active-count-metric.md) | hmc |
| [mainframe.host.cpu.defective.count](reports/mainframe-host-cpu-defective-count-metric.md) | hmc |
| [mainframe.host.cpu.spare.count](reports/mainframe-host-cpu-spare-count-metric.md) | hmc |
| [mainframe.host.cpu.utilization](reports/mainframe-host-cpu-utilization-metric.md) | hmc |
| [mainframe.host.dewpoint](reports/mainframe-host-dewpoint-metric.md) | hmc |
| [mainframe.host.heatload](reports/mainframe-host-heatload-metric.md) | hmc |
| [mainframe.host.humidity](reports/mainframe-host-humidity-metric.md) | hmc |
| [mainframe.host.memory.size](reports/mainframe-host-memory-size-metric.md) | hmc |
| [mainframe.host.memory.vfm.increment.size](reports/mainframe-host-memory-vfm-increment-size-metric.md) | hmc |
| [mainframe.host.memory.vfm.size](reports/mainframe-host-memory-vfm-size-metric.md) | hmc |
| [mainframe.host.power.cord.usage](reports/mainframe-host-power-cord-usage-metric.md) | hmc |
| [mainframe.host.power.usage](reports/mainframe-host-power-usage-metric.md) | hmc |
| [mainframe.host.status.unacceptable](reports/mainframe-host-status-unacceptable-metric.md) | hmc |
| [mainframe.partition.adapter.utilization](reports/mainframe-partition-adapter-utilization-metric.md) | hmc |
| [mainframe.partition.capacity.defined](reports/mainframe-partition-capacity-defined-metric.md) | hmc |
| [mainframe.partition.cpu.capped.count](reports/mainframe-partition-cpu-capped-count-metric.md) | hmc |
| [mainframe.partition.cpu.mode](reports/mainframe-partition-cpu-mode-metric.md) | hmc |
| [mainframe.partition.cpu.reserved.count](reports/mainframe-partition-cpu-reserved-count-metric.md) | hmc |
| [mainframe.partition.cpu.threads_per_processor](reports/mainframe-partition-cpu-threads-per-processor-metric.md) | hmc |
| [mainframe.partition.cpu.utilization](reports/mainframe-partition-cpu-utilization-metric.md) | hmc |
| [mainframe.partition.cpu.virtual.count](reports/mainframe-partition-cpu-virtual-count-metric.md) | hmc |
| [mainframe.partition.memory.size](reports/mainframe-partition-memory-size-metric.md) | hmc |
| [mainframe.partition.power.usage](reports/mainframe-partition-power-usage-metric.md) | hmc |
| [mainframe.partition.status.code](reports/mainframe-partition-status-code-metric.md) | hmc |
| [mainframe.partition.status.unacceptable](reports/mainframe-partition-status-unacceptable-metric.md) | hmc |
| [mainframe.partition.wlm.enabled](reports/mainframe-partition-wlm-enabled-metric.md) | hmc |
| [mainframe.storage.group.capacity](reports/mainframe-storage-group-capacity-metric.md) | hmc |
| [mainframe.storage.group.usage](reports/mainframe-storage-group-usage-metric.md) | hmc |
| [mainframe.storage.group.volume.capacity](reports/mainframe-storage-group-volume-capacity-metric.md) | hmc |
| [system.cpu.time on virtualization.partition, virtualization.platform, virtualization.vm](reports/refinement-virtualization-system-cpu-time-metric.md) | hmc |
| [system.cpu.utilization on virtualization.partition, virtualization.platform](reports/refinement-mainframe-system-cpu-utilization-metric.md) | hmc |
| [system.cpu.utilization on virtualization.partition, virtualization.platform, virtualization.vm](reports/refinement-virtualization-system-cpu-utilization-metric.md) | hmc |
| [system.disk.limit on virtualization.platform, virtualization.storage_pool](reports/refinement-virtualization-system-disk-limit-metric.md) | hmc |
| [system.filesystem.usage on virtualization.vm](reports/refinement-virtualization-vm-system-filesystem-usage-metric.md) | hmc |
| [system.filesystem.utilization on virtualization.vm](reports/refinement-virtualization-vm-system-filesystem-utilization-metric.md) | hmc |
| [system.memory.usage on virtualization.vm](reports/refinement-virtualization-vm-system-memory-usage-metric.md) | hmc |
| [system.memory.utilization on virtualization.vm](reports/refinement-virtualization-vm-system-memory-utilization-metric.md) | hmc |
| [system.network.errors on mainframe.partition.nic](reports/refinement-mainframe-nic-system-network-errors-metric.md) | hmc |
| [system.network.errors on mainframe.adapter.port](reports/refinement-mainframe-port-system-network-errors-metric.md) | hmc |
| [system.network.errors on virtualization.partition, virtualization.vm, virtualization.vswitch](reports/refinement-virtualization-system-network-errors-metric.md) | hmc |
| [system.network.io on mainframe.partition.nic](reports/refinement-mainframe-nic-system-network-io-metric.md) | hmc |
| [system.network.io on mainframe.adapter.port](reports/refinement-mainframe-port-system-network-io-metric.md) | hmc |
| [system.network.io on virtualization.partition, virtualization.vm, virtualization.vswitch](reports/refinement-virtualization-system-network-io-metric.md) | hmc |
| [system.network.packet.count on mainframe.partition.nic](reports/refinement-mainframe-nic-system-network-packet-count-metric.md) | hmc |
| [system.network.packet.count on mainframe.adapter.port](reports/refinement-mainframe-port-system-network-packet-count-metric.md) | hmc |
| [system.network.packet.count on virtualization.partition, virtualization.vm, virtualization.vswitch](reports/refinement-virtualization-system-network-packet-count-metric.md) | hmc |
| [system.network.packet.dropped on mainframe.partition.nic](reports/refinement-mainframe-nic-system-network-packet-dropped-metric.md) | hmc |
| [system.network.packet.dropped on mainframe.adapter.port](reports/refinement-mainframe-port-system-network-packet-dropped-metric.md) | hmc |
| [system.network.packet.dropped on virtualization.partition, virtualization.vm, virtualization.vswitch](reports/refinement-virtualization-system-network-packet-dropped-metric.md) | hmc |
| [system.paging.faults on virtualization.vm](reports/refinement-virtualization-vm-system-paging-faults-metric.md) | hmc |
| [system.uptime on virtualization.vm](reports/refinement-virtualization-vm-system-uptime-metric.md) | hmc |
| [virtualization.cluster.host.count](reports/virtualization-cluster-host-count-metric.md) | hmc |
| [virtualization.cluster.vm.count](reports/virtualization-cluster-vm-count-metric.md) | hmc |
| [virtualization.hypervisor.memory.overcommit_ratio](reports/virtualization-hypervisor-memory-overcommit-ratio-metric.md) | hmc |
| [virtualization.partition.cpu.count](reports/virtualization-partition-cpu-count-metric.md) | hmc |
| [virtualization.partition.cpu.is_capped](reports/virtualization-partition-cpu-is-capped-metric.md) | hmc |
| [virtualization.partition.cpu.time](reports/virtualization-partition-cpu-time-metric.md) | hmc |
| [virtualization.partition.cpu.utilization](reports/virtualization-partition-cpu-utilization-metric.md) | hmc |
| [virtualization.partition.cpu.weight on virtualization.partition](reports/refinement-mainframe-virtualization-partition-cpu-weight-metric.md) | hmc |
| [virtualization.partition.cpu.weight](reports/virtualization-partition-cpu-weight-metric.md) | hmc |
| [virtualization.partition.memory.size](reports/virtualization-partition-memory-size-metric.md) | hmc |
| [virtualization.partition.state.code](reports/virtualization-partition-state-code-metric.md) | hmc |
| [virtualization.platform.cpu.utilization](reports/virtualization-platform-cpu-utilization-metric.md) | hmc |
| [virtualization.platform.memory.total](reports/virtualization-platform-memory-total-metric.md) | hmc |
| [virtualization.platform.memory.used](reports/virtualization-platform-memory-used-metric.md) | hmc |
| [virtualization.platform.partition.count](reports/virtualization-platform-partition-count-metric.md) | hmc |
| [virtualization.platform.power.usage](reports/virtualization-platform-power-usage-metric.md) | hmc |
| [virtualization.platform.vm.count](reports/virtualization-platform-vm-count-metric.md) | hmc |
| [virtualization.resource_pool.cpu.allocated](reports/virtualization-resource-pool-cpu-allocated-metric.md) | hmc |
| [virtualization.resource_pool.memory.allocated](reports/virtualization-resource-pool-memory-allocated-metric.md) | hmc |
| [virtualization.storage_pool.available](reports/virtualization-storage-pool-available-metric.md) | hmc |
| [virtualization.storage_pool.used](reports/virtualization-storage-pool-used-metric.md) | hmc |
| [virtualization.vm.cpu.count](reports/virtualization-vm-cpu-count-metric.md) | hmc |
| [virtualization.vm.cpu.ready_time](reports/virtualization-vm-cpu-ready-time-metric.md) | hmc |
| [virtualization.vm.cpu.steal_time](reports/virtualization-vm-cpu-steal-time-metric.md) | hmc |
| [virtualization.vm.cpu.utilization](reports/virtualization-vm-cpu-utilization-metric.md) | hmc |
| [virtualization.vm.disk.errors](reports/virtualization-vm-disk-errors-metric.md) | hmc |
| [virtualization.vm.disk.io](reports/virtualization-vm-disk-io-metric.md) | hmc |
| [virtualization.vm.disk.latency.time](reports/virtualization-vm-disk-latency-time-metric.md) | hmc |
| [virtualization.vm.disk.operations](reports/virtualization-vm-disk-operations-metric.md) | hmc |
| [virtualization.vm.memory.allocated](reports/virtualization-vm-memory-allocated-metric.md) | hmc |
| [virtualization.vm.memory.balloon](reports/virtualization-vm-memory-balloon-metric.md) | hmc |
| [virtualization.vm.memory.rss](reports/virtualization-vm-memory-rss-metric.md) | hmc |
| [virtualization.vm.memory.swapped](reports/virtualization-vm-memory-swapped-metric.md) | hmc |
| [virtualization.vm.memory.used](reports/virtualization-vm-memory-used-metric.md) | hmc |
| [virtualization.vm.network.io](reports/virtualization-vm-network-io-metric.md) | hmc |
| [virtualization.vm.power.state](reports/virtualization-vm-power-state-metric.md) | hmc |
<!-- status:end -->
