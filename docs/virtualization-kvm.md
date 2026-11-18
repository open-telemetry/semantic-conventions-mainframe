# Virtualization Semantic Conventions — KVM / libvirt Implementation Guide

> **Scope:** This document describes how the OpenTelemetry semantic conventions defined in
> `model/virtualization/` map to KVM / libvirt / QEMU telemetry sources. Entity types, attribute
> keys and metric names are those of the `definition/2` YAML files; the generated pages under
> [docs/registry/virtualization/](registry/virtualization/README.md) are authoritative for
> instruments, units and attributes.

---

## 1. Architecture Overview

KVM (Kernel-based Virtual Machine) is a Linux kernel module that turns the host kernel into a
Type-1 hypervisor. Guest domains are managed by the `libvirt` management library, which drives
the QEMU device emulation layer. The mapping to OTel virtualization entities is:

```text
Linux Host (kernel + KVM module)                    → virtualization.platform  (virtualization.system.name = "kvm")
└── libvirt daemon (libvirtd / virtqemud)           → virtualization.hypervisor
    ├── virDomain[] — guest domains                 → virtualization.vm
    │   ├── virDomainGetCPUStats() / vCPU stats     → virtualization.vm.cpu.*
    │   ├── virDomainMemoryStats()                  → virtualization.vm.memory.*
    │   ├── virDomainBlockStats() [per disk]        → virtualization.vm.disk.*    (attr: virtualization.vm.disk.name)
    │   └── virDomainInterfaceStats() [per NIC]     → virtualization.vm.network.io (attr: virtualization.vm.network.interface.name)
    ├── virNetwork[] — virtual networks
    │   └── Linux bridge / Open vSwitch bridge      → virtualization.vswitch
    └── virStoragePool[] — storage pools
        └── virStoragePoolGetInfo()                 → virtualization.storage_pool
```

**Key design decisions:**

- The Linux host that runs KVM maps to `virtualization.platform`, identified by the host machine
  ID. Its `virtualization.system.name` is `kvm`. (On IBM Z the physical platform is the CPC; see
  §4.3.)
- `virtualization.hypervisor` represents the libvirt-managed hypervisor on the host, identified by
  the libvirt host UUID. It carries hypervisor-level metrics such as the memory overcommit ratio.
- Each libvirt domain maps to `virtualization.vm`, identified by the domain UUID. The UUID does not
  change when the domain is live-migrated to another host.
- Linux bridges or Open vSwitch bridges backing libvirt virtual networks map to
  `virtualization.vswitch`, identified by the host machine ID and the bridge name.
- libvirt storage pools map to `virtualization.storage_pool`, identified by the pool UUID.
- `virtualization.partition` does not apply to a standard KVM environment (no firmware
  partitioning).
- `virtualization.cluster` applies when KVM hosts are managed by a cluster manager such as oVirt,
  Proxmox VE or OpenStack Nova; the attribute definitions do not define an identifier fill rule
  for these yet.

---

## 2. Entity Instance Construction

### 2.1 `virtualization.platform` — KVM Host

| OTel Attribute | libvirt / Linux Source | API / Path | Notes |
| --- | --- | --- | --- |
| `virtualization.platform.id` *(identity)* | Host machine ID | `/etc/machine-id` | e.g. `4c4c45440042351080580b4c04f4e373` |
| `host.id` | same value | `/etc/machine-id` | SHOULD equal `virtualization.platform.id` |
| `host.name` | `virConnectGetHostname()` | libvirt connection | e.g. `kvm-host-01`; descriptive |
| `host.type` | `dmidecode -s system-product-name` | SMBIOS | Server model |
| `host.arch` | `uname -m`, mapped to the `host.arch` values | kernel | e.g. `amd64`, `arm64`, `s390x` |
| `virtualization.system.name` | *static* | — | `kvm` |
| `virtualization.platform.serial_number` | `dmidecode -s system-serial-number` | SMBIOS | Vendor serial, if available |
| `virtualization.platform.firmware.version` | `dmidecode -s bios-version` | SMBIOS | BIOS version |

### 2.2 `virtualization.hypervisor` — libvirt-managed Hypervisor

| OTel Attribute | Source | API | Notes |
| --- | --- | --- | --- |
| `virtualization.hypervisor.id` *(identity)* | libvirt host UUID | `<host><uuid>` in the `virConnectGetCapabilities()` XML | |
| `virtualization.hypervisor.version` | `virConnectGetVersion()` | `virConnect` | Encoded version, e.g. `8002000` → `8.2.0` |
| `virtualization.hypervisor.type` | *static* | — | `type1` |
| `virtualization.hypervisor.state` | connectivity check | — | `active` if `virConnectOpen()` succeeds |
| `virtualization.system.name` | *static* | — | `kvm` |

### 2.3 `virtualization.vm` — libvirt Domain

| OTel Attribute | libvirt Source | API | Notes |
| --- | --- | --- | --- |
| `virtualization.vm.id` *(identity)* | `virDomainGetUUIDString()` | `virDomain` | Domain UUID, e.g. `8c3f2a1b-4d56-4e78-9f01-2a3b4c5d6e7f`; unchanged by live migration |
| `virtualization.vm.name` | `virDomainGetName()` | `virDomain` | e.g. `prod-db-01` |
| `virtualization.vm.state` | `virDomainGetState()` | `virDomain` | `VIR_DOMAIN_RUNNING` → `running`, `VIR_DOMAIN_SHUTOFF` → `stopped`, `VIR_DOMAIN_PAUSED` → `paused`; see §6 for migration |
| `virtualization.vm.cpu.count` | `virDomainGetInfo().nrVirtCpu` | `virDomain` | Current vCPU count |
| `virtualization.vm.memory.size` | `virDomainGetInfo().maxMem / 1024` | `virDomain` | KiB → MiB (the attribute is defined in MiB) |
| `virtualization.vm.machine_type` | `<os><type machine="...">` in the domain XML | `virDomainGetXMLDesc()` | e.g. `pc-q35-8.2`, `s390-ccw-virtio` |
| `virtualization.vm.nested_virtualization.enabled` | CPU definition in the domain XML | `virDomainGetXMLDesc()` | x86: `host-passthrough` CPU mode, or the `vmx` (Intel) / `svm` (AMD) feature required in `<cpu>` |
| `virtualization.vm.node.name` | `virConnectGetHostname()` | libvirt connection | The host the domain currently runs on |
| `virtualization.system.name` | *static* | — | `kvm` |

### 2.4 `virtualization.vswitch` — Linux Bridge / Open vSwitch

| OTel Attribute | Source | API | Notes |
| --- | --- | --- | --- |
| `virtualization.vswitch.id` *(identity)* | Host machine ID + `/` + bridge name | `/etc/machine-id`, `virNetworkGetBridgeName()` or the OVS bridge name | e.g. `4c4c45440042351080580b4c04f4e373/virbr0` |
| `virtualization.vswitch.name` | `virNetworkGetName()`, or the bridge name for bridges without a libvirt network | `virNetwork` | e.g. `default`, `br-internal` |
| `virtualization.system.name` | *static* | — | `kvm` |

### 2.5 `virtualization.storage_pool` — libvirt Storage Pool

| OTel Attribute | Source | API | Notes |
| --- | --- | --- | --- |
| `virtualization.storage_pool.id` *(identity)* | `virStoragePoolGetUUIDString()` | `virStoragePool` | Pool UUID |
| `virtualization.storage_pool.name` | `virStoragePoolGetName()` | `virStoragePool` | e.g. `default`, `FCP-POOL-A` |
| `virtualization.system.name` | *static* | — | `kvm` |

---

## 3. Signal Mapping

The exporter metric names refer to the `libvirt-exporter` described in §5.1; it already converts
nanoseconds to seconds and KiB to bytes.

### 3.1 Virtual Machine CPU Metrics

| OTel Metric Name | Instrument | Unit | libvirt API | libvirt-exporter Metric | Transformation | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `virtualization.vm.cpu.utilization` | gauge | `1` | `virDomainGetCPUStats()` total `cpu_time` (ns) | `libvirt_domain_info_cpu_time_seconds_total` | `Δcpu_time / (Δt × nrVirtCpu)` | CPU time of all vCPUs divided by elapsed time × vCPU count. |
| `virtualization.vm.cpu.steal_time` | counter | `s` | `vcpu.<n>.delay` (ns), summed over vCPUs | `libvirt_domain_vcpu_delay_seconds_total` | `ns / 1e9` | Time a runnable vCPU waited for a host CPU; libvirt exposes it to the guest as steal time. Requires libvirt 7.2.0 or later. |
| `virtualization.vm.cpu.ready_time` | counter | `s` | — | — | — | No separate source: libvirt's `vcpu.<n>.wait` and `vcpu.<n>.delay` both measure run-queue time. Report it once, as `virtualization.vm.cpu.steal_time`. |
| `virtualization.vm.cpu.count` | updowncounter | `{vcpu}` | `virDomainGetInfo().nrVirtCpu` | `libvirt_domain_info_virtual_cpus` | — | |

### 3.2 Virtual Machine Memory Metrics

| OTel Metric Name | Instrument | Unit | libvirt API | libvirt-exporter Metric | Transformation | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `virtualization.vm.memory.allocated` | gauge | `By` | `virDomainMemoryStats()` → `actual` (KiB) | `libvirt_domain_memory_stats_actual_balloon_bytes` | `value_KiB * 1024` | Current balloon-adjusted allocation. |
| `virtualization.vm.memory.used` | gauge | `By` | `actual` − `usable` (KiB) | `libvirt_domain_memory_stats_actual_balloon_bytes - libvirt_domain_memory_stats_usable_bytes` | `value_KiB * 1024` | `usable` is memory the balloon can reclaim without host swapping. |
| `virtualization.vm.memory.balloon` | gauge | `By` | `maxMem` − `actual` (KiB) | `libvirt_domain_info_maximum_memory_bytes - libvirt_domain_memory_stats_actual_balloon_bytes` | `value_KiB * 1024` | Non-zero means the host has reclaimed memory. |
| `virtualization.vm.memory.swapped` | gauge | `By` | cgroup `memory.swap.current` of the domain | — | — | Host swap used by the domain; see §4.2. libvirt's `swap_in` / `swap_out` describe swapping inside the guest, not hypervisor swap. |
| `virtualization.vm.memory.rss` | gauge | `By` | `virDomainMemoryStats()` → `rss` (KiB) | `libvirt_domain_memory_stats_rss_bytes` | `value_KiB * 1024` | Physical host pages backing the domain. |

**libvirt memory statistics reference:**

| `virDomainMemoryStat` tag | Description | OTel use |
| --- | --- | --- |
| `VIR_DOMAIN_MEMORY_STAT_ACTUAL_BALLOON` | Current balloon value (KiB) | `virtualization.vm.memory.allocated` |
| `VIR_DOMAIN_MEMORY_STAT_USABLE` | Memory the balloon can reclaim without host swapping (KiB) | Derives `virtualization.vm.memory.used` |
| `VIR_DOMAIN_MEMORY_STAT_RSS` | Resident set size of the domain's QEMU process (KiB) | `virtualization.vm.memory.rss` |
| `VIR_DOMAIN_MEMORY_STAT_AVAILABLE` | Usable memory as seen by the guest (KiB) | — |
| `VIR_DOMAIN_MEMORY_STAT_SWAP_IN` / `SWAP_OUT` | Data read from / written to swap inside the guest (KiB) | — |

### 3.3 Virtual Machine Disk I/O Metrics

| OTel Metric Name | Instrument | Unit | libvirt API | libvirt-exporter Metric | Transformation | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `virtualization.vm.disk.io` (read) | counter | `By` | `virDomainBlockStats().rd_bytes` | `libvirt_domain_block_stats_read_bytes_total` | — | Set `virtualization.vm.disk.direction=read`. |
| `virtualization.vm.disk.io` (write) | counter | `By` | `virDomainBlockStats().wr_bytes` | `libvirt_domain_block_stats_write_bytes_total` | — | Set `virtualization.vm.disk.direction=write`. |
| `virtualization.vm.disk.operations` (read) | counter | `{operation}` | `virDomainBlockStats().rd_req` | `libvirt_domain_block_stats_read_requests_total` | — | |
| `virtualization.vm.disk.operations` (write) | counter | `{operation}` | `virDomainBlockStats().wr_req` | `libvirt_domain_block_stats_write_requests_total` | — | |
| `virtualization.vm.disk.latency.time` (read) | counter | `s` | `rd_total_times` (ns) | `libvirt_domain_block_stats_read_time_seconds_total` | `ns / 1e9` | Set `virtualization.vm.disk.direction=read`. |
| `virtualization.vm.disk.latency.time` (write) | counter | `s` | `wr_total_times` (ns) | `libvirt_domain_block_stats_write_time_seconds_total` | `ns / 1e9` | Set `virtualization.vm.disk.direction=write`. |
| `virtualization.vm.disk.errors` | counter | `{error}` | — | — | — | libvirt reports the block `errs` field only for Xen; there is no per-disk error counter for KVM/QEMU. Omit. |

**Per-disk attribute binding:** `virtualization.vm.disk.name` is the target device from the domain
XML (`<disk><target dev="vda"/>`), e.g. `vda`, `vdb`, `sda`; the exporter label is
`target_device`.

### 3.4 Virtual Machine Network I/O Metrics

| OTel Metric Name | Instrument | Unit | libvirt API | libvirt-exporter Metric | Transformation | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `virtualization.vm.network.io` (receive) | counter | `By` | `virDomainInterfaceStats().rx_bytes` | `libvirt_domain_interface_stats_receive_bytes_total` | — | Set `network.io.direction=receive`. |
| `virtualization.vm.network.io` (transmit) | counter | `By` | `virDomainInterfaceStats().tx_bytes` | `libvirt_domain_interface_stats_transmit_bytes_total` | — | Set `network.io.direction=transmit`. |
| `system.network.packet.dropped` (refined) | counter | `{packet}` | `rx_drop` / `tx_drop` | `libvirt_domain_interface_stats_receive_drops_total`, `..._transmit_drops_total` | — | Associated with `virtualization.vm` by `refinement.virtualization.system.network.packet.dropped`. |
| `system.network.errors` (refined) | counter | `{error}` | `rx_errs` / `tx_errs` | `libvirt_domain_interface_stats_receive_errors_total`, `..._transmit_errors_total` | — | Associated by `refinement.virtualization.system.network.errors`. |

**Per-NIC attribute binding:**

- `virtualization.vm.network.interface.name` is the host-side target device from the domain XML
  (`<interface><target dev="vnet0"/>`); the exporter label is `target_device`.
- `virtualization.vswitch.name` (opt-in on the `system.network.*` refinements) is the libvirt
  network or bridge the interface is connected to (`<interface><source network="default"/>` or
  `<source bridge="br0"/>`); the exporter reports it as `source_bridge` on
  `libvirt_domain_interface_meta`.

### 3.5 Storage Pool Metrics

| OTel Metric Name | Instrument | Unit | libvirt API | libvirt-exporter Metric | Transformation | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `virtualization.storage_pool.used` | updowncounter | `By` | `virStoragePoolGetInfo().allocation` | `libvirt_pool_info_allocation_bytes` | — | Bytes allocated within the pool. |
| `virtualization.storage_pool.available` | updowncounter | `By` | `virStoragePoolGetInfo().available` | `libvirt_pool_info_available_bytes` | — | Bytes available for new volumes. |

`virStoragePoolGetInfo()` returns `capacity` (total), `allocation` (used) and `available` (free).

### 3.6 Hypervisor and Platform Metrics

| OTel Metric Name | Instrument | Unit | libvirt / Linux Source | Derivation | Notes |
| --- | --- | --- | --- | --- | --- |
| `virtualization.hypervisor.memory.overcommit_ratio` | gauge | `1` | `sum(virDomainGetInfo().maxMem)` and `virNodeGetInfo().memory` | `sum_maxMem_KiB / node_memory_KiB` | From the exporter: sum of `libvirt_domain_info_maximum_memory_bytes` divided by the host memory. |
| `virtualization.platform.cpu.utilization` | gauge | `1` | `/proc/stat` | `(total - idle) / total` | For example from the collector's `hostmetrics` receiver. |
| `virtualization.platform.memory.total` | gauge | `By` | `virNodeGetInfo().memory` (KiB) | `value_KiB * 1024` | Physical memory of the host. |
| `virtualization.platform.memory.used` | gauge | `By` | `/proc/meminfo` `MemTotal - MemAvailable` (KiB) | `value_KiB * 1024` | |
| `virtualization.platform.vm.count` | updowncounter | `{vm}` | `virConnectListAllDomains()` | count per state | Set `virtualization.platform.vm.state` (`running`, `stopped`, `paused`, or `all`). |

---

## 4. Kernel & cgroup Instrumentation Details

### 4.1 Host and Guest `system.*` Metrics

The host-level `system.*` metrics (CPU, memory, disk, network) collected by the collector's
`hostmetrics` receiver or by `node_exporter` describe the KVM host. The host is a
`virtualization.platform`, which refines the upstream `host` entity:

```text
hostmetrics receiver (on the KVM host)
  → system.cpu.utilization (instrument: gauge, unit: "1")
      → refinement.virtualization.system.cpu.utilization
          → entity_associations: [virtualization.platform, virtualization.partition, virtualization.vm]
```

For the guest's own view, a collector runs **inside** the domain and collects the guest's `/proc`
metrics with the `hostmetrics` receiver. It sets `virtualization.vm.id` (the domain UUID) and
`virtualization.system.name=kvm` as resource attributes, so the signals describe the
`virtualization.vm` entity. On x86 guests, libvirt passes the domain UUID as the SMBIOS system
UUID, which the guest can read from `/sys/class/dmi/id/product_uuid`. The refinements
`refinement.virtualization.vm.system.uptime`, `refinement.virtualization.vm.system.memory.usage`,
`refinement.virtualization.vm.system.paging.faults` and
`refinement.virtualization.vm.system.filesystem.usage` associate these guest metrics with
`virtualization.vm`.

### 4.2 cgroup v2

KVM domains run in cgroup v2 scopes below `/sys/fs/cgroup/machine.slice/` on modern Linux hosts.
The scope of a domain exposes host-side resource accounting that supplements the libvirt data:

| cgroup v2 File | Content | OTel use |
| --- | --- | --- |
| `memory.swap.current` | Host swap used by the domain, in bytes | `virtualization.vm.memory.swapped` |
| `memory.current` | Host memory charged to the domain, in bytes | Cross-check for `virtualization.vm.memory.rss` |
| `cpu.stat` → `throttled_usec` | Time the domain was throttled by its CPU quota (`cpu.max`), in µs | No dedicated metric; explains CPU limits set by the operator |

### 4.3 KVM on IBM Z

On IBM Z and LinuxONE, KVM runs in a Linux instance in a logical partition (LPAR). The entity
mapping for guests is unchanged (`virtualization.system.name = "kvm"`, `virtualization.vm.id` =
domain UUID), but the physical platform is the Central Processing Complex (CPC):

| Feature | x86 KVM | KVM on IBM Z |
| --- | --- | --- |
| `virtualization.platform` | The KVM host (`virtualization.platform.id` = host machine ID) | The CPC (`virtualization.platform.id` = `<machine type>-<serial>`, e.g. `3931-45A01`); the KVM host is a `virtualization.hypervisor` running in a `virtualization.partition` |
| Steal time source | `vcpu.<n>.delay` | `vcpu.<n>.delay` |
| Hardware virtualization | Intel VT-x (`vmx`) / AMD-V (`svm`) | Start Interpretive Execution (SIE) |
| Machine type | e.g. `pc-q35-8.2` | `s390-ccw-virtio` |
| `host.arch` | `amd64` | `s390x` |
| vNIC model | `virtio-net`, `e1000` | `virtio-net` (CCW transport) |

---

## 5. Collector Pipeline

### 5.1 libvirt-exporter + Prometheus Receiver

The [libvirt-exporter](https://github.com/Tinkoff/libvirt-exporter) (the repository is archived)
reads domain, block, interface and storage pool statistics from the libvirt socket and exposes
them on port 9177. Most series carry the domain **name** (`domain` label) and the device
(`target_device`); the domain UUID appears only on `libvirt_domain_info_meta`. The collector
therefore cannot set `virtualization.vm.id` on each series with a simple label copy; join with
`libvirt_domain_info_meta` at query time, or use a collector component that reads the UUID from
libvirt directly.

**OTel Collector configuration skeleton** (runs on the KVM host):

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
  # Identify the KVM host. KVM_HOST_MACHINE_ID holds the content of /etc/machine-id.
  resource/kvm_host:
    attributes:
      - key: virtualization.platform.id
        value: ${env:KVM_HOST_MACHINE_ID}
        action: upsert
      - key: host.id
        value: ${env:KVM_HOST_MACHINE_ID}
        action: upsert
      - key: virtualization.system.name
        value: kvm
        action: upsert

  # Map libvirt-exporter labels to semantic convention attributes.
  transform/libvirt_to_semconv:
    metric_statements:
      - context: datapoint
        statements:
          - set(attributes["virtualization.vm.name"], attributes["domain"]) where attributes["domain"] != nil
          - set(attributes["virtualization.vm.disk.name"], attributes["target_device"]) where IsMatch(metric.name, "^libvirt_domain_block_stats_")
          - set(attributes["virtualization.vm.network.interface.name"], attributes["target_device"]) where IsMatch(metric.name, "^libvirt_domain_interface_stats_")

  # Rename libvirt-exporter metrics to semantic convention names.
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
      processors: [resource/kvm_host, transform/libvirt_to_semconv, metricstransform]
      exporters: [otlp]
```

The metric names the `prometheus` receiver produces depend on its name normalization settings
(for example whether the `_total` suffix of counters is kept); check them with the `debug`
exporter and adjust the `include` patterns. The `groupbyattrs` processor can move per-domain data
point attributes to resource attributes, so that each domain becomes its own resource.

### 5.2 Steal Time without `vcpu.<n>.delay`

With libvirt older than 7.2.0, `vcpu.<n>.delay` is not available. The second field of
`/proc/<pid>/task/<tid>/schedstat` of each vCPU thread of the QEMU process is the time the thread
waited on a run queue, in nanoseconds; summed over the vCPU threads it gives the same measure.

---

## 6. KVM-Specific Caveats

| Topic | Detail |
| --- | --- |
| **Balloon driver requirement** | `virtualization.vm.memory.balloon` and the guest-reported memory statistics (`usable`, `available`) require the `virtio_balloon` driver in the guest and a statistics period set on the domain. Without it, libvirt reports `actual` equal to the maximum (no ballooning). `rss` is measured on the host and is available without the driver. |
| **CPU steal time support** | `vcpu.<n>.delay` requires libvirt 7.2.0 or later and scheduler statistics (`CONFIG_SCHED_INFO`) in the host kernel. |
| **Disk errors** | libvirt has no per-disk error counter for KVM/QEMU; omit `virtualization.vm.disk.errors`. |
| **Block device granularity** | `virDomainBlockStats()` reports per virtual disk device (e.g. `vda`), not per partition. Use `virtualization.vm.disk.name` to identify the disk. |
| **Network interface naming** | libvirt creates tap interfaces on the host (e.g. `vnet0`); the guest uses its own names (e.g. `eth0`, `enp1s0`). `virtualization.vm.network.interface.name` carries the host-side tap name; use `network.interface.name` inside the guest for the guest-side name. |
| **Live migration** | The domain UUID, and with it `virtualization.vm.id`, does not change. While a migration is in progress, map the state reasons that indicate migration (for example `VIR_DOMAIN_PAUSED_MIGRATION`) to `migrating`. After the migration, `virtualization.vm.node.name` names the destination host. |
| **Storage pool types** | libvirt supports pool types such as `dir`, `fs`, `netfs`, `logical` (LVM), `disk`, `iscsi`, `rbd` and `gluster`. The `virtualization.storage_pool` entity is independent of the backing type, and the pool UUID identifies the pool for every type. |
| **IBM Z storage** | On KVM on IBM Z, guest disks often use `virtio-blk` on DASD or FCP-attached SCSI volumes. The guest sees them as `vda` / `sda`; the libvirt block statistics apply unchanged. |
