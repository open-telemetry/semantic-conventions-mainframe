# Mainframe Semantic Conventions — Visual Semantic Models & Architecture

> **Scope:** This document synthesises the entity model, metric associations, and cross-platform
> topology defined in `model/mainframe/` and `model/virtualization/` into modular Mermaid diagrams
> and an executive architecture summary for the IBM Z mainframe observability domain. All entity
> types, attribute keys, and metric names are exact references to the v2 YAML definitions in the
> repository.

---

## 1. Executive Summary

### Design Lessons & Trade-offs

The mainframe semantic conventions answer a single architectural question: *How do we describe
the full IBM Z compute stack — from a physical CPC drawer to a z/VM guest VM — using the same
unified entity model that also covers VMware vSphere, KVM, and OpenShift Virtualization?*

Seven key lessons shaped the final design:

**1. Two entities represent one physical machine.**
The Central Processor Complex (CPC) maps to two overlapping OTel entities: `mainframe.host`
(for environmental, power, and physical hardware metrics) and `virtualization.platform` (for
aggregate CPU, memory, and partition count metrics). Both reference the same CPC via `host.name`.
This dual-binding avoids duplicating physical hardware metrics on the platform entity while keeping
the `system.*` metrics on the standard virtualization entity hierarchy.

**2. `virtualization.partition` fills the firmware-partitioning gap.**
PR/SM Logical Partitions (LPARs) are enforced at the firmware level, not by software. They are
neither VMs (no software hypervisor) nor bare-metal hosts (they share physical hardware within
a sub-millisecond switching boundary). `virtualization.partition` is the entity type that models
this concept precisely, with composite identity (`partition.id` + `platform.id`) to handle
uniqueness within a CPC.

**3. The `ibm.prsm` discriminator enables single-label filtering.**
By setting `virtualization.system.name = "ibm.prsm"` on every PR/SM entity, any PromQL query
can isolate IBM Z PR/SM metrics with `{virtualization_system_name="ibm.prsm"}`. Similarly,
`ibm.zvm` isolates the z/VM layer. This eliminates the need for a separate mainframe entity
type for most queries.

**4. Processor type is a metric attribute, not an entity split.**
IBM Z has six physical processor types (CP, IFL, zIIP, ICF, SAP, IFP) — each assigned to
different workloads. Rather than creating separate entity types per processor type, the model
uses `mainframe.cpu.type` as a discriminating attribute on the `system.cpu.utilization` and
`mainframe.cpu.utilization` metrics. This keeps the entity count minimal while producing the
correct per-type time series.

**5. `mainframe.*` namespace captures what no upstream entity covers.**
Six entity types are genuinely unique to IBM Z infrastructure and have no upstream analogue:
`mainframe.host` (CPC physical hardware), `mainframe.cpu` (individual physical core),
`mainframe.channel` (CHPID I/O channel path), `mainframe.adapter` (crypto/flash/PCIe adapter),
`mainframe.port` (physical adapter port), and `mainframe.nic` (virtual partition-attached NIC).
All other entities reuse upstream `virtualization.*` types with the `ibm.prsm` or `ibm.zvm`
discriminator.

**6. Nested virtualization is an attribute pattern, not a new entity type.**
When z/VM runs inside a PR/SM LPAR, the model uses `virtualization.partition` for the LPAR
and `virtualization.hypervisor` for the z/VM CP instance — both referencing the same
`mainframe.host` via parent attribute traversal. No new entity type is needed for the nested
configuration. Correlate layers with `mainframe.host.name` as a shared resource attribute.

**7. 94 metrics, 11 entity types, minimal duplication.**
The complete mainframe model uses 24 base metric associations, 18 existing virtualization metric
refinements, 14 new mainframe-specific refinements, and 38 net-new `mainframe.*` metrics —
spread across 11 entity types. Every metric definition traces to exactly one target entity; no
metric is duplicated across entity types unless the physical signal genuinely occurs on multiple
resource layers.

---

## 2. CEC, LPAR & Partitioning ERD

The first diagram shows the physical CPC and firmware partitioning entities, including their
identity attributes, descriptive attributes, and `host` entity refinement lineage.

```mermaid
classDiagram
    class host_upstream["host (upstream)"] {
        +string host_name
        +string host_id
        +string host_type
        +string host_arch
    }

    class mf_host["mainframe.host"] {
        +string mainframe_host_name_IDENTITY
        +string mainframe_host_id
        +string mainframe_host_machine_type
        +string mainframe_host_machine_model
        +string mainframe_host_serial_number
    }

    class virt_platform["virtualization.platform"] {
        +string host_name_IDENTITY
        +string host_id
        +string host_type
        +string host_arch
        +enum system_name__ibm_prsm
        +string platform_id
        +string platform_serial_number
        +string platform_firmware_version
    }

    class virt_partition["virtualization.partition"] {
        +string partition_id_IDENTITY
        +string platform_id_IDENTITY
        +enum system_name__ibm_prsm
        +string partition_name
        +int partition_number
        +enum partition_type
        +enum partition_state
    }

    class mf_partition["mainframe.partition"] {
        +string mainframe_partition_id_IDENTITY
        +string mainframe_partition_name
    }

    class mf_cpu["mainframe.cpu"] {
        +string mainframe_cpu_id_IDENTITY
        +enum mainframe_cpu_type
        +enum mainframe_cpu_smt_mode
    }

    note for mf_host "identity: mainframe.host.name\ndesc: mainframe.host.id,\n  mainframe.host.machine.type,\n  mainframe.host.serial_number\nRefinement: host (upstream)"
    note for virt_platform "identity: host.name (= CPC name)\ndesc: host.id, host.type, host.arch,\n  virtualization.system.name,\n  virtualization.platform.id,\n  virtualization.platform.firmware.version\nDiscriminator: system.name = ibm.prsm"
    note for virt_partition "identity: virtualization.partition.id\n         + virtualization.platform.id\ndesc: system.name, partition.name,\n  partition.number, partition.type,\n  partition.state\nDiscriminator: system.name = ibm.prsm"
    note for mf_partition "identity: mainframe.partition.id\ndesc: mainframe.partition.name\nSpecialisation for IBM Z-specific\nreserved processor metrics"
    note for mf_cpu "identity: mainframe.cpu.id\ndesc: mainframe.cpu.type,\n  mainframe.cpu.smt_mode\nPhysical/logical core from HIS"

    %% Refinement lineage (entity_refinements: ref: host)
    mf_host        --|> host_upstream : refines host
    virt_platform  --|> host_upstream : refines host
    virt_partition --|> host_upstream : refines host

    %% Containment
    mf_host       "1" *-- "1..*" virt_platform : same CPC, different entity scope
    virt_platform "1" *-- "0..*" virt_partition : hosts LPARs
    virt_platform "1" *-- "0..*" mf_cpu : contains physical cores
    virt_partition "1" *-- "0..1" mf_partition : mainframe extensions
```

**Notes:**
- `[identity]` marks attributes in the entity `identity:` block — these uniquely identify an instance.
- `mf_host` and `virt_platform` represent the **same physical CPC** but serve different consumers:
  `mf_host` anchors environmental and hardware metrics; `virt_platform` anchors OS-level and
  partition management metrics.
- `virtualization.partition` uses composite identity (`partition.id` + `platform.id`) because
  LPAR numbers (1–64) are only unique within a single CPC.
- `mainframe.partition` is a specialised entity that only carries IBM Z-specific metrics not
  present in the generic `virtualization.partition` schema.

---

## 3. Hypervisor & Guest VM ERD

The second diagram shows the z/VM hypervisor layer and its guest VM entities.

```mermaid
classDiagram
    class virt_hypervisor["virtualization.hypervisor"] {
        +string hypervisor_id_IDENTITY
        +enum system_name__ibm_zvm
        +string hypervisor_version
        +enum hypervisor_type
        +enum hypervisor_state
    }

    class virt_vm["virtualization.vm"] {
        +string vm_id_IDENTITY
        +enum system_name__ibm_zvm
        +string vm_name
        +string vm_instance_id
        +enum vm_state
        +int vm_cpu_count
        +int vm_memory_size_MiB
        +string vm_machine_type
        +bool vm_nested_virtualization_enabled
    }

    class virt_partition["virtualization.partition"] {
        +string partition_id_IDENTITY
        +string platform_id_IDENTITY
        +enum system_name__ibm_prsm
    }

    class host_upstream["host (upstream)"] {
        +string host_name
        +string host_id
    }

    note for virt_hypervisor "identity: virtualization.hypervisor.id\n  = z/VM SYSNAME (e.g. ZLINUX1)\ndesc: system.name = ibm.zvm,\n  hypervisor.version = 7.3.0,\n  hypervisor.type = ibm.zvm,\n  hypervisor.state = running\nTopology: runs inside a virt.partition"
    note for virt_vm "identity: virtualization.vm.id\n  = z/VM VMID / guest userid\ndesc: system.name = ibm.zvm,\n  vm.name = same as vm.id,\n  vm.state: running|stopped|paused\nVM CPU types: CP, IFL, zIIP"

    %% Refinement lineage
    virt_vm --|> host_upstream : refines host

    %% z/VM nesting topology
    virt_partition "1" *-- "0..1" virt_hypervisor : hosts z/VM CP
    virt_hypervisor "1" *-- "0..*" virt_vm : manages guest VMs

    %% z/VM guest can itself run a nested hypervisor
    virt_vm "0..1" *-- "0..1" virt_hypervisor : nested z/VM (optional)
```

**Notes:**
- z/VM always runs **inside** a `virtualization.partition`. The `virt_hypervisor` entity
  does not exist independently — it is anchored to the LPAR that hosts it.
- Guest VMs (`virtualization.vm`) are z/VM User Directory entries identified by their
  8-character userid (e.g., `LINUX01`). This userid is the stable, unique identity.
- Nested virtualization: z/VM supports running a second z/VM instance inside a guest VM.
  In this case, the inner z/VM appears as a `virtualization.vm` to the outer z/VM, and its
  own `virtualization.hypervisor` entity represents the nested CP instance.
- KVM on IBM Z uses `virtualization.vm.id` from `virDomainGetUUIDString()` and
  `virtualization.system.name = "kvm"`.

---

## 4. Channel, Adapter & Crypto Hardware ERD

The third diagram shows the physical I/O hardware entities: channel paths, hardware adapters,
and their specialisations for crypto and AI acceleration.

```mermaid
classDiagram
    class mf_host["mainframe.host"] {
        +string mainframe_host_name_IDENTITY
    }

    class mf_channel["mainframe.channel"] {
        +string mainframe_channel_id_IDENTITY
        +string mainframe_host_name
        +enum mainframe_channel_type
    }

    class mf_adapter["mainframe.adapter"] {
        +string mainframe_adapter_id_IDENTITY
        +string mainframe_host_name
        +enum mainframe_adapter_type
        +enum mainframe_adapter_crypto_type
        +string mainframe_adapter_name
    }

    class mf_port["mainframe.port"] {
        +string mainframe_port_id_IDENTITY
        +string mainframe_adapter_id
        +string mainframe_port_name
    }

    note for mf_channel "identity: mainframe.channel.id (CHPID, e.g. A0)\ndesc: mainframe.host.name,\n  mainframe.channel.type:\n    ficon | osa | roce |\n    zhyperlink | hipersockets\nHMC source: channel-path object"
    note for mf_adapter "identity: mainframe.adapter.id (UUID)\ndesc: mainframe.host.name,\n  mainframe.adapter.type:\n    crypto | flash_memory |\n    network | storage |\n    accelerator\n  mainframe.adapter.crypto.type:\n    cca | ep11 | accelerator\nHMC source: adapter object"
    note for mf_port "identity: mainframe.port.id (element-uri)\ndesc: mainframe.adapter.id,\n  mainframe.port.name\nHMC source: port element"

    %% Containment
    mf_host "1" *-- "0..*" mf_channel : owns channel paths (CHPIDs)
    mf_host "1" *-- "0..*" mf_adapter : owns PCIe adapters
    mf_adapter "1" *-- "0..*" mf_port : has physical ports
```

**Channel type reference (`mainframe.channel.type`):**

| Enum Value | Full Name | Description |
|---|---|---|
| `ficon` | FICON / ESCON | Fibre Channel Connection for DASD and tape storage (IBM Z primary storage fabric) |
| `osa` | OSA-Express | Open Systems Adapter — Ethernet (GbE / 25GbE / OSD) for TCP/IP networking |
| `roce` | RoCE Express | RDMA over Converged Ethernet — high-throughput 25/100 GbE PCIe network adapter |
| `zhyperlink` | zHyperLink | PCIe synchronous coupling channel for ultra-low latency (<20 µs) Coupling Facility access |
| `hipersockets` | HiperSockets | Internal LAN fabric for zero-copy memory-to-memory transfers between LPARs |

**Adapter type reference (`mainframe.adapter.type`):**

| Enum Value | Description |
|---|---|
| `crypto` | Crypto Express CEX8S/CEX9S hardware security module (HSM). Sub-types: `cca`, `ep11`, `accelerator` |
| `flash_memory` | PCIe Flash Memory (Storage Class Memory / Virtual Flash Memory) for z/OS expanded storage |
| `network` | OSA-Express, RoCE Express, or ISM (Internal Shared Memory) network adapters |
| `storage` | FICON-attached storage controllers, NVMe adapters, FCP HBAs |
| `accelerator` | Neural Network Processing Assist (NNPA) on-chip AI inference accelerator (Telum/Telum-II) |

---

## 5. Network & Storage Virtualization ERD

The fourth diagram shows virtual networking and storage entities for both PR/SM (DPM) and z/VM
layers.

```mermaid
classDiagram
    class virt_vswitch["virtualization.vswitch"] {
        +string vswitch_name_IDENTITY
        +string vswitch_id
        +enum system_name__ibm_zvm
    }

    class virt_storage_pool["virtualization.storage_pool"] {
        +string pool_name_IDENTITY
        +string pool_id
        +enum system_name__ibm_prsm_or_ibm_zvm
    }

    class mf_nic["mainframe.nic"] {
        +string mainframe_nic_id_IDENTITY
        +string virtualization_partition_id
        +string mainframe_nic_name
    }

    class virt_partition["virtualization.partition"] {
        +string partition_id_IDENTITY
        +string platform_id_IDENTITY
        +enum system_name__ibm_prsm
    }

    class virt_vm["virtualization.vm"] {
        +string vm_id_IDENTITY
        +enum system_name__ibm_zvm
    }

    note for virt_vswitch "identity: virtualization.vswitch.name\n  (e.g. VSW1, SYSTEM)\ndesc: vswitch.id, system.name = ibm.zvm\nAlso used for DPM virtual switches\nHMC: vswitch object / z/VM Domain 11"
    note for virt_storage_pool "identity: virtualization.storage_pool.name\ndesc: pool.id,\n  system.name = ibm.prsm (DPM SG)\n            or ibm.zvm (minidisk pool)\nHMC: storage-group object\nz/VM: Domain 9 storage pool"
    note for mf_nic "identity: mainframe.nic.id (element-uri)\ndesc: partition.id, nic.name\nDPM mode only — virtual NIC\nattached to a DPM partition\nHMC: nic element (partition-attached-NIC)"

    %% z/VM virtual networking
    virt_vswitch "1" *-- "0..*" virt_vm : carries guest VM traffic
    virt_vswitch "1" *-- "0..*" virt_partition : carries partition traffic

    %% DPM virtual networking
    virt_partition "1" *-- "0..*" mf_nic : has virtual NICs (DPM)

    %% Storage
    virt_storage_pool "1" *-- "0..*" virt_partition : backs DPM partition volumes
    virt_storage_pool "1" *-- "0..*" virt_vm : backs z/VM guest minidisks
```

**Storage pool discriminator (`virtualization.system.name`):**

| Value | Context | Storage Construct |
|---|---|---|
| `ibm.prsm` | HMC DPM mode | DPM Storage Group (NVMe, FICON, FCP SAN attached volumes) |
| `ibm.zvm` | z/VM | Named minidisk pool or DASD volume group (Domain 9 records) |

---

## 6. Full Metric-to-Entity Association Map

This diagram shows all mainframe entity types and their complete bound metric sets, organised
by metric source class:
- **A** = `system.*` or `hw.*` base metric associations (from upstream registry)
- **ER** = `existing_virt_refinement` (already defined in `model/virtualization/`)
- **MR** = `new_mf_refinement` (base metric extended with mainframe-specific attributes)
- **NN** = net-new `mainframe.*` metrics

```mermaid
classDiagram
    %% ── Entity anchors ──────────────────────────────────────────────────────
    class mf_host["mainframe.host"] {
        +string mainframe_host_name_IDENTITY
    }
    class virt_platform["virtualization.platform"] {
        +string host_name_IDENTITY
        +enum system_name__ibm_prsm
    }
    class virt_partition["virtualization.partition"] {
        +string partition_id_IDENTITY
        +string platform_id_IDENTITY
        +enum system_name__ibm_prsm
    }
    class mf_partition["mainframe.partition"] {
        +string mainframe_partition_id_IDENTITY
    }
    class mf_cpu["mainframe.cpu"] {
        +string mainframe_cpu_id_IDENTITY
    }
    class virt_hypervisor["virtualization.hypervisor"] {
        +string hypervisor_id_IDENTITY
        +enum system_name__ibm_zvm
    }
    class virt_vm["virtualization.vm"] {
        +string vm_id_IDENTITY
        +enum system_name__ibm_zvm
    }
    class mf_channel["mainframe.channel"] {
        +string mainframe_channel_id_IDENTITY
    }
    class mf_adapter["mainframe.adapter"] {
        +string mainframe_adapter_id_IDENTITY
    }
    class mf_port["mainframe.port"] {
        +string mainframe_port_id_IDENTITY
    }
    class mf_nic["mainframe.nic"] {
        +string mainframe_nic_id_IDENTITY
    }
    class virt_vswitch["virtualization.vswitch"] {
        +string vswitch_name_IDENTITY
        +enum system_name__ibm_zvm
    }
    class virt_storage_pool["virtualization.storage_pool"] {
        +string pool_name_IDENTITY
    }

    %% ── Class A — hw.* and system.* base associations ──────────────────────
    class A_hw_power["hw.power"] {
        <<Class A base>>
        +instrument gauge
        +unit W
    }
    class A_hw_temp["hw.temperature"] {
        <<Class A base>>
        +instrument gauge
        +unit Cel
    }
    class A_hw_status["hw.status"] {
        <<Class A base>>
        +instrument gauge
        +unit 1
    }
    class A_sys_cpu_phys["system.cpu.physical.count"] {
        <<Class A base>>
        +instrument updowncounter
        +unit cpu
    }
    class A_sys_mem_limit["system.memory.limit"] {
        <<Class A base>>
        +instrument updowncounter
        +unit By
    }
    class A_sys_mem_usage["system.memory.usage"] {
        <<Class A base>>
        +instrument updowncounter
        +unit By
    }
    class A_sys_cpu_log["system.cpu.logical.count"] {
        <<Class A base>>
        +instrument updowncounter
        +unit cpu
    }
    class A_sys_disk_limit["system.disk.limit"] {
        <<Class A base>>
        +instrument updowncounter
        +unit By
    }

    note for A_hw_power "hw.power\nhw.type=enclosure\nHMC: zcpc-environmentals-and-power/power\nUnit conversion: kW × 1000"
    note for A_hw_temp "hw.temperature\nhw.type=enclosure\nHMC: zcpc-environmentals-and-power\n  /ambient-temperature"
    note for A_hw_status "hw.status\nHMC: cpc-resource/status\nMap: operating→1, exceptions→2"
    note for A_sys_cpu_phys "system.cpu.physical.count\nsystem.name=ibm.prsm\nHMC: cpc-resource/active-cores-count"
    note for A_sys_mem_limit "system.memory.limit\nsystem.name=ibm.prsm\nHMC: cpc-resource/installed-memory\nMiB × 1048576"
    note for A_sys_mem_usage "system.memory.usage\nsystem.name=ibm.prsm\nstate=used|free\nHMC: cpc-resource/assigned-memory"
    note for A_sys_cpu_log "system.cpu.logical.count\nsystem.name=ibm.prsm\nHMC: logical-partition-resource\n  /logical-processors-count"
    note for A_sys_disk_limit "system.disk.limit\nsystem.name=ibm.prsm\nHMC: storagevolume-resource/size\nGiB × 1073741824"

    %% ── Class ER — existing virtualization refinements ─────────────────────
    class ER_part_cpu_util["virt.partition.cpu.utilization"] {
        <<ER existing refinement>>
        +instrument gauge
        +unit 1
    }
    class ER_part_cpu_time["virt.partition.cpu.time"] {
        <<ER existing refinement>>
        +instrument counter
        +unit s
    }
    class ER_part_cpu_wt["virt.partition.cpu.weight"] {
        <<ER existing refinement>>
        +instrument gauge
        +unit 1
    }
    class ER_part_cpu_cap["virt.partition.cpu.is_capped"] {
        <<ER existing refinement>>
        +instrument gauge
        +unit 1
    }
    class ER_hyp_cpu_util["virt.hypervisor.cpu.utilization"] {
        <<ER existing refinement>>
        +instrument gauge
        +unit 1
    }
    class ER_vm_cpu_util["virt.vm.cpu.utilization"] {
        <<ER existing refinement>>
        +instrument gauge
        +unit 1
    }
    class ER_vm_cpu_time["virt.vm.cpu.time"] {
        <<ER existing refinement>>
        +instrument counter
        +unit s
    }
    class ER_vm_cpu_wait["virt.vm.cpu.wait_time"] {
        <<ER existing refinement>>
        +instrument counter
        +unit s
    }
    class ER_vm_mem["virt.vm.memory.usage"] {
        <<ER existing refinement>>
        +instrument updowncounter
        +unit By
    }
    class ER_vsw_io["virt.vswitch.network.io"] {
        <<ER existing refinement>>
        +instrument counter
        +unit By
    }
    class ER_vsw_drop["virt.vswitch.network.packet.dropped"] {
        <<ER existing refinement>>
        +instrument counter
        +unit packet
    }
    class ER_pool_cap["virt.storage_pool.capacity"] {
        <<ER existing refinement>>
        +instrument updowncounter
        +unit By
    }
    class ER_pool_usage["virt.storage_pool.usage"] {
        <<ER existing refinement>>
        +instrument updowncounter
        +unit By
    }

    note for ER_part_cpu_util "virtualization.partition.cpu.utilization\nsystem.name=ibm.prsm\nHMC: logical-partition-usage\n  /processor-usage-ifl|cp|ziip"
    note for ER_hyp_cpu_util "virtualization.hypervisor.cpu.utilization\nsystem.name=ibm.zvm\nz/VM: Domain 2 Record 1 / CPOVRHD"
    note for ER_vm_cpu_util "virtualization.vm.cpu.utilization\nsystem.name=ibm.zvm\nz/VM: Domain 4 Record 3\n  (CALC_IFL+CALC_CP)/(VIRT_PROC×INTERVAL)"
    note for ER_vsw_io "virtualization.vswitch.network.io\nsystem.name=ibm.zvm\nz/VM: Domain 11 Record 2\n  VSW_BYTES_RX|TX"
    note for ER_pool_cap "virtualization.storage_pool.capacity\nsystem.name=ibm.prsm\nHMC: storagegroup-resource/total-capacity\nGiB × 1073741824"

    %% ── Class MR — new mainframe-specific metric refinements ────────────────
    class MR_cpu_util["system.cpu.utilization (MR)"] {
        <<MR mainframe refinement>>
        +instrument gauge
        +unit 1
        +dim mainframe_cpu_type
        +dim mainframe_cpu_sharing_mode
    }
    class MR_cpu_time["system.cpu.time (MR)"] {
        <<MR mainframe refinement>>
        +instrument counter
        +unit s
        +dim mainframe_cpu_type
    }
    class MR_disk_io["system.disk.io (MR)"] {
        <<MR mainframe refinement>>
        +instrument counter
        +unit By
        +dim disk_io_direction
        +dim mainframe_channel_id
    }
    class MR_net_io["system.network.io (MR)"] {
        <<MR mainframe refinement>>
        +instrument counter
        +unit By
        +dim network_io_direction
    }
    class MR_paging["system.paging.operations (MR)"] {
        <<MR mainframe refinement>>
        +instrument counter
        +unit operation
        +dim direction
    }

    note for MR_cpu_util "refinement.mainframe.system.cpu.utilization\nentity: virtualization.platform\nAdds: mainframe.cpu.type = cp|ifl|ziip|icf\n  mainframe.cpu.sharing.mode = shared|dedicated\nHMC: cpc-usage-overview/processor-usage-*"
    note for MR_cpu_time "refinement.mainframe.system.cpu.time\nentity: virtualization.platform\nAdds: mainframe.cpu.type\nHMC: cpc-usage-overview/processor-time-*"
    note for MR_disk_io "refinement.mainframe.system.disk.io\nentity: mainframe.channel\nAdds: mainframe.channel.id (CHPID)\nmainframe.channel.type = ficon|…\nHMC: channel-usage/read|write-data-rate"
    note for MR_net_io "refinement.mainframe.system.network.io\nentities: mainframe.port (physical OSA/RoCE)\n          mainframe.nic (virtual DPM NIC)\nHMC: network-physical-adapter-port\n     partition-attached-network-interface"
    note for MR_paging "refinement.mainframe.system.paging.operations\nentity: virtualization.partition\nsystem.name = ibm.zvm\nz/VM: Domain 8 Record 1 / PGIN+PGOUT"

    %% ── Class NN — net-new mainframe.* metrics ──────────────────────────────
    class NN_host_env["mainframe.host env/power"] {
        <<NN net-new>>
        +host_power_usage gauge W
        +host_power_cord_usage gauge W
        +host_humidity gauge 1
        +host_dewpoint gauge Cel
        +host_heatload gauge Jph
        +host_msu_capacity gauge msu
    }
    class NN_host_cpu["mainframe.host cpu/memory"] {
        <<NN net-new>>
        +host_cpu_defective_count updowncounter cpu
        +host_cpu_spare_count updowncounter cpu
        +host_cpu_sap_count updowncounter cpu
        +host_cpu_ifp_count updowncounter cpu
        +host_memory_vfm_size updowncounter By
        +host_memory_vfm_increment_size updowncounter By
    }
    class NN_cpu["mainframe.cpu metrics"] {
        <<NN net-new>>
        +cpu_utilization gauge 1
        +cpu_thread_utilization gauge 1
    }
    class NN_channel["mainframe.channel metrics"] {
        <<NN net-new>>
        +channel_utilization gauge 1
        +channel_latency gauge s
    }
    class NN_adapter["mainframe.adapter metrics"] {
        <<NN net-new>>
        +adapter_utilization gauge 1
        +crypto_operations counter operation
        +crypto_queue_depth gauge request
        +crypto_request_wait_time gauge s
    }
    class NN_nnpa["mainframe.nnpa metrics"] {
        <<NN net-new>>
        +nnpa_operations counter operation
        +nnpa_utilization gauge 1
    }
    class NN_smc["mainframe.smc metrics"] {
        <<NN net-new>>
        +smc_transfer_bytes counter By
    }
    class NN_partition["mainframe.partition metrics"] {
        <<NN net-new>>
        +partition_cpu_reserved_count updowncounter cpu
        +partition_power_usage gauge W
        +partition_adapter_utilization gauge 1
    }

    note for NN_host_env "mainframe.host.power.usage\n  dim: host.power.usage.type = partition|infrastructure\nmainframe.host.power.cord.usage\n  dim: host.power.cord.id\nmainframe.host.humidity\nmainframe.host.dewpoint\nmainframe.host.heatload\n  dim: heatload.type = air|water\nmainframe.host.msu.capacity"
    note for NN_cpu "mainframe.cpu.utilization\n  dim: mainframe.cpu.id\nmainframe.cpu.thread.utilization\n  dim: mainframe.cpu.thread.id = 0|1\nHMC: zcpc-processor-usage (HIS)"
    note for NN_channel "mainframe.channel.utilization\n  dim: channel.id, channel.type\nmainframe.channel.latency\n  dim: channel.type=zhyperlink\n  operation = read|write"
    note for NN_adapter "mainframe.adapter.utilization\n  dim: adapter.type, adapter.id\nmainframe.crypto.operations\n  dim: crypto.function = rsa|aes|ecc|…\nmainframe.crypto.queue.depth\n  dim: crypto.domain.id\nmainframe.crypto.request.wait_time"
    note for NN_nnpa "mainframe.nnpa.operations\n  dim: nnpa.operation = matmul|conv2d|…\nmainframe.nnpa.utilization\nAvailable: z16 (Telum) + z17 (Telum-II)\nentity: virtualization.platform"
    note for NN_partition "mainframe.partition.cpu.reserved.count\n  dim: mainframe.cpu.type\nmainframe.partition.power.usage\nmainframe.partition.adapter.utilization\n  dim: mainframe.adapter.type"

    %% ── Associations — base metrics ─────────────────────────────────────────
    mf_host .. A_hw_power
    mf_host .. A_hw_temp
    mf_host .. A_hw_status
    virt_platform .. A_sys_cpu_phys
    virt_platform .. A_sys_mem_limit
    virt_platform .. A_sys_mem_usage
    virt_partition .. A_sys_cpu_log
    virt_storage_pool .. A_sys_disk_limit

    %% ── Associations — existing virtualization refinements ──────────────────
    virt_partition .. ER_part_cpu_util
    virt_partition .. ER_part_cpu_time
    virt_partition .. ER_part_cpu_wt
    virt_partition .. ER_part_cpu_cap
    virt_hypervisor .. ER_hyp_cpu_util
    virt_vm .. ER_vm_cpu_util
    virt_vm .. ER_vm_cpu_time
    virt_vm .. ER_vm_cpu_wait
    virt_vm .. ER_vm_mem
    virt_vswitch .. ER_vsw_io
    virt_vswitch .. ER_vsw_drop
    virt_storage_pool .. ER_pool_cap
    virt_storage_pool .. ER_pool_usage

    %% ── Associations — new mainframe refinements ────────────────────────────
    virt_platform .. MR_cpu_util
    virt_platform .. MR_cpu_time
    mf_channel .. MR_disk_io
    mf_port .. MR_net_io
    mf_nic .. MR_net_io
    virt_partition .. MR_paging

    %% ── Associations — net-new mainframe metrics ────────────────────────────
    mf_host .. NN_host_env
    mf_host .. NN_host_cpu
    mf_cpu .. NN_cpu
    mf_channel .. NN_channel
    mf_adapter .. NN_adapter
    virt_platform .. NN_nnpa
    mf_host .. NN_smc
    mf_partition .. NN_partition
```

---

## 7. Cross-Platform Topology Lineage

This diagram shows how each IBM Z virtualization layer maps its native constructs into the
unified OTel mainframe/virtualization entity schema. All paths converge on the same entity types
and the same metric definitions — discriminated by `virtualization.system.name`.

```mermaid
flowchart TD
    subgraph Physical ["L0 — Physical Infrastructure"]
        CPC["Central Processor Complex\n(z17 / z16 / z15 CEC frame)"]
        CHPID["Channel Paths (CHPIDs)\nFICON | OSA | RoCE | zHyperLink"]
        ADAPTER["Physical Adapters\nCrypto Express | Flash Memory | RoCE"]
        ENV["Environmental Sensors\nPower | Temperature | Humidity | Heatload"]
    end

    subgraph PRSM_Classic ["L1 — PR/SM Classic Mode"]
        LPAR["Logical Partition (LPAR)\nnamed, processor-type-assigned"]
        POOL["Shared Processor Pool\nCP / IFL / zIIP shared weight pools"]
    end

    subgraph PRSM_DPM ["L1 — PR/SM DPM Mode"]
        DPM_PART["DPM Partition\nresource-profile-based allocation"]
        SG["DPM Storage Group\nNVMe / FICON / FCP SAN"]
        DPM_NIC["Virtual NIC\nattached to DPM partition"]
    end

    subgraph ZVM ["L2 — IBM z/VM Control Program"]
        ZVM_CP["z/VM CP Hypervisor\nSYSNAME-identified instance"]
        GUEST["Guest Virtual Machine\nz/VM User Directory entry (VMID)"]
        VSW["VSWITCH / Guest LAN\nz/VM virtual network switch"]
        MPOOL["Minidisk / DASD Pool\nz/VM named storage pool"]
    end

    subgraph KVM ["L2 — Linux KVM on IBM Z"]
        KVM_HOST["KVM Host (Linux LPAR)\nrunning in a PR/SM partition"]
        KVM_GUEST["KVM Guest VM\nlibvirt domain (virDomain)"]
        KVM_NET["Linux Bridge / macvtap\nvirtual network"]
    end

    subgraph OCP ["L2 — OpenShift Virtualization (s390x)"]
        OCP_NODE["OpenShift Worker Node\nLinux on Z s390x"]
        VMI["VirtualMachineInstance\nKubeVirt vmi.metadata.uid"]
        OCP_NS["Namespace ResourceQuota"]
        OCP_NET["OVN-Kubernetes Network"]
    end

    subgraph OTel_Entities ["OTel Semantic Convention Entities"]
        direction TB
        E_HOST["mainframe.host\nidentity: mainframe.host.name\nsystem discriminator: —"]
        E_PLAT["virtualization.platform\nidentity: host.name\nsystem.name: ibm.prsm"]
        E_PART["virtualization.partition\nidentity: partition.id + platform.id\nsystem.name: ibm.prsm"]
        E_MF_PART["mainframe.partition\nidentity: mainframe.partition.id"]
        E_CHAN["mainframe.channel\nidentity: mainframe.channel.id (CHPID)"]
        E_ADAPT["mainframe.adapter\nidentity: mainframe.adapter.id (UUID)"]
        E_PORT["mainframe.port\nidentity: mainframe.port.id"]
        E_NIC["mainframe.nic\nidentity: mainframe.nic.id"]
        E_HYP["virtualization.hypervisor\nidentity: hypervisor.id (SYSNAME)\nsystem.name: ibm.zvm"]
        E_VM["virtualization.vm\nidentity: vm.id\nsystem.name: ibm.zvm / kvm / ocp_virt"]
        E_VSW["virtualization.vswitch\nidentity: vswitch.name\nsystem.name: ibm.zvm"]
        E_POOL["virtualization.storage_pool\nidentity: pool.name\nsystem.name: ibm.prsm / ibm.zvm"]
    end

    %% Physical layer mappings
    CPC  -->|"mainframe.host.name = CPC.name\nhost.type = machine-type"| E_HOST
    CPC  -->|"host.name = CPC.name\nsystem.name = ibm.prsm"| E_PLAT
    CHPID -->|"channel.id = CHPID\nchannel.type = ficon|osa|roce|…"| E_CHAN
    ADAPTER -->|"adapter.id = object-uri UUID\nadapter.type = crypto|flash|network|…"| E_ADAPT
    ADAPTER -->|"port.id = element-uri"| E_PORT

    %% PR/SM Classic mode mappings
    LPAR  -->|"partition.id = LPAR UUID\nplatform.id = CPC UUID\nsystem.name = ibm.prsm"| E_PART
    LPAR  -->|"partition.id = LPAR UUID\n(IBM Z-specific reserved CPU metrics)"| E_MF_PART
    POOL  -->|"pool.name = shared pool name\nsystem.name = ibm.prsm"| E_POOL

    %% PR/SM DPM mode mappings
    DPM_PART -->|"partition.id = partition UUID\nsystem.name = ibm.prsm"| E_PART
    SG       -->|"pool.name = storage group name\nsystem.name = ibm.prsm"| E_POOL
    DPM_NIC  -->|"nic.id = NIC element-uri\npartition.id = parent partition"| E_NIC

    %% z/VM layer mappings
    ZVM_CP -->|"hypervisor.id = SYSNAME\nhypervisor.version = 7.3.0\nsystem.name = ibm.zvm"| E_HYP
    GUEST  -->|"vm.id = VMID (userid)\nvm.name = VMID\nsystem.name = ibm.zvm"| E_VM
    VSW    -->|"vswitch.name = VSW_NAME\nsystem.name = ibm.zvm"| E_VSW
    MPOOL  -->|"pool.name = POOL_NAME\nsystem.name = ibm.zvm"| E_POOL

    %% KVM layer mappings
    KVM_HOST  -->|"host.name = virConnectGetHostname()\nsystem.name = kvm"| E_PLAT
    KVM_GUEST -->|"vm.id = virDomainGetUUIDString()\nsystem.name = kvm"| E_VM
    KVM_NET   -->|"vswitch.name = virNetworkGetName()\nsystem.name = kvm"| E_VSW

    %% OpenShift Virtualization mappings
    OCP_NODE -->|"host.name = node.metadata.name\nsystem.name = kvm"| E_PLAT
    VMI      -->|"vm.id = vmi.metadata.uid\nsystem.name = openshift_virtualization"| E_VM
    OCP_NS   -->|"pool.name = namespace.name\nsystem.name = openshift_virtualization"| E_POOL
    OCP_NET  -->|"vswitch.name = network.name\nsystem.name = openshift_virtualization"| E_VSW
```

---

## 8. IBM Z Processor Type Dimension

The `mainframe.cpu.type` attribute is the primary IBM Z-specific dimension across processor
metrics. It appears in two refinements and one net-new metric:

```mermaid
classDiagram
    class M_cpu_util["system.cpu.utilization"] {
        <<MR mainframe refinement>>
        +instrument gauge
        +unit 1
        +dim mainframe_cpu_type
        +dim mainframe_cpu_sharing_mode
    }
    class M_cpu_time["system.cpu.time"] {
        <<MR mainframe refinement>>
        +instrument counter
        +unit s
        +dim mainframe_cpu_type
    }
    class M_cpu_core["mainframe.cpu.utilization"] {
        <<NN net-new>>
        +instrument gauge
        +unit 1
        +identity mainframe_cpu_id
    }
    class M_cpu_thread["mainframe.cpu.thread.utilization"] {
        <<NN net-new>>
        +instrument gauge
        +unit 1
        +identity mainframe_cpu_id
        +dim mainframe_cpu_thread_id
    }

    class CpuType["mainframe.cpu.type enum"] {
        <<attribute enum>>
        +cp General Purpose
        +ifl Integrated Facility for Linux
        +ziip Z Integrated Info Processor
        +icf Internal Coupling Facility
        +sap System Assist Processor
        +ifp Integrated Firmware Processor
    }

    note for M_cpu_util "entity: virtualization.platform\nHMC: cpc-usage-overview\n  processor-usage-ifl|cp|ziip|icf\n15-second interval, ratio 0.0–1.0"
    note for M_cpu_time "entity: virtualization.platform\nHMC: cpc-usage-overview\n  processor-time-ifl|cp|ziip|icf\ncumulative ms → s"
    note for M_cpu_core "entity: mainframe.cpu\nHMC: zcpc-processor-usage\n  per individual physical/logical core\nfrom Hardware Instrumentation Services (HIS)"
    note for M_cpu_thread "entity: mainframe.cpu\nHMC: zcpc-processor-usage\n  thread-0-utilization | thread-1-utilization\nSMT-2: each core has 2 threads"

    M_cpu_util  -- CpuType : discriminates by
    M_cpu_time  -- CpuType : discriminates by
    M_cpu_core  -- CpuType : described by
    M_cpu_thread -- CpuType : described by
```

**Processor type reference:**

| `mainframe.cpu.type` | Full Name | Primary Workload | Licensed Separately? |
|---|---|---|---|
| `cp` | Central Processor (General Purpose) | z/OS transaction, batch, all workloads | Yes (MLC, sub-capacity) |
| `ifl` | Integrated Facility for Linux | Linux on Z, z/VM, Java | Yes (flat fee, cheaper) |
| `ziip` | IBM Z Integrated Information Processor | z/OS offload: Java, XML, REST, SSL | Yes (eligible z/OS work) |
| `icf` | Internal Coupling Facility | Parallel Sysplex Coupling Facility workloads | Yes (per ICF engine) |
| `sap` | System Assist Processor | I/O channel operations (invisible to workloads) | No (included in CPC) |
| `ifp` | Integrated Firmware Processor | PCIe subsystem management | No (included in CPC) |

---

## 9. Entity Identity & Discriminator Reference

| Entity Type | Identity Attributes | `virtualization.system.name` Values | Source |
|---|---|---|---|
| `mainframe.host` | `mainframe.host.name` | *not applicable* | HMC CPC object `name` |
| `virtualization.platform` | `host.name` | `ibm.prsm` | HMC CPC object `name` |
| `virtualization.partition` | `virtualization.partition.id` + `virtualization.platform.id` | `ibm.prsm` | HMC LPAR / partition `object-uri` UUID |
| `mainframe.partition` | `mainframe.partition.id` | *not applicable* | HMC LPAR `object-uri` UUID |
| `mainframe.cpu` | `mainframe.cpu.id` | *not applicable* | HIS per-core identifier |
| `virtualization.hypervisor` | `virtualization.hypervisor.id` | `ibm.zvm` | z/VM SYSNAME (Domain 1 / `SYSNAME`) |
| `virtualization.vm` | `virtualization.vm.id` | `ibm.zvm`, `kvm`, `openshift_virtualization` | z/VM VMID; KVM virDomainGetUUIDString() |
| `mainframe.channel` | `mainframe.channel.id` | *not applicable* | HMC channel-path `channel-path-id` (CHPID) |
| `mainframe.adapter` | `mainframe.adapter.id` | *not applicable* | HMC adapter `object-uri` UUID |
| `mainframe.port` | `mainframe.port.id` | *not applicable* | HMC port `element-uri` |
| `mainframe.nic` | `mainframe.nic.id` | *not applicable* | HMC NIC `element-uri` |
| `virtualization.vswitch` | `virtualization.vswitch.name` | `ibm.zvm` | z/VM `VSW_NAME` (Domain 11) |
| `virtualization.storage_pool` | `virtualization.storage_pool.name` | `ibm.prsm`, `ibm.zvm` | HMC storage group `name`; z/VM `POOL_NAME` |

---

## 10. Multi-Tenant Isolation Patterns

IBM Z PR/SM provides hardware-enforced multi-tenant isolation at the firmware level, which has
specific implications for the observability entity model:

```mermaid
flowchart TD
    subgraph CPC ["Single CPC (mainframe.host + virtualization.platform)"]
        direction TB
        subgraph LPAR_A ["LPAR A — z/OS Production\nvirt.partition (id=A)"]
            ZOS_A["z/OS system\n(system.name=ibm.prsm)"]
        end
        subgraph LPAR_B ["LPAR B — z/VM for Linux\nvirt.partition (id=B)"]
            ZVM_B["z/VM hypervisor\nvirt.hypervisor (id=ZVMB)"]
            subgraph GUESTS_B ["z/VM Guest VMs"]
                G1["Linux VM 1\nvirt.vm (id=LINUX01)"]
                G2["Linux VM 2\nvirt.vm (id=LINUX02)"]
                G3["KVM Host\nvirt.vm (id=KVMHOST)"]
            end
        end
        subgraph LPAR_C ["LPAR C — OpenShift\nvirt.partition (id=C)"]
            OCP_C["OpenShift cluster\nvirt.platform (system.name=kvm)"]
            subgraph VMI_C ["KubeVirt VMIs"]
                VMI1["VMI 1\nvirt.vm (id=vmi-uid-1)"]
                VMI2["VMI 2\nvirt.vm (id=vmi-uid-2)"]
            end
        end
    end

    ZVM_B --> GUESTS_B
    OCP_C --> VMI_C

    CPC -->|"PR/SM hardware boundary\n(no CPU/memory crossover)"| LPAR_A
    CPC -->|"PR/SM hardware boundary"| LPAR_B
    CPC -->|"PR/SM hardware boundary"| LPAR_C
```

**Isolation properties visible in the entity model:**

| Boundary | OTel Entity Relationship | Query Pattern |
|---|---|---|
| CPC → LPAR | `virtualization.platform` → `virtualization.partition` | `{virtualization_platform_id="CPC-UUID"}` |
| LPAR → z/VM CP | `virtualization.partition` → `virtualization.hypervisor` | `{virtualization_hypervisor_id="SYSNAME"}` |
| z/VM CP → Guest | `virtualization.hypervisor` → `virtualization.vm` | `{virtualization_system_name="ibm.zvm", vm_id="LINUX01"}` |
| LPAR → KVM Host | `virtualization.partition` → `virtualization.platform` (KVM) | `{virtualization_system_name="kvm"}` |
| KVM → VMI | `virtualization.platform` (KVM) → `virtualization.vm` | `{virtualization_system_name="openshift_virtualization"}` |

---

## 11. Minimal Slide-Ready ERD (Entities & Relationships Only)

A clean, compact entity-relationship chart optimized for high-legibility presentation slides, containing only entity nodes and their relational cardinality across the mainframe and virtualization hierarchy without attribute bodies:

```mermaid
erDiagram
    %% ── Upstream base entity ──
    HOST ||--o{ MAINFRAME_HOST : "refined by"
    HOST ||--o{ VIRTUALIZATION_PLATFORM : "refined by"
    HOST ||--o{ VIRTUALIZATION_PARTITION : "refined by"
    HOST ||--o{ VIRTUALIZATION_VM : "refined by"

    %% ── Physical CPC Hardware Layer ──
    MAINFRAME_HOST ||--|| VIRTUALIZATION_PLATFORM : "same CPC scope"
    MAINFRAME_HOST ||--o{ MAINFRAME_CHANNEL : "owns CHPIDs"
    MAINFRAME_HOST ||--o{ MAINFRAME_ADAPTER : "owns PCIe adapters"
    MAINFRAME_ADAPTER ||--o{ MAINFRAME_PORT : "has physical ports"

    %% ── Compute & Partitioning (PR/SM) ──
    VIRTUALIZATION_PLATFORM ||--o{ MAINFRAME_CPU : "contains physical cores"
    VIRTUALIZATION_PLATFORM ||--o{ VIRTUALIZATION_PARTITION : "hosts LPARs"
    VIRTUALIZATION_PARTITION ||--o| MAINFRAME_PARTITION : "mainframe extensions"

    %% ── Hypervisor & Guest VMs (z/VM / KVM) ──
    VIRTUALIZATION_PARTITION ||--o| VIRTUALIZATION_HYPERVISOR : "hosts hypervisor"
    VIRTUALIZATION_HYPERVISOR ||--o{ VIRTUALIZATION_VM : "manages guest VMs"
    VIRTUALIZATION_VM ||--o| VIRTUALIZATION_HYPERVISOR : "nested hypervisor"

    %% ── Fabric, Networking & Storage ──
    VIRTUALIZATION_PARTITION ||--o{ MAINFRAME_NIC : "attaches virtual NICs"
    VIRTUALIZATION_VSWITCH ||--o{ VIRTUALIZATION_VM : "routes VM traffic"
    VIRTUALIZATION_VSWITCH ||--o{ VIRTUALIZATION_PARTITION : "routes LPAR traffic"
    VIRTUALIZATION_STORAGE_POOL ||--o{ VIRTUALIZATION_PARTITION : "backs storage groups"
    VIRTUALIZATION_STORAGE_POOL ||--o{ VIRTUALIZATION_VM : "backs minidisks"
```
