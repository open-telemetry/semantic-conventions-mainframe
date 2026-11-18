<!---
This file is hand-authored. Do NOT regenerate or overwrite.
See docs/hmc-api-signal-mapping.md for the OTel ↔ HMC field mapping tables.
--->

# IBM Z HMC Web Services API — Implementation Background

This document describes the architecture, entity construction, unit conversion rules,
collector pipeline patterns and platform-specific caveats that a collector author needs to
implement the semantic conventions defined in `model/mainframe/` and `model/virtualization/`
from the IBM Z Hardware Management Console (HMC) Web Services API.

The authoritative per-signal HMC source is recorded in the model YAML files, in the
`annotations.hmc_source` block of each metric, metric refinement and attribute. This document
provides the structural context that makes those annotations actionable. The complete OTel
signal → HMC field cross-reference is in `docs/hmc-api-signal-mapping.md`; the signal
definitions themselves (instrument, unit, attributes, entity association) are on the generated
registry pages under [docs/registry/mainframe/](registry/mainframe/README.md) and
[docs/registry/virtualization/](registry/virtualization/README.md).

---

## 1. Architecture Overview

The HMC manages one or more Central Processing Complexes (CPCs). The objects of the HMC API map
to OTel entities as follows:

```text
HMC (Web Services API endpoint)
└── Central Processing Complex / CPC          → virtualization.platform (+ refinements of host)
    ├── Processor (CP, IFL, zIIP, ICF, SAP, …)    → mainframe.cpu
    ├── Shared processor pool                     → virtualization.resource_pool
    ├── Memory (installed, HSA, central, VFM)     → mainframe.host.memory.* metrics on virtualization.platform
    ├── Logical partition / LPAR   [classic]      → virtualization.partition  (virtualization.system.name = "ibm.prsm")
    │   └── z/VM running in the LPAR              → virtualization.hypervisor (virtualization.system.name = "ibm.zvm")
    ├── Partition                  [DPM]          → virtualization.partition  (virtualization.system.name = "ibm.prsm")
    │   └── NIC                                   → mainframe.partition.nic
    ├── Channel path (CSS.CHPID)                  → mainframe.channel
    ├── Adapter (PCHID)                           → mainframe.adapter
    │   └── Network port                          → mainframe.adapter.port
    ├── Virtual switch             [DPM]          → virtualization.vswitch
    └── Storage group              [DPM]          → mainframe.storage.group and virtualization.storage_pool
        └── Storage volume                        → mainframe.storage.group.volume
```

**Key design decisions:**

- The CPC maps to `virtualization.platform`. All CPC environmental, power, processor-count,
  utilization and memory metrics — the `mainframe.host.*` metrics and the generic
  `virtualization.platform.*` metrics — are associated with `virtualization.platform`. There is
  no separate mainframe host entity type. Two entity refinements describe the CPC further:
  `refinement.mainframe.host.virtualization.platform` adds `mainframe.host.machine_type`,
  `mainframe.host.machine_model` and `mainframe.host.serial_number` to the platform, and
  `refinement.mainframe.host` presents the CPC as a generic `host`, identified by `host.id`.
- Identity is the same for every observer. A CPC or LPAR is observed by the HMC, by z/OS
  (RMF, SMF type 70) and by Linux on IBM Z (`/proc/sysinfo`). Identifying values are therefore
  taken from data all three report — machine type, serial number and LPAR name — and not from
  HMC object IDs or URIs, which only HMC API clients can see.
- Every CPC-scoped mainframe entity (processor, channel, adapter, adapter port, partition NIC,
  storage group and volume) includes `virtualization.platform.id` in its identity, because one HMC
  manages several CPCs and the local keys repeat across them.
- The `virtualization.system.name` discriminator for all PR/SM entities is `ibm.prsm`; for z/VM it
  is `ibm.zvm`.
- Classic mode and DPM mode both use `virtualization.partition` for LPARs and DPM partitions; the
  HMC object class differs (`logical-partition` in classic mode, `partition` in DPM mode).
- Crypto, Flash Express, RoCE, network, storage and accelerator adapters all map to
  `mainframe.adapter`, discriminated by `mainframe.adapter.type`.

---

## 2. Entity Instance Construction

### 2.1 `virtualization.platform` — CPC

| OTel Attribute | HMC API Source | Object Class | Notes |
| --- | --- | --- | --- |
| `virtualization.platform.id` *(identity)* | `machine-type` + `-` + `cpc-serial-number` | CPC | Leading zeros removed from the serial, e.g. `3931-45A01`. See [The CPC key](#the-cpc-key). |
| `host.id` | same value | CPC | SHOULD equal `virtualization.platform.id`; identity of `refinement.mainframe.host`. |
| `host.name` | `name` | CPC | CPC name, e.g. `T01`. Descriptive: a CPC can be renamed without becoming a different CPC. |
| `host.type` | `machine-type` + `-` + `machine-model` | CPC | e.g. `3931-A01`. |
| `host.arch` | *static* | — | `s390x`. |
| `virtualization.system.name` | *static* | — | `ibm.prsm`. |
| `virtualization.platform.serial_number` | serial number | CPC | Hardware serial as reported by the HMC. |
| `virtualization.platform.firmware.version` | SE driver or MCL level | CPC | As reported by the HMC. |
| `mainframe.host.machine_type` | `machine-type` | CPC | IBM machine type, e.g. `3931`. |
| `mainframe.host.machine_model` | `machine-model` | CPC | Model, e.g. `A01`. |
| `mainframe.host.serial_number` | `serial-number` | CPC | As named in the `hmc_source` annotation of the attribute.¹ |

¹ The identity rule of `virtualization.platform.id` names the CPC property `cpc-serial-number`,
while the `hmc_source` annotation of `mainframe.host.serial_number` names `serial-number`. Both
are meant to carry the CPC serial; the property name is to be reconciled in the model.

#### The CPC key

Machine type and serial number are the only CPC identifiers that every observer reports:

| Observer | Machine type | Serial | LPAR |
| --- | --- | --- | --- |
| HMC Web Services API (CPC and partition objects) | `machine-type` | `cpc-serial-number` (12 characters) | partition `name` |
| z/OS RMF, SMF type 70 subtype 1 | `SMF70CPC_TYPE` | `SMF70CSC` (configuration sequence code) | `SMF70LPM` (name), `SMF70LPN` (number) |
| Linux on IBM Z, `/proc/sysinfo` | `Type` | `Sequence Code` (16 characters) | `LPAR Name`, `LPAR Number` |

The canonical form is `<machine type>-<serial without leading zeros>`, e.g. `3931-45A01` for
machine type `3931` and sequence code `0000000000045A01`. This assumes that the HMC serial and the
sequence code are the same number with different zero padding; this, the role of the plant of
manufacture and the LPAR name of DPM partitions are open points for the Mainframe SIG.

### 2.2 `virtualization.partition` — LPAR (classic) / Partition (DPM)

| OTel Attribute | HMC API Source | Object Class | Notes |
| --- | --- | --- | --- |
| `virtualization.partition.id` *(identity)* | `name` | `logical-partition` / `partition` | LPAR name, e.g. `LINUX1`; the same value as SMF `SMF70LPM` and `/proc/sysinfo` `LPAR Name`. |
| `virtualization.platform.id` *(identity)* | CPC key of the parent CPC | CPC | LPAR names are unique only within a CPC. |
| `virtualization.system.name` | *static* | — | `ibm.prsm`. |
| `virtualization.partition.name` | `name` | `logical-partition` / `partition` | |
| `virtualization.partition.number` | `partition-number` | `logical-partition` | Classic mode only. |
| `virtualization.partition.type` | `activation-mode` (classic); `type` (DPM) | `logical-partition` / `partition` | Map to `general_purpose`, `linux_only`, `ssc` or `unknown`. |
| `virtualization.partition.state` | `status` | `logical-partition` / `partition` | Map `operating` (classic) and `active` (DPM) → `active`, `not-activated` → `not_activated`, `stopped` → `stopped`, other values → `unknown`. The full HMC status is the metric attribute `mainframe.partition.status`. |
| `mainframe.partition.name` | `name` | `logical-partition` / `partition` | Added by `refinement.mainframe.partition.virtualization.partition`. |
| `mainframe.partition.number` | `partition-number` | `logical-partition` | Classic mode only. |
| `mainframe.partition.type` | `activation-mode` | `logical-partition` | Classic mode. |

### 2.3 `mainframe.cpu` — Processor

| OTel Attribute | HMC API Source | Object Class | Notes |
| --- | --- | --- | --- |
| `virtualization.platform.id` *(identity)* | CPC key of the parent CPC | CPC | Processor names repeat on every CPC. |
| `mainframe.cpu.name` *(identity)* | `name` | `processor` | e.g. `CP02`, `IFL01`. |
| `mainframe.cpu.type` | `type` | `processor` | `cp`, `ifl`, `iip`, `icf`, `sap`, `aap`, `cbp`. |

### 2.4 `virtualization.resource_pool` — Shared processor pool

| OTel Attribute | HMC API Source | Object Class | Notes |
| --- | --- | --- | --- |
| `virtualization.resource_pool.id` *(identity)* | CPC key + `/` + pool name | shared processor pool | e.g. `3931-45A01/IFLPOOL`. |
| `virtualization.resource_pool.name` | pool name | shared processor pool | |
| `virtualization.system.name` | *static* | — | `ibm.prsm`. |
| `mainframe.cpu.type` | `processor-type` | shared processor pool | Added by `refinement.mainframe.processor_pool.virtualization.resource_pool`. |

### 2.5 `mainframe.channel` — Channel Path

| OTel Attribute | HMC API Source | Object Class | Notes |
| --- | --- | --- | --- |
| `virtualization.platform.id` *(identity)* | CPC key of the parent CPC | CPC | |
| `mainframe.channel.name` *(identity)* | `channel-path-id` | `channel-path` | In `CSS.CHPID` form, e.g. `0.2D`, which is unique within a CPC. |
| `mainframe.channel.id` | `channel-path-id` | `channel-path` | Bare CHPID, e.g. `2D`; repeats across channel subsystems, so descriptive. |
| `mainframe.channel.type` | `type` | `adapter` | Map to `ficon`, `zhyperlink`, `osa`, `roce` or `coupling`. |
| `mainframe.channel.mode` | `shared-channel` | `channel-usage` metric group | Classic mode; `shared` or `dedicated`. |
| `mainframe.channel.owning.partition` | `logical-partition-name` | `channel-usage` metric group | Classic mode; LPAR name, `shared`, or empty for channel types without an owning partition. |

### 2.6 `mainframe.adapter` — I/O Adapter

| OTel Attribute | HMC API Source | Object Class | Notes |
| --- | --- | --- | --- |
| `virtualization.platform.id` *(identity)* | CPC key of the parent CPC | CPC | |
| `mainframe.adapter.id` *(identity)* | `adapter-id` | `adapter` | PCHID, the adapter's location in the CPC, e.g. `014`. |
| `mainframe.adapter.name` | `name` | `adapter` | User-assignable, so descriptive, e.g. `OSD 0114`. |
| `mainframe.adapter.type` | `type` | `adapter` | Map to `crypto`, `flash`, `roce`, `accelerator`, `network` or `storage`. |
| `mainframe.adapter.owning.partition` | `partitions-assigned-to-adapter` | `adapter` | DPM mode; partition name, or `shared` when more than one partition is assigned. |

### 2.7 `mainframe.adapter.port` — Physical Adapter Port (DPM)

| OTel Attribute | HMC API Source | Object Class | Notes |
| --- | --- | --- | --- |
| `virtualization.platform.id` *(identity)* | CPC key of the parent CPC | CPC | |
| `mainframe.adapter.id` *(identity)* | `adapter-id` of the parent adapter | `adapter` | PCHID. |
| `mainframe.adapter.port.id` *(identity)* | `network-port-id` | `network-physical-adapter-port` | DPM, HMC 2.13.1 or later. |
| `host.name` | `name` of the parent CPC | CPC | Descriptive. |

### 2.8 `mainframe.partition.nic` — Partition NIC (DPM)

| OTel Attribute | HMC API Source | Object Class | Notes |
| --- | --- | --- | --- |
| `virtualization.platform.id` *(identity)* | CPC key of the parent CPC | CPC | |
| `virtualization.partition.id` *(identity)* | `name` of the parent partition | `partition` | |
| `mainframe.partition.nic.name` *(identity)* | `nic-id` | `partition-attached-network-interface` | DPM, HMC 2.13.1 or later. |
| `mainframe.adapter.id`, `mainframe.adapter.port.id` | backing adapter and port | `adapter` | Descriptive: the physical port behind the NIC. |
| `host.name` | `name` of the CPC | CPC | Descriptive. |

### 2.9 `virtualization.vswitch` — Virtual Switch

| OTel Attribute | HMC API Source | Object Class | Notes |
| --- | --- | --- | --- |
| `virtualization.vswitch.id` *(identity)* | DPM: CPC key + `/` + `name` | `virtual-switch` (DPM) | e.g. `3931-45A01/104.P0.OSD`. A z/VM VSWITCH is not an HMC object; its ID is the z/VM hypervisor ID + `/` + VSWITCH name, e.g. `3931-45A01/ZVM1/VSWITCH1`. |
| `virtualization.vswitch.name` | `name` | `virtual-switch` (DPM) | |
| `mainframe.vswitch.name` | `name` | `virtual-switch` (DPM) | Added by `refinement.mainframe.vswitch.virtualization.vswitch`. |

### 2.10 DPM Storage Groups — `virtualization.storage_pool`, `mainframe.storage.group`, `mainframe.storage.group.volume`

A DPM storage group is represented both as the generic `virtualization.storage_pool` and as the
DPM-specific `mainframe.storage.group`. Storage groups require DPM and HMC 2.14.1 or later.

| OTel Attribute | HMC API Source | Object Class | Notes |
| --- | --- | --- | --- |
| `virtualization.storage_pool.id` *(identity of the storage pool)* | CPC key + `/` + `name` | `storage-group` | e.g. `3931-45A01/SG-PROD`. |
| `virtualization.storage_pool.name` | `name` | `storage-group` | |
| `virtualization.system.name` | *static* | — | `ibm.prsm`. |
| `virtualization.platform.id` *(identity of storage group and volume)* | CPC key of the owning CPC | CPC | |
| `mainframe.storage.group.name` *(identity of storage group and volume)* | `name` | `storage-group` | |
| `mainframe.storage.group.type` | `type` | `storage-group` | `fcp`, `fc` or `nvme`. |
| `mainframe.storage.group.volume.name` *(identity of the volume)* | `name` | `storage-volume` | |
| `mainframe.storage.fulfillment.state` | `fulfillment-state` | `storage-group` / `storage-volume` | Metric attribute. |

### 2.11 z/VM — `virtualization.hypervisor` and `virtualization.vm`

| OTel Attribute | Source | Notes |
| --- | --- | --- |
| `virtualization.hypervisor.id` *(identity)* | CPC key + `/` + z/VM system name | e.g. `3931-45A01/ZVM1`. |
| `mainframe.zvm.hypervisor.name` | logical-partition `name` | The LPAR that runs z/VM (classic mode). |
| `virtualization.vm.id` *(identity)* | SSI cluster name (or z/VM system name outside an SSI cluster) + `/` + guest user ID | e.g. `SSIPLEX1/LINUX01`; survives Live Guest Relocation. |
| `mainframe.zvm.guest.userid` | z/VM user directory | The model records no `hmc_source` for this attribute. |

---

## 3. HMC API Access Patterns

### 3.1 Metrics Service (metric groups)

The primary source for time-series telemetry is the HMC metrics service, which reports the
metric groups listed in `docs/hmc-api-signal-mapping.md`:

```text
POST   /api/services/metrics/context        → create a metrics context for the wanted metric groups
GET    /api/services/metrics/context/{id}   → retrieve the current sample of all requested groups
DELETE /api/services/metrics/context/{id}   → delete the context
```

The [zhmc-prometheus-exporter](https://github.com/zhmcclient/zhmc-prometheus-exporter) uses the
metrics service and exposes Prometheus metrics that the OTel Collector `prometheus` receiver
scrapes. The exporter manages the metrics context; custom collectors must recreate a context
when the HMC no longer knows it.

### 3.2 Object Property Polling (REST)

Configuration properties (processor counts, memory sizes, partition weights, capping, status)
are properties of the managed objects, read with `GET /api/cpcs/{cpc-id}`,
`GET /api/logical-partitions/{id}` (classic mode) and `GET /api/partitions/{id}` (DPM mode).
They are not part of the metric groups. The `zhmc-prometheus-exporter` also derives metrics from
object properties and keeps them current through HMC property change notifications.

---

## 4. Unit Conversion Reference

The `hmc_source` annotations record a `unit_transformation` wherever the HMC unit differs from the
OTel unit declared on the metric. All byte quantities are emitted in `By`.

| HMC Unit | OTel Unit | Formula | Applies To |
| --- | --- | --- | --- |
| `%` (integer 0–100) | `1` | `value / 100` | All `*-usage` utilization fields of the metric groups, and `humidity` |
| BTU/h | `J/h` | `value * 1055.06` | `heat-load`, `heat-load-forced-air`, `heat-load-water` |
| MiB | `By` | `value * 1048576` | CPC `storage-total-installed`, `storage-hardware-system-area`, `storage-customer`, `storage-customer-central`, `storage-customer-expanded`, `storage-customer-available`; logical partition `storage-central-allocation`, `storage-expanded-allocation`; DPM partition `initial-memory`, `reserved-memory`, `maximum-memory` |
| GiB | `By` | `value * 1073741824` | CPC `storage-vfm-total`, `storage-vfm-increment-size` |
| GiB (fractional) | `By` | `round(value * 1073741824)` | Storage volume `size` |
| W | `W` | none | `power`, `total-partition-power-consumption`, `total-infrastructure-power-consumption`, `total-unassigned-power-consumption`, `linecord-*-power-phase-*`, logical partition `power-consumption` |
| °C | `Cel` | none | `dew-point` |

### Percentage Normalization

The utilization and humidity fields of the metric groups are integer percentages in the range
0–100. Divide by 100 to obtain the 0–1 ratio that the OTel metrics declare (unit `1`).

The partition processing weights (`initial-processing-weight`, `minimum-processing-weight`,
`current-processing-weight`, `maximum-processing-weight`) are integers in the range 1–999 and are
reported unchanged as `virtualization.partition.cpu.weight`. The weight category is the attribute
`mainframe.partition.weight.type`, added by the metric refinement
`refinement.mainframe.virtualization.partition.cpu.weight`.

### Absolute Capping

`mainframe.partition.cpu.capped.count` is a `double` value in processors; 0 means that no absolute
capping is configured.

- Classic mode: the logical-partition properties `absolute-processing-capping` (`cp`),
  `absolute-ifl-capping` (`ifl`), `absolute-cf-capping` (`icf`), `absolute-ziip-capping` (`iip`)
  and `absolute-aap-capping` (`aap`) are objects with `type` and `value`. Report `value` when
  `type` is `processors`, otherwise 0.
- DPM mode: report `cp-absolute-processor-capping-value` (`cp`) and
  `ifl-absolute-processor-capping-value` (`ifl`) when the booleans
  `cp-absolute-processor-capping` and `ifl-absolute-processor-capping` are true, otherwise 0.
- Caps can be fractional; a cap of half a processor is reported as 0.5.

---

## 5. Collector Pipeline

### 5.1 zhmc-prometheus-exporter + Prometheus receiver

The `zhmc-prometheus-exporter` (IBM, open source) queries the HMC Web Services API and exposes
Prometheus metrics. The OTel Collector `prometheus` receiver scrapes them and converts them to
OTLP.

**HMC metric groups used by the conventions:**

```yaml
metric_groups:
  - cpc-usage-overview                      # classic mode
  - dpm-system-usage-overview               # DPM mode
  - logical-partition-usage                 # classic mode
  - partition-usage                         # DPM mode
  - zcpc-environmentals-and-power
  - environmental-power-status
  - zcpc-processor-usage
  - channel-usage                           # classic mode
  - crypto-usage                            # classic mode
  - flash-memory-usage                      # classic mode
  - adapter-usage                           # DPM mode
  - network-physical-adapter-port           # DPM mode
  - partition-attached-network-interface    # DPM mode
```

**Mapping exporter labels to OTel attributes:** the exporter labels its series with names such as
the CPC and partition name; the label names depend on the exporter version and its metric
definition file. The CPC key is not one of the exporter labels, so the collector has to add it.
Because one HMC manages a small, known set of CPCs, a static mapping per CPC name is sufficient:

```yaml
processors:
  transform/hmc_semconv:
    metric_statements:
      - context: datapoint
        statements:
          # Adjust the source label names ("cpc", "partition") to your exporter.
          - set(attributes["host.name"], attributes["cpc"])
          - set(attributes["virtualization.platform.id"], "3931-45A01") where attributes["cpc"] == "CPC1"
          - set(attributes["virtualization.platform.id"], "3932-1B2C3") where attributes["cpc"] == "CPC2"
          - set(attributes["virtualization.partition.id"], attributes["partition"]) where attributes["partition"] != nil
          - set(attributes["virtualization.system.name"], "ibm.prsm")
```

The identifying attributes belong on the resource of the entity they identify. To move them from
data point attributes to resource attributes, group the data points by those keys with the
`groupbyattrs` processor (for example `keys: [virtualization.platform.id, virtualization.partition.id]`).

### 5.2 Counter Resets

The network port and partition NIC fields (`bytes-sent`, `bytes-received`, `packets-*`) feed the
refined `system.network.*` counters. After a CPC IML, or when a metrics context is recreated, the
HMC counters restart at zero. Report them as cumulative sums with a new start time; Prometheus
`rate()` and `increase()` treat the drop as a counter reset. No conversion processor is needed.

The utilization fields (`*-usage`) are gauges sampled per interval, not counters.

---

## 6. Platform-Specific Caveats

| Topic | Detail |
| --- | --- |
| **Classic vs. DPM mode** | Classic mode uses `logical-partition` objects and the `logical-partition-usage` metric group. DPM mode uses `partition` objects and `partition-usage`. Detect the mode with the CPC property `dpm-enabled`. |
| **Processor type cardinality** | `cpc-usage-overview` reports utilization per processor type (CP, IFL, zIIP, ICF) and sharing mode; select with `mainframe.cpu.type` and `mainframe.cpu.sharing.mode`. Not every processor type is installed on every CPC. In DPM mode, `partition-usage` reports only an aggregate `processor-usage`, so `mainframe.cpu.type` is not set on `mainframe.partition.cpu.utilization`. |
| **Processor counts** | `mainframe.host.cpu.active.count` reports all active processor types, including SAP (`processor-count-service-assist`, `mainframe.cpu.type` = `sap`) and Container Based Processors (`processor-count-cbp`, `mainframe.cpu.type` = `cbp`, HMC/SE 2.14.0 through 2.15.0 only). |
| **Virtual Flash Memory** | `storage-vfm-total` requires HMC 2.14.0 or later and is `0` on CPCs without VFM. Consider dropping zero values to avoid meaningless series. |
| **HMC API version gates** | `network-physical-adapter-port`, `partition-attached-network-interface`, the DPM `partition-usage` group and the adapter `status` require HMC 2.13.1 or later; storage groups and volumes require 2.14.1; power cord metrics (`environmental-power-status`) require 2.15.0. The `min_hmc_version` field of each `hmc_source` entry records the gate. Read the API version with `GET /api/version`. |
| **Metrics context lifecycle** | A metrics context does not exist forever. The `zhmc-prometheus-exporter` manages it; custom collectors must detect an invalid context URI and create a new context. |
| **Humidity unit** | `humidity` is an integer percentage (0–100). The OTel metric `mainframe.host.humidity` has unit `1`; divide by 100. |
| **Storage group capacity** | The HMC API exposes no storage-group capacity or allocation property. `mainframe.storage.group.capacity` and `mainframe.storage.group.usage` are derived, for example by summing the `size` of the group's volumes. |

---

## 7. Relationship to Generated Registry Documentation

The signal-level details (instrument, unit, stability, entity association, attributes) are
authoritative on the generated registry pages under `docs/registry/mainframe/` and
`docs/registry/virtualization/`. Each metric, metric refinement and attribute with an HMC source
carries an `annotations.hmc_source` block that records the HMC object class or metric group,
field name, operating mode, minimum HMC version and unit transformation.

When the Weaver templates can render custom annotation blocks, the `hmc_source` annotations
will be shown on the generated metric pages. Until then, the cross-reference is maintained by
hand in `docs/hmc-api-signal-mapping.md`.
