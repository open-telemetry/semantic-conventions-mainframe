# Virtualization Semantic Conventions — VMware vSphere Implementation Guide

> **Scope:** This document describes how the OpenTelemetry Semantic Conventions defined in
> `model/virtualization/` map to VMware vSphere / ESXi telemetry sources. All entity types,
> attribute keys, and metric names are exact references to the v2 YAML definitions in the repository.

---

## 1. Architecture Overview

VMware vSphere presents a six-tier management hierarchy. The table below maps each vSphere
construct to its canonical OTel virtualization entity:

```
vCenter Server (management plane)
└── Datacenter
    └── Cluster (ClusterComputeResource)          → virtualization.cluster
        ├── ESXi Host (HostSystem)                → virtualization.platform  (virtualization.system.name = "vmware.esxi")
        │   ├── Resource Pool (ResourcePool)      → virtualization.resource_pool
        │   ├── Virtual Machine (VirtualMachine)  → virtualization.vm
        │   │   ├── Virtual Disk (VirtualDisk)    → (attribute: virtualization.vm.disk.name)
        │   │   └── vNIC (VirtualEthernetCard)    → (attribute: virtualization.vm.network.interface.name)
        │   └── Datastore (Datastore)             → virtualization.storage_pool
        └── dvSwitch (DistributedVirtualSwitch)   → virtualization.vswitch
```

**Key design decisions:**
- The ESXi host maps to `virtualization.platform`. Its `virtualization.system.name` discriminator is `vmware.esxi`.
- Virtual machines map to `virtualization.vm`. The hypervisor entity (`virtualization.hypervisor`) is used to represent the vCenter or ESXi management service itself when hypervisor-level metrics (e.g., memory overcommit ratio) are required.
- vSphere Resource Pools map to `virtualization.resource_pool`. Note that the DRS/HA cluster maps to `virtualization.cluster`, not the resource pool.
- Datastores map to `virtualization.storage_pool`.
- dvSwitches (and standard vSwitches at the host level) map to `virtualization.vswitch`.
- IBM Z PR/SM logical partitions are **not** used on this platform; `virtualization.partition` is irrelevant for vSphere.

---

## 2. Entity Instance Construction

### 2.1 `virtualization.platform` — ESXi Host

| OTel Attribute | vSphere Source | Managed Object | Notes |
|---|---|---|---|
| `host.name` *(identity)* | `HostSystem.summary.config.name` | `HostSystem` | Short hostname, e.g. `esxi-01.corp.local` |
| `host.id` | `HostSystem.summary.hardware.uuid` | `HostSystem` | SMBIOS UUID, e.g. `422a8f9d-…` |
| `host.type` | `HostSystem.summary.hardware.model` | `HostSystem` | e.g. `ProLiant DL380 Gen10` |
| `host.arch` | `HostSystem.summary.hardware.cpuArch` | `HostSystem` | Typically `amd64` |
| `virtualization.system.name` | *static* | — | Hardcode `vmware.esxi` |
| `virtualization.platform.serial_number` | `HostSystem.summary.hardware.otherIdentifyingInfo[SerialNumberTag]` | `HostSystem` | Vendor serial |
| `virtualization.platform.firmware.version` | `HostSystem.config.product.version` | `HostSystem` | e.g. `7.0.3` |

### 2.2 `virtualization.vm` — Virtual Machine

| OTel Attribute | vSphere Source | Managed Object | Notes |
|---|---|---|---|
| `virtualization.vm.id` *(identity)* | `VirtualMachine.config.uuid` | `VirtualMachine` | Instance UUID, e.g. `502f1234-…` |
| `virtualization.vm.name` | `VirtualMachine.config.name` | `VirtualMachine` | Display name |
| `virtualization.vm.instance_id` | `VirtualMachine.summary.config.uuid` | `VirtualMachine` | Same as `.config.uuid` or BIOS UUID |
| `virtualization.vm.state` | `VirtualMachine.runtime.powerState` | `VirtualMachine` | `poweredOn` → `running`, `poweredOff` → `stopped`, `suspended` → `paused` |
| `virtualization.vm.cpu.count` | `VirtualMachine.config.hardware.numCPU` | `VirtualMachine` | vCPU count |
| `virtualization.vm.memory.size` | `VirtualMachine.config.hardware.memoryMB` | `VirtualMachine` | Configured MiB |
| `virtualization.vm.machine_type` | `VirtualMachine.config.guestId` | `VirtualMachine` | e.g. `rhel8_64Guest` |
| `virtualization.vm.nested_virtualization.enabled` | `VirtualMachine.config.nestedHVEnabled` | `VirtualMachine` | Boolean |
| `virtualization.system.name` | *static* | — | `vmware.esxi` |

### 2.3 `virtualization.cluster` — vSphere Cluster

| OTel Attribute | vSphere Source | Managed Object | Notes |
|---|---|---|---|
| `virtualization.cluster.name` *(identity)* | `ClusterComputeResource.name` | `ClusterComputeResource` | e.g. `prod-cluster-01` |
| `virtualization.cluster.id` | `ClusterComputeResource.self` (MoRef) | `ClusterComputeResource` | e.g. `domain-c8` |

### 2.4 `virtualization.resource_pool` — Resource Pool

| OTel Attribute | vSphere Source | Managed Object | Notes |
|---|---|---|---|
| `virtualization.resource_pool.name` *(identity)* | `ResourcePool.name` | `ResourcePool` | e.g. `high-priority-pool` |
| `virtualization.resource_pool.id` | `ResourcePool.self` (MoRef) | `ResourcePool` | e.g. `resgroup-72` |
| `virtualization.system.name` | *static* | — | `vmware.esxi` |

### 2.5 `virtualization.storage_pool` — Datastore

| OTel Attribute | vSphere Source | Managed Object | Notes |
|---|---|---|---|
| `virtualization.storage_pool.name` *(identity)* | `Datastore.summary.name` | `Datastore` | e.g. `datastore-ssd-01` |
| `virtualization.storage_pool.id` | `Datastore.self` (MoRef) | `Datastore` | e.g. `datastore-21` |
| `virtualization.system.name` | *static* | — | `vmware.esxi` |

### 2.6 `virtualization.vswitch` — dvSwitch / vSwitch

| OTel Attribute | vSphere Source | Managed Object | Notes |
|---|---|---|---|
| `virtualization.vswitch.name` *(identity)* | `DistributedVirtualSwitch.name` | `DistributedVirtualSwitch` | e.g. `dvSwitch-prod` |
| `virtualization.vswitch.id` | `DistributedVirtualSwitch.self` (MoRef) | `DistributedVirtualSwitch` | e.g. `dvs-19` |
| `virtualization.system.name` | *static* | — | `vmware.esxi` |

---

## 3. Comprehensive Signal Mapping

### 3.1 Virtual Machine Metrics

| OTel Metric Name | Instrument | Unit | Target Entity | vSphere Performance Counter | Transformation | Notes |
|---|---|---|---|---|---|---|
| `virtualization.vm.cpu.utilization` | gauge | `1` | `virtualization.vm` | `cpu.usage.average` (per-VM, rollup: average) | `value_percent / 100` | vCenter returns 0–10000 (in hundredths of %). Divide by 10000 for a 0–1 ratio. Interval: 20 s real-time. |
| `virtualization.vm.cpu.ready_time` | gauge | `1` | `virtualization.vm` | `cpu.ready.summation` | `value_ms / (interval_ms × numCPU)` | Returns milliseconds ready per interval. Divide by (20000 × vCPU count) for per-vCPU ratio. Interval: 20 s. |
| `virtualization.vm.cpu.count` | updowncounter | `{vcpu}` | `virtualization.vm` | `VirtualMachine.config.hardware.numCPU` (property) | — | Not a perf counter; read from VM config property. |
| `virtualization.vm.memory.allocated` | gauge | `MiBy` | `virtualization.vm` | `mem.granted.average` | `value_KB / 1024` | Returns kilobytes. Convert to MiB by dividing by 1024. |
| `virtualization.vm.memory.used` | gauge | `MiBy` | `virtualization.vm` | `mem.active.average` | `value_KB / 1024` | Active (touched) guest memory in KB. |
| `virtualization.vm.memory.balloon` | gauge | `MiBy` | `virtualization.vm` | `mem.vmmemctl.average` | `value_KB / 1024` | Balloon driver inflation in KB. Non-zero = host pressure. |
| `virtualization.vm.memory.swapped` | gauge | `MiBy` | `virtualization.vm` | `mem.swapped.average` | `value_KB / 1024` | Memory swapped to host swap area in KB. |
| `virtualization.vm.disk.io` (read) | counter | `By` | `virtualization.vm` | `disk.read.average` | `rate_KBps × 1024 × Δt` | Per-disk, per-interval rate in KB/s. Multiply by 1024 and elapsed seconds to get cumulative bytes. Set `virtualization.vm.disk.direction=read`. |
| `virtualization.vm.disk.io` (write) | counter | `By` | `virtualization.vm` | `disk.write.average` | `rate_KBps × 1024 × Δt` | Per-disk, per-interval rate. Set `virtualization.vm.disk.direction=write`. |
| `virtualization.vm.disk.operations` (read) | counter | `{operation}` | `virtualization.vm` | `disk.numberRead.summation` | accumulate | Per-disk cumulative read count. Set `virtualization.vm.disk.direction=read`. |
| `virtualization.vm.disk.operations` (write) | counter | `{operation}` | `virtualization.vm` | `disk.numberWrite.summation` | accumulate | Per-disk cumulative write count. Set `virtualization.vm.disk.direction=write`. |
| `virtualization.vm.disk.latency.time` (read) | counter | `s` | `virtualization.vm` | `disk.totalReadLatency.average` | `latency_ms / 1000 × Δops` | Average read latency in ms per op × ops in interval → cumulative seconds. Set `virtualization.vm.disk.direction=read`. |
| `virtualization.vm.disk.latency.time` (write) | counter | `s` | `virtualization.vm` | `disk.totalWriteLatency.average` | `latency_ms / 1000 × Δops` | Average write latency. Set `virtualization.vm.disk.direction=write`. |
| `virtualization.vm.disk.errors` | counter | `{error}` | `virtualization.vm` | `disk.commandsAborted.summation` + `disk.busResets.summation` | sum and accumulate | Sum aborted commands and bus resets. |
| `virtualization.vm.network.io` (rx) | counter | `By` | `virtualization.vm` | `net.bytesRx.average` | `rate_KBps × 1024 × Δt` | Per-NIC rate in KB/s → cumulative bytes. Set `network.io.direction=receive`. |
| `virtualization.vm.network.io` (tx) | counter | `By` | `virtualization.vm` | `net.bytesTx.average` | `rate_KBps × 1024 × Δt` | Per-NIC rate. Set `network.io.direction=transmit`. |
| `virtualization.vm.power.state` | gauge | `1` | `virtualization.vm` | `VirtualMachine.runtime.powerState` (property) | 1 if current state matches, else 0 | Emit one series per state value (`running`, `stopped`, `paused`). |
| `virtualization.vm.cpu.steal_time` | gauge | `1` | `virtualization.vm` | N/A | — | **Not available** on vSphere. Omit. |
| `virtualization.vm.memory.rss` | gauge | `MiBy` | `virtualization.vm` | `mem.consumed.average` | `value_KB / 1024` | Closest approximation: consumed = granted − balloon. Technically distinct from RSS. |

### 3.2 Platform (ESXi Host) Metrics

| OTel Metric Name | Instrument | Unit | Target Entity | vSphere Source | Transformation | Notes |
|---|---|---|---|---|---|---|
| `virtualization.platform.cpu.utilization` | gauge | `1` | `virtualization.platform` | `cpu.usage.average` (per-host rollup) | `value_percent / 100` | Aggregate across all pCPUs on the host. |
| `virtualization.platform.memory.total` | gauge | `MiBy` | `virtualization.platform` | `HostSystem.summary.hardware.memorySize` | `value_B / 1048576` | Physical RAM in bytes. Convert to MiB. |
| `virtualization.platform.memory.used` | gauge | `MiBy` | `virtualization.platform` | `mem.usage.average` (host) | `value_KB / 1024` | Host-level memory usage in KB. |
| `virtualization.platform.vm.count` | updowncounter | `{vm}` | `virtualization.platform` | `HostSystem.summary.quickStats.overallCpuUsage` → `numVms` from summary | — | Read `HostSystem.summary.config.product.version` → `numVMs` via `DatastoreSummary`. |
| `virtualization.platform.power.usage` | gauge | `W` | `virtualization.platform` | `power.power` (host perf counter, if host supports vSphere Power Management) | — | Returns Watts directly. Not available on all hardware. |

### 3.3 Cluster Metrics

| OTel Metric Name | Instrument | Unit | Target Entity | vSphere Source | Transformation | Notes |
|---|---|---|---|---|---|---|
| `virtualization.cluster.host.count` | updowncounter | `{host}` | `virtualization.cluster` | `ClusterComputeResource.summary.numHosts` | — | Total hosts in cluster. |
| `virtualization.cluster.vm.count` | updowncounter | `{vm}` | `virtualization.cluster` | `ClusterComputeResource.summary.numEffectiveHosts` → sum VM count | — | Sum VMs across all member hosts. |

### 3.4 Resource Pool Metrics

| OTel Metric Name | Instrument | Unit | Target Entity | vSphere Source | Transformation | Notes |
|---|---|---|---|---|---|---|
| `virtualization.resource_pool.cpu.allocated` | gauge | `{cpu}` | `virtualization.resource_pool` | `ResourcePool.config.cpuAllocation.reservation` | `value_MHz / host_pCPU_MHz` | CPU reservation in MHz. Normalise by mean pCPU frequency for fractional vCPU equivalent. |
| `virtualization.resource_pool.memory.allocated` | gauge | `MiBy` | `virtualization.resource_pool` | `ResourcePool.config.memoryAllocation.reservation` | `value_MB` | Reservation in MB = MiB on vSphere. Direct use. |

### 3.5 Storage Pool (Datastore) Metrics

| OTel Metric Name | Instrument | Unit | Target Entity | vSphere Source | Transformation | Notes |
|---|---|---|---|---|---|---|
| `virtualization.storage_pool.capacity.used` | gauge | `By` | `virtualization.storage_pool` | `DatastoreSummary.capacity - DatastoreSummary.freeSpace` | — | vCenter does not expose `.used` directly; compute as total − free. |
| `virtualization.storage_pool.capacity.available` | gauge | `By` | `virtualization.storage_pool` | `DatastoreSummary.freeSpace` | — | Returns bytes directly. |

### 3.6 Hypervisor Metrics

| OTel Metric Name | Instrument | Unit | Target Entity | vSphere Source | Transformation | Notes |
|---|---|---|---|---|---|---|
| `virtualization.hypervisor.memory.overcommit_ratio` | gauge | `1` | `virtualization.hypervisor` | `sum(VM mem.granted) / HostSystem.summary.hardware.memorySize` | `granted_KB / (host_bytes / 1024)` | Compute by querying all VMs on the host and dividing sum of `mem.granted.average` by total physical RAM. |

### 3.7 Upstream Metric Refinements (system.* on vSphere)

The upstream `system.*` metrics flow to `virtualization.platform` and `virtualization.vm` through the
`host` entity refinement lineage. The following metrics arrive via the OTel Collector
`hostmetricsreceiver` or `vcenterreceiver` and are associated through the refinement path:

| Refined Metric | OTel Refinement ID | Relevant for vSphere? |
|---|---|---|
| `system.cpu.time` | `refinement.virtualization.system.cpu.time` | Yes — per-mode CPU time on ESXi guest OS |
| `system.cpu.utilization` | `refinement.virtualization.system.cpu.utilization` | Yes — per-mode utilization |
| `system.network.io` | `refinement.virtualization.system.network.io` | Yes — with `virtualization.vswitch.name` |
| `system.network.errors` | `refinement.virtualization.system.network.errors` | Yes |
| `system.disk.limit` | `refinement.virtualization.system.disk.limit` | Yes — datastore-level aggregation |
| `hw.host.power` | `refinement.virtualization.hw.host.power` | Yes — via IPMI/vSphere power sensor |
| `hw.network.io` | `refinement.virtualization.hw.network.io` | Yes — bound to `virtualization.vswitch` |

---

## 4. Conversion Mathematics & Ingestion Patterns

### 4.1 Performance Counter Sample Types

vCenter collects per-interval statistics in four rollup types:

| Rollup | Meaning | OTel Mapping |
|---|---|---|
| `average` | Mean value over the 20 s collection window | Gauge (value at end of interval) |
| `summation` | Sum of values over the 20 s collection window | Counter delta (accumulate across intervals) |
| `latest` | Last sample in the interval | Gauge |
| `minimum`/`maximum` | Extremes within the interval | Histogram bucket (approximate) |

### 4.2 Rate Counters → Cumulative OTel Counters

Several vSphere counters return **rates** (e.g., KB/s) rather than cumulative totals. To produce
monotonically-increasing OTel counters from rate measurements, the Collector processor must
integrate each rate sample:

```
cumulative_bytes[t] = cumulative_bytes[t-1] + (rate_KBps[t] × 1024 × interval_s)
```

where `interval_s = 20` for vSphere real-time statistics.

The OTel Collector `cumulativetodeltaprocessor` applied in reverse (i.e., a rate-to-cumulative
transform) is not built-in; use a `metricstransformprocessor` or an intermediate Prometheus counter
accumulation via recording rules:

```yaml
# Prometheus recording rule example
- record: virt_vm_disk_io_read_bytes_total
  expr: |
    increase(vcenter_vm_disk_throughput_read_kbps[20s]) * 1024
```

### 4.3 CPU Ready Time to Ratio

```
ready_ratio = cpu_ready_summation_ms / (interval_ms × vCPU_count)
            = cpu_ready_summation_ms / (20000 × config.hardware.numCPU)
```

Values > 0.10 (10% ready ratio) indicate significant scheduling contention.

### 4.4 Disk Latency Counter to Cumulative Seconds

```
latency_total_s = totalReadLatency_ms / 1000 × numberRead_summation
```

This yields `virtualization.vm.disk.latency.time` (unit: `s`, instrument: counter). The average
latency per operation is recovered by: `rate(latency_total_s[Δt]) / rate(operations[Δt])`.

---

## 5. Collector Pipeline

### 5.1 vcenterreceiver (recommended)

The OpenTelemetry Collector `vcenterreceiver` (contrib) natively queries vCenter via the vSphere
Web Services API (SOAP/REST) and emits metrics with vSphere-native resource attributes.

**Collector configuration skeleton:**

```yaml
receivers:
  vcenter:
    endpoint: https://vcenter.corp.local
    username: otel-reader@vsphere.local
    password: ${env:VCENTER_PASSWORD}
    collection_interval: 60s
    # Opt-in to per-disk and per-NIC breakdowns
    metrics:
      vcenter.vm.disk.throughput:
        enabled: true
      vcenter.vm.disk.latency.avg:
        enabled: true
      vcenter.vm.network.throughput:
        enabled: true
      vcenter.host.memory.utilization:
        enabled: true

processors:
  # Rename vCenter-native attributes to OTel semantic convention attributes
  transform/vcenter_to_semconv:
    metric_statements:
      - context: datapoint
        statements:
          - set(attributes["virtualization.vm.id"],    attributes["vcenter.vm.id"])
          - set(attributes["virtualization.vm.name"],  attributes["vcenter.vm.name"])
          - set(attributes["host.name"],               attributes["vcenter.host.name"])
          - set(attributes["virtualization.cluster.name"], attributes["vcenter.cluster.name"])
          - set(attributes["virtualization.system.name"], "vmware.esxi")

  # Convert vCenter rates to cumulative counters
  cumulativetodelta:
    metrics:
      - vcenter.vm.disk.throughput
      - vcenter.vm.network.throughput

exporters:
  otlp:
    endpoint: otel-collector-gateway:4317

service:
  pipelines:
    metrics:
      receivers: [vcenter]
      processors: [transform/vcenter_to_semconv, cumulativetodelta]
      exporters: [otlp]
```

### 5.2 Prometheus vSphere Exporter (alternative)

For environments where the OTel `vcenterreceiver` is not available, the
[vmware/vsphere-influxdb-go](https://github.com/influxdata/vsphere-influxdb-go) or
[pryorda/vmware_exporter](https://github.com/pryorda/vmware_exporter) Prometheus exporters can
be used with the OTel Collector `prometheusreceiver` and appropriate `metricstransformprocessor`
relabelling rules.

---

## 6. Platform-Specific Caveats

| Topic | Detail |
|---|---|
| **Partition metrics** | `virtualization.partition.*` metrics are not applicable on vSphere. Use `virtualization.vm.*` and `virtualization.platform.*` instead. |
| **CPU steal time** | `virtualization.vm.cpu.steal_time` is not exposed by vSphere; the ESXi hypervisor does not report per-VM steal time. Use `cpu.ready.summation` as the scheduling contention proxy instead. |
| **Memory RSS** | The closest approximation is `mem.consumed.average` (granted minus balloon). True RSS from the hypervisor perspective is not directly available via the performance counter API. |
| **Power telemetry** | `virtualization.platform.power.usage` requires the host hardware to support vSphere Power Management (`power.power` counter). Not available on all server models. |
| **Datastore vs. VMFS** | The `virtualization.storage_pool` entity maps to a Datastore, not a VMFS volume or NFS mount. A single datastore may span multiple LUNs on VMFS-6. |
| **dvSwitch vs. standard vSwitch** | Standard vSwitches are per-host and do not have a cluster-wide MoRef. Use `HostSystem.config.network.vswitch[*]` for standard switch discovery. dvSwitches have a cluster-level MoRef and are preferred for multi-host environments. |
| **vSphere Tags** | vCenter tags (categories/tags) can be propagated as additional resource attributes using the `vcenterreceiver`'s tag collection feature — useful for mapping VMs to application teams for tenancy attribution. |
