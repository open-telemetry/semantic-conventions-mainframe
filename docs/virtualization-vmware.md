# Virtualization Semantic Conventions — VMware vSphere Implementation Guide

> **Scope:** This document describes how the OpenTelemetry semantic conventions defined in
> `model/virtualization/` map to VMware vSphere / ESXi telemetry sources. Entity types, attribute
> keys and metric names are those of the `definition/2` YAML files; the generated pages under
> [docs/registry/virtualization/](registry/virtualization/README.md) are authoritative for
> instruments, units and attributes.

---

## 1. Architecture Overview

VMware vSphere presents a multi-tier management hierarchy. The tree below maps each vSphere
construct to its OTel virtualization entity:

```text
vCenter Server (management plane)
└── Datacenter
    └── Cluster (ClusterComputeResource)          → virtualization.cluster
        ├── ESXi Host (HostSystem)                → virtualization.platform (virtualization.system.name = "vmware.esxi")
        │   │                                       and virtualization.hypervisor (the ESXi hypervisor on the host)
        │   ├── Resource Pool (ResourcePool)      → virtualization.resource_pool
        │   ├── Virtual Machine (VirtualMachine)  → virtualization.vm
        │   │   ├── Virtual Disk (VirtualDisk)    → (attribute: virtualization.vm.disk.name)
        │   │   └── vNIC (VirtualEthernetCard)    → (attribute: virtualization.vm.network.interface.name)
        │   └── Datastore (Datastore)             → virtualization.storage_pool
        └── dvSwitch (DistributedVirtualSwitch)   → virtualization.vswitch
```

**Key design decisions:**

- The ESXi host maps to `virtualization.platform`; its `virtualization.system.name` is
  `vmware.esxi`. The ESXi hypervisor running on the host is the `virtualization.hypervisor`
  entity, used for hypervisor-level metrics such as the memory overcommit ratio. Because ESXi
  runs directly on the hardware, both are identified by the host hardware UUID.
- Virtual machines map to `virtualization.vm`, identified by the VM `instanceUuid`, which does not
  change when the VM is moved to another host with vMotion.
- vSphere resource pools map to `virtualization.resource_pool`. The DRS/HA cluster maps to
  `virtualization.cluster`, not to a resource pool.
- Datastores map to `virtualization.storage_pool`.
- Distributed switches (and standard vSwitches at the host level) map to
  `virtualization.vswitch`.
- vSphere has no firmware partitions; `virtualization.partition` does not apply.
- Managed object reference (MoRef) IDs such as `domain-c7` are unique only within one vCenter.
  Where the conventions use them, they are qualified by the vCenter instance UUID
  (`ServiceContent.about.instanceUuid`).

---

## 2. Entity Instance Construction

### 2.1 `virtualization.platform` — ESXi Host

| OTel Attribute | vSphere Source | Managed Object | Notes |
| --- | --- | --- | --- |
| `virtualization.platform.id` *(identity)* | `HostSystem.hardware.systemInfo.uuid` (also `summary.hardware.uuid`) | `HostSystem` | Host hardware (SMBIOS) UUID, e.g. `4c4c4544-0042-3510-8058-b4c04f4e3732` |
| `host.id` | same value | `HostSystem` | SHOULD equal `virtualization.platform.id` |
| `host.name` | `HostSystem.name` | `HostSystem` | e.g. `esxi-01.corp.local`; descriptive |
| `host.type` | `HostSystem.summary.hardware.model` | `HostSystem` | e.g. `ProLiant DL380 Gen10` |
| `host.arch` | *static* | — | `amd64` for x86 hosts |
| `virtualization.system.name` | *static* | — | `vmware.esxi` |
| `virtualization.platform.serial_number` | `HostSystem.summary.hardware.otherIdentifyingInfo` entry `SerialNumberTag` | `HostSystem` | Vendor serial |
| `virtualization.platform.firmware.version` | `HostSystem.hardware.biosInfo.biosVersion` | `HostSystem` | BIOS or firmware version |

### 2.2 `virtualization.hypervisor` — ESXi Hypervisor

| OTel Attribute | vSphere Source | Managed Object | Notes |
| --- | --- | --- | --- |
| `virtualization.hypervisor.id` *(identity)* | `HostSystem.hardware.systemInfo.uuid` | `HostSystem` | Host hardware UUID |
| `virtualization.hypervisor.version` | `HostSystem.config.product.version` | `HostSystem` | e.g. `8.0.3` |
| `virtualization.hypervisor.type` | *static* | — | `type1` |
| `virtualization.hypervisor.state` | `HostSystem.runtime.connectionState` | `HostSystem` | `connected` → `active`, `disconnected` → `inactive`, `notResponding` → `unknown` |
| `virtualization.system.name` | *static* | — | `vmware.esxi` |

### 2.3 `virtualization.vm` — Virtual Machine

| OTel Attribute | vSphere Source | Managed Object | Notes |
| --- | --- | --- | --- |
| `virtualization.vm.id` *(identity)* | `VirtualMachine.config.instanceUuid` | `VirtualMachine` | vCenter instance UUID, e.g. `502e7c9a-1b2d-4f3e-8a6b-7c8d9e0f1a2b`; unchanged by vMotion |
| `virtualization.vm.name` | `VirtualMachine.name` | `VirtualMachine` | Display name |
| `virtualization.vm.instance_id` | `VirtualMachine.config.uuid` | `VirtualMachine` | BIOS UUID, distinct from the instance UUID |
| `virtualization.vm.state` | `VirtualMachine.runtime.powerState` | `VirtualMachine` | `poweredOn` → `running`, `poweredOff` → `stopped`, `suspended` → `paused` |
| `virtualization.vm.cpu.count` | `VirtualMachine.config.hardware.numCPU` | `VirtualMachine` | vCPU count |
| `virtualization.vm.memory.size` | `VirtualMachine.config.hardware.memoryMB` | `VirtualMachine` | Configured memory in MiB (the attribute is defined in MiB) |
| `virtualization.vm.machine_type` | `VirtualMachine.config.guestId` | `VirtualMachine` | e.g. `rhel8_64Guest` |
| `virtualization.vm.nested_virtualization.enabled` | `VirtualMachine.config.nestedHVEnabled` | `VirtualMachine` | Boolean |
| `virtualization.system.name` | *static* | — | `vmware.esxi` |

### 2.4 `virtualization.cluster` — vSphere Cluster

| OTel Attribute | vSphere Source | Managed Object | Notes |
| --- | --- | --- | --- |
| `virtualization.cluster.id` *(identity)* | vCenter instance UUID + `/` + cluster MoRef | `ServiceContent.about`, `ClusterComputeResource` | e.g. `1b9c0e2a-6f4d-4a52-9d3e-0c7d1e2f3a4b/domain-c7` |
| `virtualization.cluster.name` | `ClusterComputeResource.name` | `ClusterComputeResource` | e.g. `prod-cluster-01`; descriptive |

### 2.5 `virtualization.resource_pool` — Resource Pool

| OTel Attribute | vSphere Source | Managed Object | Notes |
| --- | --- | --- | --- |
| `virtualization.resource_pool.id` *(identity)* | vCenter instance UUID + `/` + ResourcePool MoRef | `ServiceContent.about`, `ResourcePool` | e.g. `1b9c0e2a-6f4d-4a52-9d3e-0c7d1e2f3a4b/resgroup-21` |
| `virtualization.resource_pool.name` | `ResourcePool.name` | `ResourcePool` | e.g. `high-priority-pool` |
| `virtualization.system.name` | *static* | — | `vmware.esxi` |

### 2.6 `virtualization.storage_pool` — Datastore

| OTel Attribute | vSphere Source | Managed Object | Notes |
| --- | --- | --- | --- |
| `virtualization.storage_pool.id` *(identity)* | Datastore UUID: `Datastore.info.vmfs.uuid` for VMFS; otherwise the identifier in `Datastore.summary.url` (`ds:///vmfs/volumes/<id>/`) | `Datastore` | Stable across vCenters that mount the datastore |
| `virtualization.storage_pool.name` | `Datastore.summary.name` | `Datastore` | e.g. `datastore-ssd-01` |
| `virtualization.system.name` | *static* | — | `vmware.esxi` |

### 2.7 `virtualization.vswitch` — dvSwitch / vSwitch

| OTel Attribute | vSphere Source | Managed Object | Notes |
| --- | --- | --- | --- |
| `virtualization.vswitch.id` *(identity)* | `DistributedVirtualSwitch.uuid`; standard vSwitch: host hardware UUID + `/` + switch name | `DistributedVirtualSwitch`, `HostSystem` | A distributed switch spans hosts, so its ID contains no host |
| `virtualization.vswitch.name` | `DistributedVirtualSwitch.name`; standard vSwitch: `HostSystem.config.network.vswitch[].name` | `DistributedVirtualSwitch`, `HostSystem` | e.g. `dvSwitch-prod`, `vSwitch0` |
| `virtualization.system.name` | *static* | — | `vmware.esxi` |

---

## 3. Signal Mapping

vSphere performance counters are named `<group>.<counter>.<rollup>`. The real-time statistics of
a host and its VMs are sampled every 20 seconds.

### 3.1 Virtual Machine Metrics

| OTel Metric Name | Instrument | Unit | vSphere Source | Transformation | Notes |
| --- | --- | --- | --- | --- | --- |
| `virtualization.vm.cpu.utilization` | gauge | `1` | `cpu.usage.average` (VM) | `value / 10000` | vCenter reports hundredths of a percent (0–10000). |
| `virtualization.vm.cpu.ready_time` | counter | `s` | `cpu.ready.summation` | `value_ms / 1000` per interval | Milliseconds ready but not scheduled in each interval; see §4.1 and §4.3. |
| `virtualization.vm.cpu.count` | updowncounter | `{vcpu}` | `VirtualMachine.config.hardware.numCPU` (property) | — | Not a performance counter. |
| `virtualization.vm.memory.allocated` | gauge | `By` | `mem.granted.average` | `value_KiB * 1024` | |
| `virtualization.vm.memory.used` | gauge | `By` | `mem.active.average` | `value_KiB * 1024` | Active (touched) guest memory. |
| `virtualization.vm.memory.balloon` | gauge | `By` | `mem.vmmemctl.average` | `value_KiB * 1024` | Non-zero means the host is reclaiming memory. |
| `virtualization.vm.memory.swapped` | gauge | `By` | `mem.swapped.average` | `value_KiB * 1024` | Memory swapped to the host swap file. |
| `virtualization.vm.disk.io` | counter | `By` | `disk.read.average`, `disk.write.average` | not derivable with built-in collector processors | Average rates in KBps, not byte totals; see §4.2. Set `virtualization.vm.disk.direction`. |
| `virtualization.vm.disk.operations` | counter | `{operation}` | `disk.numberRead.summation`, `disk.numberWrite.summation` | per interval | Operations in each interval. Set `virtualization.vm.disk.direction`. |
| `virtualization.vm.disk.latency.time` | counter | `s` | `disk.totalReadLatency.average`, `disk.totalWriteLatency.average` | see §4.4 | Average latency per operation in ms, multiplied by the operations in the interval. Set `virtualization.vm.disk.direction`. |
| `virtualization.vm.disk.errors` | counter | `{error}` | `disk.commandsAborted.summation` + `disk.busResets.summation` | per interval | No read/write split; `virtualization.vm.disk.direction` is omitted. |
| `virtualization.vm.network.io` | counter | `By` | `net.bytesRx.average`, `net.bytesTx.average` | not derivable with built-in collector processors | Average rates in KBps; see §4.2. Set `network.io.direction`. |
| `virtualization.vm.power.state` | gauge | `1` | `VirtualMachine.runtime.powerState` (property) | 1 for the current state, 0 otherwise | One series per `virtualization.vm.state` value (`running`, `stopped`, `paused`). |
| `virtualization.vm.cpu.steal_time` | counter | `s` | — | — | **Not available** on vSphere; omit. |
| `virtualization.vm.memory.rss` | gauge | `By` | — | — | **Not available** on vSphere; omit, or approximate with `virtualization.vm.memory.used`. `mem.consumed.average` is the closest counter but is not a resident set size. |

### 3.2 Platform (ESXi Host) Metrics

| OTel Metric Name | Instrument | Unit | vSphere Source | Transformation | Notes |
| --- | --- | --- | --- | --- | --- |
| `virtualization.platform.cpu.utilization` | gauge | `1` | `cpu.usage.average` (host) | `value / 10000` | Aggregate across all physical CPUs of the host. |
| `virtualization.platform.memory.total` | gauge | `By` | `HostSystem.summary.hardware.memorySize` | — | Already in bytes. |
| `virtualization.platform.memory.used` | gauge | `By` | `HostSystem.summary.quickStats.overallMemoryUsage` | `value_MiB * 1048576` | The host counter `mem.usage.average` is a percentage of host memory; if used, multiply it by `memorySize / 100`. |
| `virtualization.platform.vm.count` | updowncounter | `{vm}` | `HostSystem.vm` | count per `runtime.powerState` | Set `virtualization.platform.vm.state` (`running`, `stopped`, `paused`, or `all`). |
| `virtualization.platform.power.usage` | gauge | `W` | `power.power.average` (host) | — | Already in watts; requires host power management support. |
| `virtualization.platform.partition.count` | updowncounter | `{partition}` | — | — | Not applicable on vSphere. |

### 3.3 Cluster Metrics

| OTel Metric Name | Instrument | Unit | vSphere Source | Transformation | Notes |
| --- | --- | --- | --- | --- | --- |
| `virtualization.cluster.host.count` | updowncounter | `{host}` | `ClusterComputeResource.summary.numHosts` | — | Total hosts in the cluster. |
| `virtualization.cluster.vm.count` | updowncounter | `{vm}` | VMs of the cluster's hosts, counted per `runtime.powerState` | count | Set `virtualization.vm.state`. |

### 3.4 Resource Pool Metrics

| OTel Metric Name | Instrument | Unit | vSphere Source | Transformation | Notes |
| --- | --- | --- | --- | --- | --- |
| `virtualization.resource_pool.cpu.allocated` | gauge | `{cpu}` | `ResourcePool.config.cpuAllocation.reservation` | `value_MHz / pCPU_MHz` | CPU reservation in MHz, divided by the physical CPU frequency for a processor equivalent. |
| `virtualization.resource_pool.memory.allocated` | gauge | `By` | `ResourcePool.config.memoryAllocation.reservation` | `value_MiB * 1048576` | Reservation in MB (MiB). |

### 3.5 Storage Pool (Datastore) Metrics

| OTel Metric Name | Instrument | Unit | vSphere Source | Transformation | Notes |
| --- | --- | --- | --- | --- | --- |
| `virtualization.storage_pool.used` | updowncounter | `By` | `Datastore.summary.capacity - Datastore.summary.freeSpace` | — | vSphere does not report used space directly; compute it as total minus free. |
| `virtualization.storage_pool.available` | updowncounter | `By` | `Datastore.summary.freeSpace` | — | Already in bytes. |

### 3.6 Hypervisor Metrics

| OTel Metric Name | Instrument | Unit | vSphere Source | Transformation | Notes |
| --- | --- | --- | --- | --- | --- |
| `virtualization.hypervisor.memory.overcommit_ratio` | gauge | `1` | Sum of `VirtualMachine.config.hardware.memoryMB` of the host's VMs, and `HostSystem.summary.hardware.memorySize` | `sum(memoryMB) * 1048576 / memorySize` | Greater than 1 means memory is overcommitted. |

### 3.7 Upstream Metric Refinements

`system.*` metrics are reported by an operating system. On vSphere they come from a collector
running inside the guest (for example the collector's `hostmetrics` receiver) and describe the
VM from the inside; the guest's resource carries `virtualization.vm.id`. No collector runs on
ESXi itself, so vSphere provides no `system.*` source for `virtualization.platform`.

| Refined Metric | Refinement ID | Source on vSphere |
| --- | --- | --- |
| `system.cpu.time` | `refinement.virtualization.system.cpu.time` | Guest OS |
| `system.cpu.utilization` | `refinement.virtualization.system.cpu.utilization` | Guest OS |
| `system.network.io` | `refinement.virtualization.system.network.io` | Guest OS; `virtualization.vswitch.name` (opt-in) names the switch the vNIC is connected to |
| `system.network.errors` | `refinement.virtualization.system.network.errors` | Guest OS |
| `system.uptime` | `refinement.virtualization.vm.system.uptime` | Guest OS |
| `system.memory.usage` | `refinement.virtualization.vm.system.memory.usage` | Guest OS |
| `system.filesystem.usage` | `refinement.virtualization.vm.system.filesystem.usage` | Guest OS |
| `system.disk.limit` | `refinement.virtualization.system.disk.limit` | Datastore capacity (`Datastore.summary.capacity`), with `virtualization.storage_pool.name` |
| `hw.host.power` | `refinement.virtualization.hw.host.power` | Host power sensor (`power.power.average`) or the server's BMC |
| `hw.network.io` | `refinement.virtualization.hw.network.io` | Physical uplink adapters of a `virtualization.vswitch` |

---

## 4. Conversion Mathematics & Ingestion Patterns

### 4.1 Performance Counter Rollup Types

vCenter reports statistics per sampling interval in the following rollup types:

| Rollup | Meaning | OTel Mapping |
| --- | --- | --- |
| `average` | Mean value over the interval | Gauge |
| `summation` | Sum of values over the interval | Sum per interval: emit with delta temporality, or accumulate into a cumulative sum |
| `latest` | Last sample in the interval | Gauge |
| `minimum` / `maximum` | Extremes within the interval | Gauge; not used by these conventions |

### 4.2 Rate Counters and Byte Counters

`disk.read.average`, `disk.write.average`, `net.bytesRx.average` and `net.bytesTx.average` are
average **rates** in KBps over the sampling interval, not cumulative totals.
`virtualization.vm.disk.io` and `virtualization.vm.network.io` are byte **counters**. Producing a
counter from a rate means integrating it:

```text
bytes[t] = bytes[t-1] + rate_KBps[t] * 1024 * interval_s
```

The built-in OpenTelemetry Collector processors do not support this integration. The
`cumulativetodelta` processor converts cumulative sums to delta sums — it is configured with
`include`, `exclude`, `max_staleness` and `initial_value` and has no setting that turns a rate
into a counter. A collector component that reads the performance counters itself can integrate
them; the result is an approximation, because each sample is an interval average.

Without such a component, keep the rate metrics of the `vcenter` receiver as they are:

- `vcenter.vm.disk.throughput` is a gauge in `{KiBy/s}`, with a `direction` attribute (`read`,
  `write`).
- `vcenter.vm.network.throughput` is a non-monotonic sum in `By/s`, with a `direction` attribute
  (`transmitted`, `received`).

Query them as rates. A per-second byte rate is the average of the samples, multiplied by 1024
for the KiBy/s metric:

```promql
# Disk bytes per second (vcenter.vm.disk.throughput is in KiBy/s)
avg_over_time({"vcenter.vm.disk.throughput"}[5m]) * 1024

# Network bytes per second (vcenter.vm.network.throughput is already in By/s)
avg_over_time({"vcenter.vm.network.throughput"}[5m])
```

`increase()` and `rate()` are meaningless on these series, because they are rates, not counters.
The selectors use UTF-8 metric names (Prometheus 3); adjust them if Prometheus translates OTLP
metric names.

### 4.3 CPU Ready Time

`cpu.ready.summation` is the time, in milliseconds, that the VM was ready to run but not scheduled
during the interval, summed over its vCPUs:

```text
ready_time_s (per interval) = cpu.ready.summation_ms / 1000
ready ratio per vCPU        = rate(virtualization.vm.cpu.ready_time) / virtualization.vm.cpu.count
```

Ready ratios above about 0.10 per vCPU indicate significant scheduling contention.

### 4.4 Disk Latency Counter to Cumulative Seconds

```text
latency_time_s (per interval) = disk.totalReadLatency.average_ms / 1000 * disk.numberRead.summation
```

The write direction uses `disk.totalWriteLatency.average` and `disk.numberWrite.summation`. This
yields `virtualization.vm.disk.latency.time` (unit `s`, instrument counter). The average latency
per operation is recovered with
`rate(virtualization.vm.disk.latency.time) / rate(virtualization.vm.disk.operations)`.

---

## 5. Collector Pipeline

### 5.1 `vcenter` receiver (recommended)

The OpenTelemetry Collector `vcenter` receiver (contrib) queries vCenter through the vSphere Web
Services API and emits metrics with vSphere-specific resource attributes such as
`vcenter.vm.id` (the VM instance UUID), `vcenter.vm.name`, `vcenter.host.name` and
`vcenter.cluster.name`.

**Collector configuration skeleton:**

```yaml
receivers:
  vcenter:
    endpoint: https://vcenter.corp.local
    username: otel-reader@vsphere.local
    password: ${env:VCENTER_PASSWORD}
    collection_interval: 60s

processors:
  # Copy vCenter resource attributes to the semantic convention attributes.
  transform/vcenter_to_semconv:
    metric_statements:
      - context: resource
        statements:
          - set(attributes["virtualization.vm.id"], attributes["vcenter.vm.id"]) where attributes["vcenter.vm.id"] != nil
          - set(attributes["virtualization.vm.name"], attributes["vcenter.vm.name"]) where attributes["vcenter.vm.name"] != nil
          - set(attributes["host.name"], attributes["vcenter.host.name"]) where attributes["vcenter.vm.id"] == nil and attributes["vcenter.host.name"] != nil
          - set(attributes["virtualization.cluster.name"], attributes["vcenter.cluster.name"]) where attributes["vcenter.cluster.name"] != nil
          - set(attributes["virtualization.system.name"], "vmware.esxi")

exporters:
  otlp:
    endpoint: otel-collector-gateway:4317

service:
  pipelines:
    metrics:
      receivers: [vcenter]
      processors: [transform/vcenter_to_semconv]
      exporters: [otlp]
```

The receiver's resource attributes contain the VM instance UUID, so `virtualization.vm.id` can be
filled from them. They contain no host hardware UUID, vCenter instance UUID or datastore UUID, so
`virtualization.platform.id`, `virtualization.hypervisor.id`, `virtualization.cluster.id`,
`virtualization.resource_pool.id` and `virtualization.storage_pool.id` need an additional source,
such as an inventory lookup through the vSphere API. Names such as `vcenter.host.name` are
descriptive and do not replace them.

Do not route the receiver's throughput metrics through the `cumulativetodelta` processor: they are
rates, and that processor only converts cumulative sums to delta sums (see §4.2).

### 5.2 Other vSphere Collectors (alternatives)

Where the `vcenter` receiver cannot be used:

- [pryorda/vmware_exporter](https://github.com/pryorda/vmware_exporter) is a Prometheus exporter
  for vCenter. Scrape it with the collector's `prometheus` receiver and map its metric and label
  names with the `transform` or `metricstransform` processor. Its maintainer has announced that
  the project is looking for a new maintainer.
- [Oxalide/vsphere-influxdb-go](https://github.com/Oxalide/vsphere-influxdb-go) collects vSphere
  performance metrics and writes them to InfluxDB. It exposes no Prometheus endpoint, so the
  `prometheus` receiver cannot scrape it.

---

## 6. Platform-Specific Caveats

| Topic | Detail |
| --- | --- |
| **Partition metrics** | `virtualization.partition.*` metrics do not apply on vSphere. Use `virtualization.vm.*` and `virtualization.platform.*`. |
| **CPU steal time** | `virtualization.vm.cpu.steal_time` is not exposed by vSphere. Use `virtualization.vm.cpu.ready_time` (`cpu.ready.summation`) as the scheduling contention signal. |
| **Memory RSS** | vSphere reports no resident set size per VM. Omit `virtualization.vm.memory.rss` or approximate it with `virtualization.vm.memory.used`. |
| **Disk and network bytes** | The vSphere byte counters are interval-average rates; see §4.2 for why `virtualization.vm.disk.io` and `virtualization.vm.network.io` cannot be produced with built-in collector processors. |
| **Power telemetry** | `virtualization.platform.power.usage` requires host hardware that reports power to vSphere (`power.power.average`). Not available on all server models. |
| **Datastore vs. VMFS** | `virtualization.storage_pool` maps to a datastore, not to a VMFS volume or NFS mount. A VMFS datastore can span several LUNs. |
| **dvSwitch vs. standard vSwitch** | Standard vSwitches are per host and have no UUID of their own; their ID is the host hardware UUID plus the switch name. Discover them with `HostSystem.config.network.vswitch[]`. Distributed switches have a UUID and are preferred in multi-host environments. |
| **Several vCenters** | MoRef IDs repeat across vCenters. Qualify cluster and resource pool IDs with the vCenter instance UUID, as the attribute definitions require. |
| **vMotion** | The VM `instanceUuid` does not change when a VM moves to another host; the host the VM runs on is descriptive (`vcenter.host.name`), not part of the VM identity. |
