# Virtualization Semantic Conventions — KVM / libvirt Implementation Guide

> **Scope:** This document describes how the OpenTelemetry Semantic Conventions defined in
> `model/virtualization/` map to KVM / libvirt / QEMU telemetry sources. All entity types,
> attribute keys, and metric names are exact references to the v2 YAML definitions in the repository.

---

## 1. Architecture Overview

KVM (Kernel-based Virtual Machine) is a Linux kernel module that provides a Type-1 hypervisor
embedded in the host OS. Guest domains are managed by the `libvirt` management library, which
fronts the QEMU device emulation layer. The mapping to OTel virtualization entities is:

```
Linux Host (kernel + KVM module)
└── libvirt daemon (libvirtd / virtqemud)
    ├── virNodeInfo — host topology             → virtualization.platform  (virtualization.system.name = "kvm")
    ├── virDomain[] — guest domains
    │   ├── virDomainGetCPUStats()              → virtualization.vm.cpu.*
    │   ├── virDomainMemoryStats()              → virtualization.vm.memory.*
    │   ├── virDomainBlockStats() [per disk]    → virtualization.vm.disk.*   (attr: virtualization.vm.disk.name)
    │   └── virDomainInterfaceStats() [per NIC] → virtualization.vm.network.* (attr: virtualization.vm.network.interface.name)
    ├── virNetwork[] — virtual networks
    │   └── Linux Bridge / OVS bridge          → virtualization.vswitch     (virtualization.system.name = "kvm")
    └── virStoragePool[] — storage pools
        └── virStoragePoolGetInfo()             → virtualization.storage_pool
```

**Key design decisions:**
- The Linux host running the KVM hypervisor maps to `virtualization.platform`. Its `virtualization.system.name` is `kvm`.
- Each libvirt domain (`virDomain`) maps to `virtualization.vm`.
- `virtualization.hypervisor` represents the libvirt daemon itself for hypervisor-level metrics (memory overcommit ratio).
- Linux Bridge or OVS bridges backing libvirt virtual networks map to `virtualization.vswitch`.
- libvirt storage pools map to `virtualization.storage_pool`.
- `virtualization.partition` is not applicable in a standard KVM environment (no firmware-level partitioning).
- `virtualization.cluster` applies when KVM hosts are managed by a cluster manager such as oVirt, Proxmox VE, or OpenStack Nova.

---

## 2. Entity Instance Construction

### 2.1 `virtualization.platform` — KVM Host

| OTel Attribute | libvirt / Linux Source | API / Path | Notes |
|---|---|---|---|
| `host.name` *(identity)* | `virConnectGetHostname()` | libvirt connection | Linux hostname, e.g. `kvm-host-01` |
| `host.id` | `/etc/machine-id` or `dmidecode -s system-uuid` | sysfs / SMBIOS | Hardware UUID |
| `host.type` | `virNodeInfo.model` | `virNodeGetInfo()` | CPU model string, e.g. `x86_64` |
| `host.arch` | `virNodeInfo.type` | `virNodeGetInfo()` | Architecture string |
| `virtualization.system.name` | *static* | — | Hardcode `kvm` |
| `virtualization.platform.serial_number` | `dmidecode -s system-serial-number` | SMBIOS | Vendor serial, if available |
| `virtualization.platform.firmware.version` | `dmidecode -s bios-version` | SMBIOS | BIOS version |

### 2.2 `virtualization.vm` — libvirt Domain

| OTel Attribute | libvirt Source | API | Notes |
|---|---|---|---|
| `virtualization.vm.id` *(identity)* | `virDomainGetUUIDString()` | `virDomain` | UUID assigned at domain creation, e.g. `8c3f2a1b-4d56-4e78-9f01-2a3b4c5d6e7f` |
| `virtualization.vm.name` | `virDomainGetName()` | `virDomain` | Human-readable domain name, e.g. `prod-db-01` |
| `virtualization.vm.state` | `virDomainGetState()` → `virDomainState` | `virDomain` | `VIR_DOMAIN_RUNNING` → `running`, `VIR_DOMAIN_SHUTOFF` → `stopped`, `VIR_DOMAIN_PAUSED` → `paused` |
| `virtualization.vm.cpu.count` | `virDomainGetInfo().nrVirtCpu` | `virDomain` | Current active vCPU count |
| `virtualization.vm.memory.size` | `virDomainGetInfo().maxMem / 1024` | `virDomain` | Max memory in KB → MiB |
| `virtualization.vm.machine_type` | `<os><type machine="...">` in domain XML | `virDomainGetXMLDesc()` | e.g. `pc-i440fx-7.2`, `s390-ccw-virtio` |
| `virtualization.vm.nested_virtualization.enabled` | `<cpu mode="host-passthrough">` or `vmx`/`svm` CPU feature in domain XML | `virDomainGetXMLDesc()` | Present if `vmx` (Intel) or `svm` (AMD) feature flag in `<cpu><feature policy="require" name="vmx"/>` |
| `virtualization.system.name` | *static* | — | `kvm` |
| `virtualization.vm.node.name` | `virConnectGetHostname()` | libvirt connection | In standalone KVM: the KVM host's own hostname |

### 2.3 `virtualization.vswitch` — Linux Bridge / OVS

| OTel Attribute | Source | API | Notes |
|---|---|---|---|
| `virtualization.vswitch.name` *(identity)* | `virNetworkGetName()` | `virNetwork` | libvirt network name, e.g. `default`, `br-internal` |
| `virtualization.vswitch.id` | `virNetworkGetUUIDString()` | `virNetwork` | UUID of the libvirt network object |
| `virtualization.system.name` | *static* | — | `kvm` |

### 2.4 `virtualization.storage_pool` — libvirt Storage Pool

| OTel Attribute | Source | API | Notes |
|---|---|---|---|
| `virtualization.storage_pool.name` *(identity)* | `virStoragePoolGetName()` | `virStoragePool` | e.g. `default`, `FCP-POOL-A` |
| `virtualization.storage_pool.id` | `virStoragePoolGetUUIDString()` | `virStoragePool` | UUID of the pool |
| `virtualization.system.name` | *static* | — | `kvm` |

### 2.5 `virtualization.hypervisor` — libvirt Daemon

| OTel Attribute | Source | API | Notes |
|---|---|---|---|
| `virtualization.hypervisor.id` *(identity)* | `virConnectGetURI()` + hostname | `virConnect` | Construct as `kvm://` + hostname |
| `virtualization.hypervisor.version` | `virConnectGetVersion()` | `virConnect` | KVM/QEMU version integer, e.g. `8002000` → `8.2.0` |
| `virtualization.hypervisor.type` | *static* | — | `type1` |
| `virtualization.hypervisor.state` | connectivity check | — | `active` if `virConnectOpen()` succeeds |
| `virtualization.system.name` | *static* | — | `kvm` |

---

## 3. Comprehensive Signal Mapping

### 3.1 Virtual Machine CPU Metrics

| OTel Metric Name | Instrument | Unit | Target Entity | libvirt API | libvirt-exporter Metric | Transformation | Notes |
|---|---|---|---|---|---|---|---|
| `virtualization.vm.cpu.utilization` | gauge | `1` | `virtualization.vm` | `virDomainGetCPUStats(totalcpustats=true)` → `cpu_time` (nanoseconds) | `libvirt_domain_vcpu_cpu_time_seconds_total` | `Δcpu_time_ns / (elapsed_ns × nrVirtCpu)` | Sum `cpu_time` across all vCPUs; divide by elapsed real nanoseconds × vCPU count to get 0–1 utilization ratio. |
| `virtualization.vm.cpu.steal_time` | gauge | `1` | `virtualization.vm` | `virDomainGetCPUStats()` → `steal_time` | `libvirt_domain_vcpu_steal_time_seconds_total` | `Δsteal_time_ns / (elapsed_ns × nrVirtCpu)` | Available on KVM hosts with `CONFIG_PARAVIRT_SPINLOCKS`; steal = time hypervisor ran other guests while this domain was runnable. |
| `virtualization.vm.cpu.ready_time` | gauge | `1` | `virtualization.vm` | `virDomainGetCPUStats()` → `wait_time` | `libvirt_domain_vcpu_wait_time_seconds_total` | `Δwait_time_ns / (elapsed_ns × nrVirtCpu)` | vCPU wait time is the closest libvirt analogue to vSphere ready time. |
| `virtualization.vm.cpu.count` | updowncounter | `{vcpu}` | `virtualization.vm` | `virDomainGetInfo().nrVirtCpu` | `libvirt_domain_info_virtual_cpus` | — | Static property from domain info. |
| `system.cpu.time` (refined) | counter | `s` | `virtualization.vm` | `virDomainGetCPUStats()` per-vCPU | `libvirt_domain_vcpu_cpu_time_seconds_total{cpu="N"}` | `cpu_time_ns / 1e9` | Per-vCPU CPU time counter. `cpu.mode` set to `system` or `user` if OS stats available. |

### 3.2 Virtual Machine Memory Metrics

| OTel Metric Name | Instrument | Unit | Target Entity | libvirt API | libvirt-exporter Metric | Transformation | Notes |
|---|---|---|---|---|---|---|---|
| `virtualization.vm.memory.allocated` | gauge | `MiBy` | `virtualization.vm` | `virDomainMemoryStats()` → `actual` | `libvirt_domain_memory_stats_actual_balloon_bytes` | `value_KB / 1024` | `actual` = current balloon-adjusted allocation in KB. |
| `virtualization.vm.memory.used` | gauge | `MiBy` | `virtualization.vm` | `virDomainMemoryStats()` → `actual - usable` | `libvirt_domain_memory_stats_actual_balloon_bytes - libvirt_domain_memory_stats_usable_bytes` | `value_KB / 1024` | `usable` = memory available to guest (not in active use). |
| `virtualization.vm.memory.balloon` | gauge | `MiBy` | `virtualization.vm` | `virDomainMemoryStats()` → `balloon` | `libvirt_domain_memory_stats_actual_balloon_bytes` (delta from max) | `(max_KB - actual_KB) / 1024` | Balloon inflation = reduction from configured max. A non-zero value means host reclaimed memory. |
| `virtualization.vm.memory.swapped` | gauge | `MiBy` | `virtualization.vm` | `virDomainMemoryStats()` → `swap_in` | `libvirt_domain_memory_stats_swap_in_bytes` | `value_KB / 1024` | Bytes swapped into guest from host swap space. |
| `virtualization.vm.memory.rss` | gauge | `MiBy` | `virtualization.vm` | `virDomainMemoryStats()` → `rss` | `libvirt_domain_memory_stats_rss_bytes` | `value_KB / 1024` | True host-side RSS: physical pages backing this domain on the KVM host. |

**libvirt memory statistics key reference:**

| `virDomainMemoryStat.tag` | Description | OTel metric target |
|---|---|---|
| `VIR_DOMAIN_MEMORY_STAT_SWAP_IN` (1) | Bytes swapped in since domain start | `virtualization.vm.memory.swapped` |
| `VIR_DOMAIN_MEMORY_STAT_SWAP_OUT` (2) | Bytes swapped out since domain start | — |
| `VIR_DOMAIN_MEMORY_STAT_ACTUAL_BALLOON` (5) | Current balloon allocation in KB | `virtualization.vm.memory.allocated` |
| `VIR_DOMAIN_MEMORY_STAT_RSS` (6) | Host RSS in KB (physical pages) | `virtualization.vm.memory.rss` |
| `VIR_DOMAIN_MEMORY_STAT_USABLE` (8) | Available memory in balloon allocation | Used to derive `virtualization.vm.memory.used` |
| `VIR_DOMAIN_MEMORY_STAT_AVAILABLE` (9) | Total available memory in guest | — |

### 3.3 Virtual Machine Disk I/O Metrics

| OTel Metric Name | Instrument | Unit | Target Entity | libvirt API | libvirt-exporter Metric | Transformation | Notes |
|---|---|---|---|---|---|---|---|
| `virtualization.vm.disk.io` (read) | counter | `By` | `virtualization.vm` | `virDomainBlockStats().rd_bytes` | `libvirt_domain_block_stats_read_bytes_total` | — | Cumulative bytes read from virtual disk. Set `virtualization.vm.disk.direction=read`. |
| `virtualization.vm.disk.io` (write) | counter | `By` | `virtualization.vm` | `virDomainBlockStats().wr_bytes` | `libvirt_domain_block_stats_write_bytes_total` | — | Cumulative bytes written. Set `virtualization.vm.disk.direction=write`. |
| `virtualization.vm.disk.operations` (read) | counter | `{operation}` | `virtualization.vm` | `virDomainBlockStats().rd_req` | `libvirt_domain_block_stats_read_requests_total` | — | Cumulative read operations. |
| `virtualization.vm.disk.operations` (write) | counter | `{operation}` | `virtualization.vm` | `virDomainBlockStats().wr_req` | `libvirt_domain_block_stats_write_requests_total` | — | Cumulative write operations. |
| `virtualization.vm.disk.latency.time` (read) | counter | `s` | `virtualization.vm` | `virDomainBlockStats().rd_total_times` (ns) | `libvirt_domain_block_stats_read_time_seconds_total` | `value_ns / 1e9` | Total read latency in nanoseconds → seconds. Set `virtualization.vm.disk.direction=read`. |
| `virtualization.vm.disk.latency.time` (write) | counter | `s` | `virtualization.vm` | `virDomainBlockStats().wr_total_times` (ns) | `libvirt_domain_block_stats_write_time_seconds_total` | `value_ns / 1e9` | Total write latency. Set `virtualization.vm.disk.direction=write`. |
| `virtualization.vm.disk.errors` | counter | `{error}` | `virtualization.vm` | `virDomainBlockStats().errs` | `libvirt_domain_block_stats_errors_total` | — | I/O errors on the virtual disk. |

**Per-disk attribute binding:**
- `virtualization.vm.disk.name` = `virDomainGetXMLDesc()` → `<disk><target dev="vda"/>` device path, e.g. `vda`, `vdb`, `sda`.

### 3.4 Virtual Machine Network I/O Metrics

| OTel Metric Name | Instrument | Unit | Target Entity | libvirt API | libvirt-exporter Metric | Transformation | Notes |
|---|---|---|---|---|---|---|---|
| `virtualization.vm.network.io` (rx) | counter | `By` | `virtualization.vm` | `virDomainInterfaceStats().rx_bytes` | `libvirt_domain_interface_stats_receive_bytes_total` | — | Cumulative bytes received by vNIC. Set `network.io.direction=receive`. |
| `virtualization.vm.network.io` (tx) | counter | `By` | `virtualization.vm` | `virDomainInterfaceStats().tx_bytes` | `libvirt_domain_interface_stats_transmit_bytes_total` | — | Cumulative bytes transmitted. Set `network.io.direction=transmit`. |
| `system.network.io` (refined) | counter | `By` | `virtualization.vm` / `virtualization.vswitch` | `virDomainInterfaceStats()` | `libvirt_domain_interface_stats_receive_bytes_total` | — | Bound via `refinement.virtualization.system.network.io`; add `virtualization.vswitch.name` attribute. |
| `system.network.packet.dropped` (refined) | counter | `{packet}` | `virtualization.vm` | `virDomainInterfaceStats().rx_drop` / `tx_drop` | `libvirt_domain_interface_stats_receive_drops_total` | — | Dropped packets (NIC queue full). |
| `system.network.errors` (refined) | counter | `{error}` | `virtualization.vm` | `virDomainInterfaceStats().rx_errs` / `tx_errs` | `libvirt_domain_interface_stats_receive_errors_total` | — | NIC error count. |

**Per-NIC attribute binding:**
- `virtualization.vm.network.interface.name` = `virDomainGetXMLDesc()` → `<interface><target dev="vnet0"/>` interface name.
- `virtualization.vswitch.name` = the libvirt network name the interface is connected to, from `<interface><source network="default"/>`.

### 3.5 Storage Pool Metrics

| OTel Metric Name | Instrument | Unit | Target Entity | libvirt API | libvirt-exporter Metric | Transformation | Notes |
|---|---|---|---|---|---|---|---|
| `virtualization.storage_pool.capacity.used` | gauge | `By` | `virtualization.storage_pool` | `virStoragePoolGetInfo().allocation` | `libvirt_pool_info_allocation_bytes` | — | Bytes allocated within the pool. |
| `virtualization.storage_pool.capacity.available` | gauge | `By` | `virtualization.storage_pool` | `virStoragePoolGetInfo().available` | `libvirt_pool_info_available_bytes` | — | Bytes available for new volumes. |

`virStoragePoolGetInfo()` returns three fields: `capacity` (total), `allocation` (used), `available` (free).

### 3.6 Hypervisor Metrics

| OTel Metric Name | Instrument | Unit | Target Entity | libvirt / Linux Source | Derivation | Notes |
|---|---|---|---|---|---|---|
| `virtualization.hypervisor.memory.overcommit_ratio` | gauge | `1` | `virtualization.hypervisor` | `virNodeGetInfo().memory` + `sum(virDomainGetInfo().maxMem)` | `sum_max_memory_KB / node_memory_KB` | `libvirt_node_memory_stats_total_bytes` from libvirt-exporter; sum `libvirt_domain_info_maximum_memory_bytes` across all domains. |
| `virtualization.platform.cpu.utilization` | gauge | `1` | `virtualization.platform` | `/proc/stat` via hostmetrics | `(total - idle) / total` | Standard Linux CPU utilization via OTel hostmetricsreceiver. |
| `virtualization.platform.memory.total` | gauge | `MiBy` | `virtualization.platform` | `virNodeGetInfo().memory` | `value_KB / 1024` | Total physical RAM on the KVM host. |
| `virtualization.platform.memory.used` | gauge | `MiBy` | `virtualization.platform` | `/proc/meminfo` `MemTotal - MemAvailable` | `value_KB / 1024` | Host OS memory in use. |
| `virtualization.platform.vm.count` | updowncounter | `{vm}` | `virtualization.platform` | `virConnectListAllDomains()` | count | Count of active (running) domains. |

---

## 4. Kernel & cgroup Instrumentation Details

### 4.1 Host `/proc` and `/sys` Metrics via `system.*` Refinements

The host-level `system.*` metrics (CPU, memory, disk, network) collected by the OTel
`hostmetricsreceiver` or `node_exporter` flow to the `virtualization.platform` entity through the
`host` entity refinement lineage:

```
hostmetricsreceiver
  → system.cpu.utilization (instrument: gauge, unit: "1")
      → refinement.virtualization.system.cpu.utilization
          → entity_associations: [virtualization.platform, virtualization.partition, virtualization.vm]
```

For **per-domain metrics** (guest OS stats), the OTel Collector is deployed **inside** the guest VM
(i.e., the libvirt domain), where the `hostmetricsreceiver` collects standard Linux `/proc` metrics.
The guest's collector instance sets `virtualization.vm.id` and `virtualization.system.name=kvm` as
resource attributes to anchor the signal on the correct `virtualization.vm` entity.

### 4.2 cgroup v2 Integration for CPU Throttling

KVM domains run under cgroup v2 hierarchies in modern Linux hosts
(`/sys/fs/cgroup/machine.slice/machine-<domain>.scope/`). CPU quota and period constraints are
visible at:

```
/sys/fs/cgroup/machine.slice/machine-<domain>.scope/cpu.max
```

These values expose host-side CPU throttling information that supplements the libvirt
`virDomainGetCPUStats()` data:

| cgroup v2 File | Content | OTel use |
|---|---|---|
| `cpu.stat` → `nr_throttled` | Number of throttled intervals | Contributes to `virtualization.vm.cpu.ready_time` |
| `cpu.stat` → `throttled_usec` | Total throttled time in µs | `Δthrottled_usec / (elapsed_µs × vCPU_count)` → ready time ratio |
| `memory.current` | Current memory usage in bytes | Cross-check for `virtualization.vm.memory.rss` |
| `memory.swap.current` | Current swap usage in bytes | Cross-check for `virtualization.vm.memory.swapped` |

### 4.3 KVM on IBM Z (KVM on z Systems)

On IBM Z or LinuxONE systems, KVM runs as a variant called "KVM on z Systems" or "KVM for IBM Z."
The entity mapping remains identical (`virtualization.system.name = "kvm"`), but the processor
architecture is `s390x`. Key differences:

| Feature | x86 KVM | IBM Z KVM |
|---|---|---|
| Steal time API | `virDomainGetCPUStats().steal_time` | Available via `VIR_DOMAIN_CPU_STATS_STEALTIME` |
| CPU features | `vmx`/`svm` | `sie` (Start Interpretive Execution) |
| Machine type | `pc-i440fx-7.2` | `s390-ccw-virtio` |
| `host.arch` | `amd64` | `s390x` |
| vNIC types | `virtio-net`, `e1000` | `virtio-net`, `qeth` |

---

## 5. Collector Pipeline

### 5.1 libvirt-exporter + Prometheus Receiver

The `libvirt-exporter` (community project at `aleksei-burlakov/libvirt-exporter` or
`Tinkoff/libvirt-exporter`) scrapes all domain, pool, and node metrics from the libvirt socket.

**OTel Collector configuration skeleton:**

```yaml
receivers:
  prometheus:
    config:
      scrape_configs:
        - job_name: libvirt
          scrape_interval: 30s
          static_configs:
            - targets: ['localhost:9177']   # libvirt-exporter default port

  hostmetrics:
    collection_interval: 60s
    scrapers:
      cpu: {}
      memory: {}
      disk: {}
      network: {}

processors:
  # Map libvirt-exporter labels to OTel semantic convention attributes
  transform/libvirt_to_semconv:
    metric_statements:
      - context: datapoint
        statements:
          - set(attributes["virtualization.vm.id"],   attributes["uuid"])
          - set(attributes["virtualization.vm.name"], attributes["domain"])
          - set(attributes["virtualization.vm.disk.name"], attributes["target_device"])
          - set(attributes["virtualization.vm.network.interface.name"], attributes["interface"])
          - set(attributes["virtualization.system.name"], "kvm")
          - set(resource.attributes["host.name"], resource.attributes["instance"])

  # Rename libvirt-exporter metrics to OTel semconv names
  metricstransform:
    transforms:
      - include: libvirt_domain_block_stats_read_bytes_total
        action: insert
        new_name: virtualization.vm.disk.io
        operations:
          - action: add_label
            new_label: virtualization.vm.disk.direction
            new_value: read
      - include: libvirt_domain_block_stats_write_bytes_total
        action: insert
        new_name: virtualization.vm.disk.io
        operations:
          - action: add_label
            new_label: virtualization.vm.disk.direction
            new_value: write
      - include: libvirt_domain_interface_stats_receive_bytes_total
        action: insert
        new_name: virtualization.vm.network.io
        operations:
          - action: add_label
            new_label: network.io.direction
            new_value: receive
      - include: libvirt_domain_interface_stats_transmit_bytes_total
        action: insert
        new_name: virtualization.vm.network.io
        operations:
          - action: add_label
            new_label: network.io.direction
            new_value: transmit

exporters:
  otlp:
    endpoint: otel-collector-gateway:4317

service:
  pipelines:
    metrics:
      receivers: [prometheus, hostmetrics]
      processors: [transform/libvirt_to_semconv, metricstransform]
      exporters: [otlp]
```

### 5.2 eBPF-based Steal Time Collector (optional)

For environments where `virDomainGetCPUStats().steal_time` is not available, eBPF tracepoints on
`kvm_vcpu_wakeup` and `sched_stat_runtime` can provide per-domain steal and wait times. The
`inspektor-gadget` or custom BCC/bpftrace scripts can be used to export these as Prometheus counters
and relabelled to `virtualization.vm.cpu.steal_time` via the `metricstransformprocessor`.

---

## 6. KVM-Specific Caveats

| Topic | Detail |
|---|---|
| **Balloon driver requirement** | `virtualization.vm.memory.balloon` and `virtualization.vm.memory.rss` require the `virtio_balloon` kernel module inside the guest. Without it, libvirt reports `actual = max` (no ballooning) and RSS is not available. |
| **CPU steal time kernel support** | Steal time reporting from `virDomainGetCPUStats()` requires kernel `CONFIG_PARAVIRT_SPINLOCKS=y` on the host and `kvm-clock` or `pvpanic` device in the guest. |
| **Block device granularity** | `virDomainBlockStats()` operates at the virtual disk device level (e.g., `vda`), not the partition level. Use `virtualization.vm.disk.name` to identify the disk. |
| **Network interface naming** | libvirt assigns tap interfaces on the host side (e.g., `vnet0`, `vnet1`). The guest OS may use a different name (e.g., `eth0`, `enp1s0`). `virtualization.vm.network.interface.name` captures the host-side tap name; use `network.interface.name` inside the guest for the guest-side name. |
| **Live migration** | During live migration, `virDomainGetState()` returns `VIR_DOMAIN_RUNNING_MIGRATED` or `VIR_DOMAIN_RUNNING_MIGRATING`. The `virtualization.vm.state` enum maps both to `migrating`. `virtualization.vm.node.name` must be updated to the destination host after migration completes. |
| **Storage pool types** | libvirt supports pool types: `dir`, `fs`, `netfs`, `logical` (LVM), `disk`, `iscsi`, `rbd`, `gluster`. The `virtualization.storage_pool` entity is agnostic to the backing type; the pool type can be included as a `virtualization.storage_pool.id` annotation if needed. |
| **IBM Z storage** | On KVM for IBM Z, storage volumes often use `virtio-blk` or direct DASD passthrough. DASD devices appear as `vda` / `sda` in the guest; the libvirt block stats API applies unchanged. |
