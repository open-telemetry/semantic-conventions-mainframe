# Virtualization Semantic Conventions — Visual Semantic Models & Architecture

> **Scope:** This document illustrates the entity model, metric associations and cross-platform
> topology defined in `model/virtualization/` with Mermaid diagrams and a short architecture
> summary. Entity types, attribute keys and metric names are those of the `definition/2` YAML
> files. The generated registry pages under [docs/registry/virtualization/](registry/virtualization/README.md)
> are authoritative for the complete attribute and metric lists
> ([entities](registry/virtualization/entities.md), [metrics](registry/virtualization/metrics.md),
> [entity refinements](registry/virtualization/entity-refinements.md),
> [metric refinements](registry/virtualization/metric-refinements.md)); the diagrams below show
> selected attributes and metrics only.

---

## 1. Executive Summary

### Design Lessons & Trade-offs

The virtualization semantic conventions answer one architectural question: *How do we describe
the compute stack — from bare metal to VM — with a single entity model that works across IBM Z
PR/SM, IBM z/VM, VMware vSphere, KVM/libvirt and OpenShift Virtualization?*

Six lessons shaped the design:

**1. Minimal entity types, maximal attribute discrimination.**
Rather than creating a separate entity type per hypervisor platform, the model uses eight entity
types plus the `virtualization.system.name` enum to discriminate platforms. A single filter such
as `{virtualization_system_name="ibm.prsm"}` isolates all IBM Z PR/SM metrics.

**2. The `host` refinement pattern keeps upstream compatibility.**
`virtualization.platform`, `virtualization.partition` and `virtualization.vm` each refine the
upstream `host` entity (`refinement.virtualization.platform.host`,
`refinement.virtualization.partition.host`, `refinement.virtualization.vm.host`). Consumers that
understand only the generic host entity can therefore use their data, and the upstream `system.*`
metrics an operating system reports describe these entities. Metric refinements are added only
where a metric needs an additional attribute (for example `virtualization.partition.cpu.type` for
IBM Z processor types) or an explicit association with a virtualization entity (the `system.*`
refinements on `virtualization.vm` in `metrics_refinements_vm.yaml`).

**3. `virtualization.partition` fills the firmware-partitioning gap.**
IBM Z PR/SM logical partitions are enforced by firmware, not by a software hypervisor. They are
neither VMs (no hypervisor software) nor bare-metal hosts (they share physical hardware).
`virtualization.partition` models this concept; it coexists with `virtualization.vm` in mixed
environments where IBM z/VM runs inside an LPAR.

**4. Counter-based latency enables average derivation.**
`virtualization.vm.disk.latency.time` (unit `s`, instrument counter) accumulates the time spent in
disk I/O. Dividing `rate(latency_time)` by `rate(disk_operations)` yields the average latency per
operation in seconds — without histograms or high-frequency sampling.

**5. Dual lineage is an attribute, not an entity.**
OpenShift Virtualization VMIs have both a virtualization identity and a Kubernetes identity.
Rather than introducing a new entity type, the model carries the Kubernetes correlation in
`virtualization.vm.node.name` and, as an upstream attribute, `k8s.namespace.name`. The
`virtualization.vm` entity remains the primary anchor.

**6. Identity is stable and the same for every observer.**
Every entity is identified by an `*.id` attribute (the partition by `virtualization.partition.id`
together with `virtualization.platform.id`). The attribute definition states the uniqueness
scope and how each platform fills the value; names such as `host.name` or
`virtualization.cluster.name` are descriptive, because a rename must not end an entity's
lifespan. Identifiers of management-tool internal objects are not used, since other observers
cannot see them. A VM's identity never includes the host or hypervisor it runs on, so it
survives vMotion, KVM live migration and z/VM Live Guest Relocation.

---

## 2. Compute & Partitioning ERD

The first diagram shows the four entities involved in compute and workload isolation, including
their identity attributes, descriptive attributes and `host` refinement lineage.

```mermaid
classDiagram
    class host_upstream["host (upstream)"] {
        +string host_id
        +string host_name
        +string host_type
        +string host_arch
    }

    class virt_platform["virtualization.platform"] {
        +string platform_id_IDENTITY
        +string host_id
        +string host_name
        +string host_type
        +string host_arch
        +enum system_name
        +string platform_serial_number
        +string platform_firmware_version
        +string platform_name_OPT_IN
        +string platform_model_OPT_IN
    }

    class virt_partition["virtualization.partition"] {
        +string partition_id_IDENTITY
        +string platform_id_IDENTITY
        +enum system_name
        +string partition_name
        +int partition_number
        +enum partition_type
        +enum partition_state
    }

    class virt_hypervisor["virtualization.hypervisor"] {
        +string hypervisor_id_IDENTITY
        +enum system_name
        +string hypervisor_version
        +enum hypervisor_type
        +enum hypervisor_state
    }

    class virt_vm["virtualization.vm"] {
        +string vm_id_IDENTITY
        +enum system_name
        +string vm_name
        +string vm_instance_id
        +enum vm_state
        +int vm_cpu_count
        +int vm_memory_size_MiB
        +string vm_machine_type
        +bool vm_nested_virtualization_enabled
    }

    note for virt_platform "identity: virtualization.platform.id\ndesc: host.id (equal to virtualization.platform.id),\nhost.name, host.type, host.arch,\nvirtualization.system.name,\nvirtualization.platform.serial_number,\nvirtualization.platform.firmware.version"
    note for virt_partition "identity: virtualization.partition.id\n         + virtualization.platform.id\ndesc: virtualization.system.name,\nvirtualization.partition.name, .number, .type, .state"
    note for virt_hypervisor "identity: virtualization.hypervisor.id\ndesc: virtualization.system.name,\nvirtualization.hypervisor.version, .type, .state"
    note for virt_vm "identity: virtualization.vm.id\ndesc: virtualization.system.name,\nvirtualization.vm.name, .state, .cpu.count,\n.memory.size, .machine_type"

    %% Refinement lineage (entity_refinements: ref: host)
    virt_platform  --|> host_upstream : refines host
    virt_partition --|> host_upstream : refines host
    virt_vm        --|> host_upstream : refines host

    %% Containment
    virt_platform  "1" *-- "0..*" virt_partition : hosts partitions
    virt_hypervisor "1" *-- "0..*" virt_vm : manages VMs
    virt_platform  "1" *-- "0..1" virt_hypervisor : runs hypervisor
```

**Notes:**

- `_IDENTITY` marks attributes in the entity `identity:` block — together they identify an
  instance. All other attributes are in the `description:` block; `_OPT_IN` marks attributes with
  requirement level `opt_in`.
- The `--|>` arrows indicate `entity_refinements:` (is-a, not inheritance in the OOP sense).
- `virtualization.platform.id` is the platform's stable key: on IBM Z the CPC's
  `<machine type>-<serial number>` with leading zeros removed from the serial (e.g. `3931-45A01`),
  on VMware vSphere the ESXi host hardware UUID, on KVM/libvirt the host machine ID. `host.id`
  SHOULD carry the same value, so consumers of the generic host entity identify the same platform;
  `host.name` is descriptive.
- `virtualization.partition` has a two-attribute identity because partition IDs are unique only
  within a platform. On IBM Z, `virtualization.partition.id` is the LPAR name.
- `virtualization.vm.memory.size` is an attribute in MiB; the memory metrics in §4 are in bytes.

---

## 3. Cluster & Resource Governance ERD

The second diagram shows the cluster and resource governance entities and their containment
relationships.

```mermaid
classDiagram
    class virt_cluster["virtualization.cluster"] {
        +string cluster_id_IDENTITY
        +string cluster_name
    }

    class virt_resource_pool["virtualization.resource_pool"] {
        +string pool_id_IDENTITY
        +string pool_name
        +enum system_name
    }

    class virt_platform["virtualization.platform"] {
        +string platform_id_IDENTITY
        +enum system_name
    }

    class virt_vm["virtualization.vm"] {
        +string vm_id_IDENTITY
        +int vm_cpu_count
        +int vm_memory_size_MiB
        +enum vm_state
    }

    class MetricClusterHostCount {
        <<metric>>
        +name cluster_host_count
        +instrument updowncounter
        +unit host
    }

    class MetricClusterVMCount {
        <<metric>>
        +name cluster_vm_count
        +instrument updowncounter
        +unit vm
    }

    class MetricPoolCPU {
        <<metric>>
        +name resource_pool_cpu_allocated
        +instrument gauge
        +unit cpu
    }

    class MetricPoolMemory {
        <<metric>>
        +name resource_pool_memory_allocated
        +instrument gauge
        +unit By
    }

    note for MetricClusterHostCount "virtualization.cluster.host.count\nattrs: virtualization.cluster.name, virtualization.cluster.id,\nvirtualization.system.name"
    note for MetricClusterVMCount "virtualization.cluster.vm.count\nattrs: virtualization.cluster.name, virtualization.cluster.id,\nvirtualization.vm.state, virtualization.system.name"
    note for MetricPoolCPU "virtualization.resource_pool.cpu.allocated\nattrs: virtualization.resource_pool.name,\nvirtualization.resource_pool.id, virtualization.system.name"
    note for MetricPoolMemory "virtualization.resource_pool.memory.allocated\nattrs: virtualization.resource_pool.name,\nvirtualization.resource_pool.id, virtualization.system.name"

    %% Containment
    virt_cluster "1" *-- "1..*" virt_platform : contains nodes
    virt_cluster "1" *-- "0..*" virt_resource_pool : governs pools
    virt_resource_pool "1" *-- "0..*" virt_vm : bounds VMs

    %% Metric associations
    virt_cluster       .. MetricClusterHostCount
    virt_cluster       .. MetricClusterVMCount
    virt_resource_pool .. MetricPoolCPU
    virt_resource_pool .. MetricPoolMemory
```

**Platform-specific notes:**

| Entity | IBM Z | VMware vSphere | KVM / oVirt | OpenShift Virtualization |
| --- | --- | --- | --- | --- |
| `virtualization.cluster` | z/VM SSI cluster; `virtualization.cluster.id` = SSI cluster name | ClusterComputeResource; id = vCenter instance UUID + cluster MoRef, e.g. `<vCenter UUID>/domain-c7` | oVirt or Proxmox VE cluster | OpenShift cluster |
| `virtualization.resource_pool` | PR/SM shared processor pool; id = CPC key + pool name, e.g. `3931-45A01/IFLPOOL` | ResourcePool; id = vCenter instance UUID + ResourcePool MoRef, e.g. `<vCenter UUID>/resgroup-21` | cgroup v2 slice | Namespace ResourceQuota |

The attribute definitions give identifier fill rules for IBM Z and VMware vSphere only; for the
KVM cluster managers and OpenShift Virtualization the columns show the corresponding native
construct.

---

## 4. Storage & Memory Architecture ERD

The third diagram shows the storage pool entity, its relationship to VMs, and the memory
signals including ballooning and swap.

```mermaid
classDiagram
    class virt_storage_pool["virtualization.storage_pool"] {
        +string pool_id_IDENTITY
        +string pool_name
        +enum system_name
    }

    class virt_vm["virtualization.vm"] {
        +string vm_id_IDENTITY
        +int vm_memory_size_MiB
    }

    class MetricStorageUsed {
        <<metric>>
        +name storage_pool_used
        +instrument updowncounter
        +unit By
    }

    class MetricStorageAvail {
        <<metric>>
        +name storage_pool_available
        +instrument updowncounter
        +unit By
    }

    class MetricDiskIO {
        <<metric>>
        +name vm_disk_io
        +instrument counter
        +unit By
        +dim disk_direction
    }

    class MetricDiskOps {
        <<metric>>
        +name vm_disk_operations
        +instrument counter
        +unit operation
        +dim disk_direction
    }

    class MetricDiskLatency {
        <<metric>>
        +name vm_disk_latency_time
        +instrument counter
        +unit s
        +dim disk_direction
    }

    class MetricDiskErrors {
        <<metric>>
        +name vm_disk_errors
        +instrument counter
        +unit error
        +dim disk_direction
    }

    class MetricMemAlloc {
        <<metric>>
        +name vm_memory_allocated
        +instrument gauge
        +unit By
    }

    class MetricMemUsed {
        <<metric>>
        +name vm_memory_used
        +instrument gauge
        +unit By
    }

    class MetricMemBalloon {
        <<metric>>
        +name vm_memory_balloon
        +instrument gauge
        +unit By
    }

    class MetricMemSwapped {
        <<metric>>
        +name vm_memory_swapped
        +instrument gauge
        +unit By
    }

    class MetricMemRSS {
        <<metric>>
        +name vm_memory_rss
        +instrument gauge
        +unit By
    }

    note for MetricStorageUsed "virtualization.storage_pool.used\nattrs: virtualization.storage_pool.name,\nvirtualization.storage_pool.id, virtualization.system.name"
    note for MetricStorageAvail "virtualization.storage_pool.available\nattrs: virtualization.storage_pool.name,\nvirtualization.storage_pool.id, virtualization.system.name"
    note for MetricDiskIO "virtualization.vm.disk.io\nattrs: virtualization.vm.id, virtualization.vm.disk.name\ndim: virtualization.vm.disk.direction = read or write"
    note for MetricDiskOps "virtualization.vm.disk.operations\nattrs: virtualization.vm.id, virtualization.vm.disk.name\ndim: virtualization.vm.disk.direction = read or write"
    note for MetricDiskLatency "virtualization.vm.disk.latency.time\navg latency = rate(latency.time) / rate(operations)\ndim: virtualization.vm.disk.direction = read or write"
    note for MetricDiskErrors "virtualization.vm.disk.errors\nattrs: virtualization.vm.id, virtualization.vm.disk.name\ndim: virtualization.vm.disk.direction (recommended)"
    note for MetricMemAlloc "virtualization.vm.memory.allocated\nmemory committed to the VM by the hypervisor"
    note for MetricMemUsed "virtualization.vm.memory.used\nmemory the guest actively uses (subset of allocated)"
    note for MetricMemBalloon "virtualization.vm.memory.balloon\nnon-zero = hypervisor reclaiming guest memory"
    note for MetricMemSwapped "virtualization.vm.memory.swapped\nbytes in hypervisor swap space"
    note for MetricMemRSS "virtualization.vm.memory.rss\nphysical host memory backing the VM (KVM, KubeVirt)\nattrs: virtualization.vm.id, virtualization.vm.node.name"

    %% Containment
    virt_storage_pool "1" *-- "0..*" virt_vm : backs virtual disks

    %% Storage pool metrics
    virt_storage_pool .. MetricStorageUsed
    virt_storage_pool .. MetricStorageAvail

    %% VM disk metrics
    virt_vm .. MetricDiskIO
    virt_vm .. MetricDiskOps
    virt_vm .. MetricDiskLatency
    virt_vm .. MetricDiskErrors

    %% VM memory metrics
    virt_vm .. MetricMemAlloc
    virt_vm .. MetricMemUsed
    virt_vm .. MetricMemBalloon
    virt_vm .. MetricMemSwapped
    virt_vm .. MetricMemRSS
```

**Memory signal semantics (all in bytes):**

```text
virtualization.vm.memory.allocated      = memory committed to the VM by the hypervisor
│
├── virtualization.vm.memory.used       = memory the guest actively uses, as estimated by the hypervisor
├── virtualization.vm.memory.balloon    = memory reclaimed by the balloon driver (host pressure)
├── virtualization.vm.memory.swapped    = memory swapped to hypervisor swap space
└── virtualization.vm.memory.rss        = physical host pages backing this VM (KVM and KubeVirt)
```

The guest operating system's own view of its memory is reported with the upstream
`system.memory.usage` and `system.memory.utilization` metrics, which
`refinement.virtualization.vm.system.memory.usage` and
`refinement.virtualization.vm.system.memory.utilization` associate with `virtualization.vm`.

---

## 5. Virtual Networking & Fabric ERD

The fourth diagram shows the virtual switch entity, its physical NIC uplinks, and VM and
partition network attachments.

```mermaid
classDiagram
    class virt_vswitch["virtualization.vswitch"] {
        +string vswitch_id_IDENTITY
        +string vswitch_name
        +enum system_name
    }

    class virt_vm["virtualization.vm"] {
        +string vm_id_IDENTITY
        +string vm_network_interface_name
    }

    class virt_partition["virtualization.partition"] {
        +string partition_id_IDENTITY
        +string platform_id_IDENTITY
    }

    class MetricNetIO {
        <<metric>>
        +name system_network_io
        +instrument counter
        +unit By
        +dim network_io_direction
    }

    class MetricNetDropped {
        <<metric>>
        +name system_network_packet_dropped
        +instrument counter
        +unit packet
        +dim network_io_direction
    }

    class MetricNetErrors {
        <<metric>>
        +name system_network_errors
        +instrument counter
        +unit error
        +dim network_io_direction
    }

    class MetricHWNetIO {
        <<metric>>
        +name hw_network_io
        +instrument counter
        +unit By
        +dim network_io_direction
    }

    class MetricHWNetBandwidth {
        <<metric>>
        +name hw_network_bandwidth_utilization
        +instrument gauge
        +unit ratio
    }

    class MetricVMNetIO {
        <<metric>>
        +name vm_network_io
        +instrument counter
        +unit By
        +dim network_io_direction
    }

    note for MetricNetIO "system.network.io (refined)\nrefinement.virtualization.system.network.io\nattrs: network.interface.name, network.io.direction,\nvirtualization.vswitch.name (opt-in)"
    note for MetricNetDropped "system.network.packet.dropped (refined)\nrefinement.virtualization.system.network.packet.dropped\nattrs: network.interface.name, network.io.direction,\nvirtualization.vswitch.name (opt-in)"
    note for MetricNetErrors "system.network.errors (refined)\nrefinement.virtualization.system.network.errors\nattrs: network.interface.name, network.io.direction,\nvirtualization.vswitch.name (opt-in)"
    note for MetricHWNetIO "hw.network.io (refined)\nrefinement.virtualization.hw.network.io\nattrs: virtualization.vswitch.name, hw.id, hw.name,\nnetwork.io.direction"
    note for MetricHWNetBandwidth "hw.network.bandwidth.utilization (refined)\nrefinement.virtualization.hw.network.bandwidth.utilization\nattrs: virtualization.vswitch.name, hw.id, hw.name"
    note for MetricVMNetIO "virtualization.vm.network.io\nattrs: virtualization.vm.id,\nvirtualization.vm.network.interface.name, network.io.direction"

    %% Connectivity
    virt_vswitch "1" *-- "0..*" virt_vm : carries traffic for VMs
    virt_vswitch "1" *-- "0..*" virt_partition : carries traffic for partitions

    %% vswitch hw metrics
    virt_vswitch .. MetricHWNetIO
    virt_vswitch .. MetricHWNetBandwidth

    %% VM network metrics
    virt_vm .. MetricNetIO
    virt_vm .. MetricNetDropped
    virt_vm .. MetricNetErrors
    virt_vm .. MetricVMNetIO

    %% Partition network metrics
    virt_partition .. MetricNetIO
    virt_partition .. MetricNetDropped
    virt_partition .. MetricNetErrors
```

**Notes:**

- The `system.network.*` refinements are also associated with `virtualization.vswitch`; the
  diagram shows only the VM and partition associations.
- The `hw.network.*` refinements (`io`, `packets`, `bandwidth.limit`, `bandwidth.utilization`,
  `up`) describe the physical uplink adapters of a virtual switch; `hw.id` identifies the adapter.
- `virtualization.vswitch.id` is unique across management domains. A distributed switch spans
  hosts, so its identifier does not include a host: on VMware vSphere it is the distributed
  switch UUID. Per-host switches are qualified by their host or hypervisor, for example the
  host hardware UUID and switch name for a standard vSwitch, or `3931-45A01/ZVM1/VSWITCH1` for an
  IBM z/VM VSWITCH.

---

## 6. Cross-Platform Topology Lineage

This diagram shows how each enterprise virtualization platform maps its native constructs to the
unified virtualization schema. All paths converge on the same eight entity types and the same
`model/virtualization/` metric definitions. Edge labels show how the identifying attribute is
filled.

```mermaid
flowchart TD
    subgraph IBM_Z_PRSM ["IBM Z — PR/SM (classic and DPM)"]
        Z1["CPC<br/>(Central Processing Complex)"]
        Z2["LPAR<br/>(Logical Partition)"]
        Z3["Shared Processor Pool"]
        Z4["Storage Group<br/>(DPM)"]
    end

    subgraph IBM_Z_ZVM ["IBM Z — z/VM"]
        ZV1["z/VM Hypervisor Instance"]
        ZV2["z/VM Guest<br/>(Virtual Machine)"]
        ZV3["VSWITCH<br/>(z/VM Virtual Switch)"]
    end

    subgraph VMware ["VMware vSphere / ESXi"]
        VS1["ESXi Host<br/>(HostSystem)"]
        VS2["Virtual Machine<br/>(VirtualMachine)"]
        VS3["Resource Pool<br/>(ResourcePool)"]
        VS4["Datastore<br/>(Datastore)"]
        VS5["Cluster<br/>(ClusterComputeResource)"]
        VS6["dvSwitch<br/>(DistributedVirtualSwitch)"]
    end

    subgraph KVM_libvirt ["KVM / libvirt"]
        KV1["Linux KVM Host"]
        KV2["libvirt Domain<br/>(virDomain)"]
        KV3["Linux Bridge / OVS bridge"]
        KV4["libvirt Storage Pool<br/>(virStoragePool)"]
        KV5["libvirt Daemon<br/>(virtqemud)"]
    end

    subgraph OCP_Virt ["OpenShift Virtualization / KubeVirt"]
        OC1["OpenShift Worker Node"]
        OC2["VirtualMachineInstance"]
        OC3["K8s Namespace ResourceQuota"]
        OC4["PVC / StorageClass<br/>(CSI pool)"]
        OC5["OpenShift Cluster"]
        OC6["virt-handler DaemonSet"]
        OC7["OVN-Kubernetes Network"]
    end

    subgraph OTel_Entities ["OTel Virtualization Entities<br/>(model/virtualization/)"]
        direction TB
        E1["virtualization.platform<br/>ibm.prsm / kvm / vmware.esxi"]
        E2["virtualization.partition<br/>ibm.prsm"]
        E3["virtualization.hypervisor<br/>ibm.zvm / kvm / vmware.esxi / openshift_virtualization"]
        E4["virtualization.vm<br/>ibm.zvm / kvm / vmware.esxi / openshift_virtualization"]
        E5["virtualization.cluster"]
        E6["virtualization.resource_pool<br/>ibm.prsm / vmware.esxi / openshift_virtualization"]
        E7["virtualization.vswitch<br/>ibm.zvm / kvm / vmware.esxi"]
        E8["virtualization.storage_pool<br/>ibm.prsm / vmware.esxi / kvm / openshift_virtualization"]
    end

    %% IBM Z PR/SM mappings
    Z1  -->|"virtualization.platform.id = machine type-serial, e.g. 3931-45A01<br/>host.name = CPC name"| E1
    Z2  -->|"virtualization.partition.id = LPAR name<br/>virtualization.platform.id = CPC key"| E2
    Z3  -->|"virtualization.resource_pool.id = CPC key/pool name"| E6
    Z4  -->|"virtualization.storage_pool.id = CPC key/storage group name"| E8

    %% IBM z/VM mappings
    ZV1 -->|"virtualization.hypervisor.id = CPC key/z/VM system name"| E3
    ZV2 -->|"virtualization.vm.id = SSI cluster or system name/userid"| E4
    ZV3 -->|"virtualization.vswitch.id = hypervisor id/VSWITCH name"| E7

    %% VMware vSphere mappings
    VS1 -->|"virtualization.platform.id = host hardware UUID"| E1
    VS1 -->|"virtualization.hypervisor.id = host hardware UUID"| E3
    VS2 -->|"virtualization.vm.id = instanceUuid"| E4
    VS3 -->|"virtualization.resource_pool.id = vCenter UUID/ResourcePool MoRef"| E6
    VS4 -->|"virtualization.storage_pool.id = datastore UUID"| E8
    VS5 -->|"virtualization.cluster.id = vCenter UUID/cluster MoRef"| E5
    VS6 -->|"virtualization.vswitch.id = dvSwitch UUID"| E7

    %% KVM / libvirt mappings
    KV1 -->|"virtualization.platform.id = host machine ID"| E1
    KV2 -->|"virtualization.vm.id = domain UUID"| E4
    KV3 -->|"virtualization.vswitch.id = host machine ID/bridge name"| E7
    KV4 -->|"virtualization.storage_pool.id = pool UUID"| E8
    KV5 -->|"virtualization.hypervisor.id = libvirt host UUID"| E3

    %% OpenShift Virtualization mappings (no identifier fill rules defined yet)
    OC1 -->|"virtualization.system.name = kvm"| E1
    OC2 -->|"virtualization.system.name = openshift_virtualization"| E4
    OC3 -->|"virtualization.system.name = openshift_virtualization"| E6
    OC4 -->|"virtualization.system.name = openshift_virtualization"| E8
    OC5 --> E5
    OC6 -->|"virtualization.system.name = openshift_virtualization"| E3
    OC7 -->|"virtualization.system.name = openshift_virtualization"| E7
```

The attribute definitions give identifier fill rules for IBM Z, VMware vSphere and KVM/libvirt.
For OpenShift Virtualization the diagram shows which native object corresponds to each entity;
identifier fill rules for it are not defined yet.

---

## 7. Entity Identity & Discriminator Reference

| Entity Type | Identity Attributes | `virtualization.system.name` values | How the identifier is filled |
| --- | --- | --- | --- |
| `virtualization.platform` | `virtualization.platform.id` | `ibm.prsm`, `kvm`, `vmware.esxi`, `ibm.powervm`, `hyperv` | IBM Z: `<machine type>-<serial number>` of the CPC, leading zeros removed from the serial, e.g. `3931-45A01`. vSphere: ESXi host hardware UUID. KVM: host machine ID. `host.id` carries the same value. |
| `virtualization.partition` | `virtualization.partition.id` + `virtualization.platform.id` | `ibm.prsm` | IBM Z: LPAR name, unique within the CPC. |
| `virtualization.hypervisor` | `virtualization.hypervisor.id` | `ibm.zvm`, `kvm`, `openshift_virtualization`, `vmware.esxi` | z/VM: system name qualified by the CPC key, e.g. `3931-45A01/ZVM1`. vSphere: ESXi host hardware UUID. KVM: libvirt host UUID. |
| `virtualization.vm` | `virtualization.vm.id` | `ibm.zvm`, `kvm`, `vmware.esxi`, `openshift_virtualization`, `kubevirt`, `hyperv`, `xen` | z/VM: SSI cluster name (or system name outside an SSI cluster) and guest user ID, e.g. `SSIPLEX1/LINUX01`. vSphere: VM `instanceUuid`. KVM: domain UUID. Unique across the live-migration domain. |
| `virtualization.cluster` | `virtualization.cluster.id` | any | z/VM: SSI cluster name. vSphere: vCenter instance UUID + cluster MoRef, e.g. `<vCenter UUID>/domain-c7`. |
| `virtualization.resource_pool` | `virtualization.resource_pool.id` | `ibm.prsm`, `vmware.esxi`, `openshift_virtualization` | IBM Z: CPC key + processor pool name, e.g. `3931-45A01/IFLPOOL`. vSphere: vCenter instance UUID + ResourcePool MoRef. |
| `virtualization.vswitch` | `virtualization.vswitch.id` | `ibm.zvm`, `kvm`, `vmware.esxi`, `openshift_virtualization` | z/VM: hypervisor ID + VSWITCH name, e.g. `3931-45A01/ZVM1/VSWITCH1`. IBM Z DPM: CPC key + virtual switch name. vSphere: distributed switch UUID (standard vSwitch: host hardware UUID + switch name). KVM: host machine ID + bridge or Open vSwitch name. |
| `virtualization.storage_pool` | `virtualization.storage_pool.id` | `ibm.prsm`, `vmware.esxi`, `kvm`, `openshift_virtualization` | IBM Z DPM: CPC key + storage group name, e.g. `3931-45A01/SG-PROD`. vSphere: datastore UUID. KVM: storage pool UUID. |

Identifying values MUST be the same for every observer of the entity and MUST NOT change during
its lifetime. On IBM Z the CPC key and the LPAR name are reported by the HMC Web Services API,
z/OS RMF (SMF type 70) and Linux on IBM Z (`/proc/sysinfo`) alike; HMC object IDs are visible to
HMC API clients only and are therefore not used as identifiers. The corresponding `*.name`
attributes, `host.name` and `virtualization.vm.instance_id` are descriptive.

---

## 8. `virtualization.partition.cpu.type` Attribute Dimension

The `virtualization.partition.cpu.type` attribute is the IBM Z-specific dimension in the
virtualization metrics. It is used by two refinements of upstream metrics and by three net-new
partition metrics:

```mermaid
classDiagram
    %% ── Metrics that carry this dimension ─────────────────────────────────
    class M_cpu_time["system.cpu.time"] {
        <<refinement>>
        +instrument counter
        +unit s
        +dim partition_cpu_type_opt_in
    }
    class M_cpu_util["system.cpu.utilization"] {
        <<refinement>>
        +instrument gauge
        +unit ratio
        +dim partition_cpu_type_opt_in
    }
    class M_part_util["virtualization.partition.cpu.utilization"] {
        <<net-new>>
        +instrument gauge
        +unit ratio
        +dim partition_cpu_type
    }
    class M_part_time["virtualization.partition.cpu.time"] {
        <<net-new>>
        +instrument counter
        +unit s
        +dim partition_cpu_type
    }
    class M_part_count["virtualization.partition.cpu.count"] {
        <<net-new>>
        +instrument updowncounter
        +unit vcpu
        +dim partition_cpu_type
    }

    note for M_cpu_time "refinement.virtualization.system.cpu.time\nentities: platform, partition, vm"
    note for M_cpu_util "refinement.virtualization.system.cpu.utilization\nentities: platform, partition, vm"
    note for M_part_count "entity: virtualization.partition"

    %% ── Enum values of virtualization.partition.cpu.type ──────────────────
    class CpuType["virtualization.partition.cpu.type"] {
        <<attribute enum>>
        +cp Central Processor
        +ifl Integrated Facility for Linux
        +icf Internal Coupling Facility
        +iip z Integrated Information Processor
        +cbp Container Based Processor
        +aap Application Assist Processor
        +all aggregate across all types
        +unknown not differentiated
    }

    note for CpuType "cp: general-purpose processor\nifl: Linux workloads\nicf: sysplex coupling\niip: zIIP, eligible Java and Db2 work\ncbp: SE 2.14.0 to 2.15.0 only\naap: zAAP, deprecated in z13 and later\nall: aggregate across all types\nunknown: platform does not differentiate"

    M_cpu_time   -- CpuType : split by
    M_cpu_util   -- CpuType : split by
    M_part_util  -- CpuType : split by
    M_part_time  -- CpuType : split by
    M_part_count -- CpuType : split by
```

On platforms that do not differentiate processor types (VMware, KVM, OpenShift Virtualization),
`virtualization.partition.cpu.type` is omitted or set to `unknown`. Unified dashboards therefore
work across platforms while still providing the IBM Z processor-type breakdown. Use `all` to
report a value aggregated across all processor types.

---

## 9. `virtualization.vm.disk.direction` Splitting Pattern

The VM disk metrics use the `virtualization.vm.disk.direction` attribute to split read and write
measurements into separate time series:

```mermaid
classDiagram
    %% ── Enum values ───────────────────────────────────────────────────────
    class dir_read["read"] {
        <<enum value>>
        +desc data read from virtual disk
    }
    class dir_write["write"] {
        <<enum value>>
        +desc data written to virtual disk
    }

    %% ── Metrics split by this dimension ───────────────────────────────────
    class M_disk_io["virtualization.vm.disk.io"] {
        <<net-new>>
        +instrument counter
        +unit By
        +dim disk_direction_required
    }
    class M_disk_ops["virtualization.vm.disk.operations"] {
        <<net-new>>
        +instrument counter
        +unit operation
        +dim disk_direction_required
    }
    class M_disk_lat["virtualization.vm.disk.latency.time"] {
        <<net-new>>
        +instrument counter
        +unit s
        +dim disk_direction_required
    }
    class M_disk_err["virtualization.vm.disk.errors"] {
        <<net-new>>
        +instrument counter
        +unit error
        +dim disk_direction_recommended
    }

    note for M_disk_io "attrs: virtualization.vm.id (required),\nvirtualization.vm.disk.name (recommended)"
    note for M_disk_ops "attrs: virtualization.vm.id (required),\nvirtualization.vm.disk.name (recommended)"
    note for M_disk_lat "avg latency = rate(latency.time) / rate(operations)\nattrs: virtualization.vm.id, virtualization.vm.disk.name"
    note for M_disk_err "attrs: virtualization.vm.id (required),\nvirtualization.vm.disk.name (recommended)"

    %% ── Each metric is split by read and write ────────────────────────────
    dir_read  .. M_disk_io
    dir_write .. M_disk_io

    dir_read  .. M_disk_ops
    dir_write .. M_disk_ops

    dir_read  .. M_disk_lat
    dir_write .. M_disk_lat

    dir_read  .. M_disk_err
    dir_write .. M_disk_err
```

`virtualization.vm.disk.direction` is required on `virtualization.vm.disk.io`,
`virtualization.vm.disk.operations` and `virtualization.vm.disk.latency.time`, and recommended on
`virtualization.vm.disk.errors`, because some platforms report errors without a direction.

---

## 10. Multi-tenant Isolation Patterns

When deploying virtualization observability in multi-tenant environments, use the following
filters to isolate telemetry by platform and tenant. Filter on identifiers rather than names:
names can change and are not unique across management domains.

| Isolation dimension | Prometheus label filter | OTel attribute |
| --- | --- | --- |
| IBM Z PR/SM only | `{virtualization_system_name="ibm.prsm"}` | `virtualization.system.name` |
| IBM z/VM guests only | `{virtualization_system_name="ibm.zvm"}` | `virtualization.system.name` |
| VMware ESXi only | `{virtualization_system_name="vmware.esxi"}` | `virtualization.system.name` |
| KVM VMs only | `{virtualization_system_name="kvm"}` | `virtualization.system.name` |
| OpenShift VMs only | `{virtualization_system_name="openshift_virtualization"}` | `virtualization.system.name` |
| Single vSphere cluster | `{virtualization_cluster_id="1b9c0e2a-6f4d-4a52-9d3e-0c7d1e2f3a4b/domain-c7"}` | `virtualization.cluster.id` |
| Single CPC (IBM Z) | `{virtualization_platform_id="3931-45A01"}` | `virtualization.platform.id` |
| Single LPAR | `{virtualization_platform_id="3931-45A01", virtualization_partition_id="PRODZ"}` | `virtualization.platform.id`, `virtualization.partition.id` |
| K8s namespace VMs | `{k8s_namespace_name="my-team"}` | `k8s.namespace.name` |
| Specific resource pool | `{virtualization_resource_pool_id="3931-45A01/IFLPOOL"}` | `virtualization.resource_pool.id` |

The label names assume that Prometheus translates attribute names by replacing dots with
underscores; with UTF-8 metric and label names the attribute names are used unchanged. Identity
attributes are resource attributes: they appear as series labels only if Prometheus promotes them
(`promote_resource_attributes` in its OTLP configuration) or the collector copies them to the data
points; otherwise they are available on the `target_info` series.
