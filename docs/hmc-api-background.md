<!---
This file is hand-authored. Do NOT regenerate or overwrite.
See docs/hmc-api-signal-mapping.md for the full OTel ↔ HMC field mapping tables.
--->

# IBM Z HMC Web Services API — Implementation Background

This document describes the architecture, entity construction, unit conversion rules,
collector pipeline patterns, and platform-specific caveats that a collector author needs
to implement the semantic conventions defined in `model/mainframe/` and
`model/virtualization/`.

The authoritative **per-metric HMC source field** is embedded directly in each model YAML
file under the `annotations.hmc_source` block. This document provides the structural
context that makes those annotations actionable.

For the complete OTel metric → HMC field cross-reference table see
[hmc-api-signal-mapping.md](hmc-api-signal-mapping.md).

---

## 1. Architecture Overview

The IBM Z HMC manages a Central Processor Complex (CPC) through a six-tier hardware and
virtualization hierarchy. Each tier maps to a canonical OTel entity:

```
HMC Management Console (REST API endpoint)
└── Central Processor Complex / CPC  (mainframe.host + virtualization.platform)
    ├── Processor Pool (CP, IFL, zIIP, ICF, SAP, IFP)  → attributes on mainframe.host
    ├── Memory Subsystem (Central Storage, VFM)          → attributes on mainframe.host / virtualization.platform
    ├── Logical Partition / LPAR       [Classic mode]    → virtualization.partition  (system.name = "ibm.prsm")
    │   └── Reserved / Offline Processors               → mainframe.partition
    ├── DPM Partition                  [DPM mode]        → virtualization.partition  (system.name = "ibm.prsm")
    │   └── Attached Virtual NIC                        → mainframe.partition.nic
    ├── Channel Path (CHPID)                             → mainframe.channel
    │   ├── FICON / ESCON storage channels
    │   ├── OSA-Express / RoCE Express network channels
    │   └── zHyperLink PCIe coupling channels
    ├── Physical Adapter (Crypto Express, Flash, RoCE)   → mainframe.adapter
    │   └── Physical Port                               → mainframe.adapter.port
    └── DPM Storage Group (NVMe, FICON, FCP)             → mainframe.storage.group
        └── Storage Volume                              → mainframe.storage.group.volume
```

**Key design decisions:**

- The CPC maps to `virtualization.platform` (the PR/SM firmware partitioning layer). All CPC
  environmental, power, processor-count, and memory metrics are associated with
  `virtualization.platform` in the model. There is no standalone `mainframe.host` entity type;
  `refinement.mainframe.host` is a host entity *refinement* that adds mainframe-specific
  descriptive attributes (`mainframe.host.machine_type`, etc.) to the base `host` entity.
- The `virtualization.system.name` discriminator for all PR/SM entities is `ibm.prsm`.
- Classic mode and DPM mode both use `virtualization.partition` for LPARs/DPM partitions;
  the HMC API object class differs (`logical-partition` in Classic, `partition` in DPM).
- Crypto Express, Flash Memory, and RoCE adapters all map to `mainframe.adapter`
  discriminated by `mainframe.adapter.type`.

---

## 2. Entity Instance Construction

### 2.1 `virtualization.platform` — CPC as PR/SM Platform (primary entity for CPC metrics)

All `mainframe.host.*` metrics are associated with `virtualization.platform` in the model.
The CPC also carries a `refinement.mainframe.host` host entity refinement that adds
mainframe-specific descriptive attributes; those are populated on the same resource.

| OTel Attribute | HMC API Source | Object Class | Notes |
| --- | --- | --- | --- |
| `host.name` *(identity)* | `name` | `CPC` | Short CPC name, e.g. `T01`. |
| `virtualization.system.name` | *static* | — | Hardcode `ibm.prsm`. |
| `virtualization.platform.id` | `object-uri` UUID | `CPC` | HMC-assigned object identifier. |
| `virtualization.platform.firmware.version` | SE firmware version | — | From HMC version info API endpoint. |

### 2.2 `refinement.mainframe.host` — Mainframe-specific CPC descriptors (host entity refinement)

These attributes extend the base `host` entity on the same `virtualization.platform` resource.

| OTel Attribute | HMC API Source | Object Class | Notes |
| --- | --- | --- | --- |
| `mainframe.host.machine_type` | `machine-type` | `CPC` | IBM Z model, e.g. `3932` (z17), `3931` (z16). |
| `mainframe.host.machine_model` | `machine-model` | `CPC` | Model suffix, e.g. `A01`. |
| `mainframe.host.serial_number` | `serial-number` | `CPC` | Hardware serial, e.g. `12A3456`. |
| `host.id` | `serial-number` | `CPC` | Prefer serial for human readability. |
| `host.type` | `machine-type` + `-` + `machine-model` | `CPC` | e.g. `3932-A01`. |
| `host.arch` | *static* | — | Hardcode `s390x`. |

### 2.3 `virtualization.partition` — LPAR (Classic) / Partition (DPM)

| OTel Attribute | HMC API Source | Object Class | Notes |
| --- | --- | --- | --- |
| `virtualization.partition.id` *(identity)* | `object-uri` UUID | `logical-partition` / `partition` | UUID string. |
| `virtualization.platform.id` *(identity)* | parent CPC `object-uri` | `CPC` | Composite key — partition IDs are only unique per CPC. |
| `virtualization.system.name` | *static* | — | `ibm.prsm`. |
| `virtualization.partition.name` | `name` | `logical-partition` / `partition` | Partition label, e.g. `LINUX1`. |
| `virtualization.partition.type` | `partition-type` | `logical-partition` | `linux`, `zos`, `tpf`, `ssc`, `ims`. In DPM: `type` field. |
| `virtualization.partition.state` | `status` | `logical-partition` / `partition` | Map: `operating` → `running`, `not-activated` → `stopped`, `exceptions` → `degraded`. |

### 2.4 `mainframe.channel` — Channel Path (CHPID)

| OTel Attribute | HMC API Source | Object Class | Notes |
| --- | --- | --- | --- |
| `mainframe.channel.name` *(identity)* | `channel-path-id` | `channel-path` | Two-hex-digit CHPID, e.g. `A0`, `B3`. |
| `mainframe.channel.id` | `channel-path-id` | `channel-path` | Same as identity field. |
| `host.name` | parent CPC `name` | `CPC` | CPC that owns this channel path. |
| `mainframe.channel.type` | `channel-path-type` | `channel-path` | Map: `FC` → `ficon`, `OSD` → `osa`, `ROC` → `roce`, `ZHL` → `zhyperlink`, `CIB` → `hipersockets`. |

### 2.5 `mainframe.adapter` — Physical Hardware Adapter

| OTel Attribute | HMC API Source | Object Class | Notes |
| --- | --- | --- | --- |
| `mainframe.adapter.name` *(identity)* | `name` | `adapter` | Display name in CSS.CHPID format, e.g. `CEX8S-01`. |
| `host.name` | parent CPC `name` | `CPC` | CPC that owns this adapter. |
| `mainframe.adapter.type` | `type` | `adapter` | Map: `crypto` → `crypto`, `roce` → `network`, `osd` → `network`, `ficon` → `storage`, `nvme` → `storage`, `fc` → `storage`. |
| `mainframe.adapter.crypto.type` | `crypto-type` | `adapter` | `cca`, `ep11`, `accelerator`. Only when `adapter.type = crypto`. |

### 2.6 `mainframe.adapter.port` — Physical Adapter Port (DPM)

| OTel Attribute | HMC API Source | Object Class | Notes |
| --- | --- | --- | --- |
| `mainframe.adapter.name` *(identity)* | parent adapter `name` | `adapter` | Adapter name in CSS.CHPID format. |
| `mainframe.adapter.port.id` *(identity)* | `element-uri` | `port` | URI-based port identifier. |
| `host.name` | parent CPC `name` | `CPC` | CPC that owns the adapter. |

### 2.7 `mainframe.partition.nic` — Virtual Partition NIC (DPM)

| OTel Attribute | HMC API Source | Object Class | Notes |
| --- | --- | --- | --- |
| `mainframe.partition.name` *(identity)* | parent partition `name` | `partition` | DPM partition name. |
| `mainframe.partition.nic.name` *(identity)* | `name` | `nic` | NIC display name, e.g. `nic-1`. |
| `host.name` | grandparent CPC `name` | `CPC` | CPC that hosts the partition. |

### 2.8 `virtualization.storage_pool` — DPM Storage Group

| OTel Attribute | HMC API Source | Object Class | Notes |
| --- | --- | --- | --- |
| `virtualization.storage_pool.name` *(identity)* | `name` | `storage-group` | Storage group name, e.g. `SG-PROD-01`. |
| `virtualization.storage_pool.id` | `object-uri` UUID | `storage-group` | HMC object UUID. |
| `virtualization.system.name` | *static* | — | `ibm.prsm`. |

### 2.9 `mainframe.storage.group` — DPM Storage Group (Mainframe Entity)

| OTel Attribute | HMC API Source | Object Class | Notes |
| --- | --- | --- | --- |
| `mainframe.storage.group.name` *(identity)* | `name` | `storage-group` | Storage group name. |
| `mainframe.storage.group.type` | `type` | `storage-group` | `fcp`, `fc`, `nvme`. |
| `host.name` | parent CPC `name` | `CPC` | CPC that owns this storage group. |

---

## 3. HMC API Access Patterns

### 3.1 Metrics Service (push/poll)

The primary source for time-series telemetry is the **HMC Metrics Service**
(SC27-2646 / SC27-2647):

```
POST /api/metrics/context           → create metrics context, returns context URI
GET  /api/metrics/context/{id}      → retrieve current sample (all requested metric groups)
DELETE /api/metrics/context/{id}    → cleanup
```

The `zhmc-prometheus-exporter` uses the Metrics Service internally and exposes Prometheus
metrics that the OTel Collector `prometheusreceiver` scrapes. Contexts must be renewed every
24 hours; the exporter handles lifecycle automatically.

### 3.2 Object Property Polling (REST)

Static configuration attributes (`cpc-resource`, `logical-partition-resource`, etc.) are
polled via standard HMC REST `GET /api/cpcs/{id}` and `GET /api/partitions/{id}`. These are
not part of the push stream. The `zhmc-prometheus-exporter` polls them at a configurable
interval (default: 60 s).

---

## 4. Unit Conversion Reference

All `hmc_source` annotations in the model YAML files document the native HMC unit. The
following conversions are required to produce the OTel-compliant unit declared in each metric:

| HMC Native Unit | OTel UCUM Unit | Conversion Factor | Applies To |
| --- | --- | --- | --- |
| kW (float) | `W` | `× 1000` | `power`, `power-consumption-watts`, `linecord-{n}-power-phase-{A\|B\|C}` |
| BTU/h (integer) | `J/h` | `× 1055.06` | `heat-load`, `heat-load-forced-air`, `heat-load-water` |
| MiB (integer) | `By` | `× 1 048 576` | Memory fields: `installed-memory`, `assigned-memory`, `initial-memory` |
| GiB (integer/float) | `By` | `× 1 073 741 824` | VFM fields, storage volume `size`, storage group `total-capacity` |
| ratio 0.0–1.0 | `1` | None | All `*-utilization` and `*-percentage` fields |
| °C (float) | `Cel` | None | Temperature fields |

### Percentage Normalization

All utilization and percentage fields in the HMC Metrics Service are returned as ratios in
`[0.0, 1.0]` — not as 0–100 percent values. No scaling is required; emit directly as OTel
gauge with unit `"1"`.

Exception: `initial-processing-weight` (partition weight) is an integer in `1–999`. To
produce a normalised ratio: `weight_ratio = initial_processing_weight / 999.0`.

---

## 5. Collector Pipeline

### 5.1 zhmc-prometheus-exporter + prometheusreceiver (recommended)

The `zhmc-prometheus-exporter` (IBM, open source) natively queries the HMC Web Services API
Metrics Service and exposes Prometheus metrics. The OTel Collector `prometheusreceiver` scrapes
these and translates to OTLP.

**Recommended HMC metric groups to enable:**

```yaml
metric_groups:
  - zcpc-environmentals-and-power
  - environmental-power-status
  - cpc-usage-overview
  - zcpc-processor-usage
  - logical-partition-usage    # Classic mode
  - partition-usage            # DPM mode
  - channel-usage
  - crypto-usage
  - adapter-usage
  - flash-memory-usage
  - roce-usage
  - network-physical-adapter-port
  - partition-attached-network-interface
```

**OTel Collector transform processor** (map exporter label names to OTel attribute names):

```yaml
processors:
  transform/hmc_semconv:
    metric_statements:
      - context: datapoint
        statements:
          - set(attributes["mainframe.host.name"],         attributes["cpc_name"])
          - set(attributes["mainframe.channel.id"],        attributes["channel_path_id"])
          - set(attributes["mainframe.adapter.id"],        attributes["adapter_id"])
          - set(attributes["virtualization.partition.id"], attributes["partition_id"])
          - set(attributes["virtualization.system.name"],  "ibm.prsm")

  cumulativetodelta:
    metrics:
      - zhmc_cpc_channel_read_data_rate_mbps
      - zhmc_cpc_channel_write_data_rate_mbps
```

### 5.2 Counter Rollover Handling

HMC network and channel I/O counters are 64-bit unsigned integers that do not roll over
under normal operation. After a CPC IML (reboot) or after resetting a metrics context, all
counters reset to zero. The OTel Collector `cumulativetodeltaprocessor` with
`initial_value: auto` handles this correctly.

---

## 6. Platform-Specific Caveats

| Topic | Detail |
| --- | --- |
| **Classic vs. DPM mode** | Classic mode uses `logical-partition` objects and `logical-partition-usage` metric group. DPM mode uses `partition` objects and `partition-usage`. Detect mode via `CPC.dpm-enabled` property. |
| **PR/SM processor type cardinality** | CPC-level CPU utilization (`cpc-usage-overview`) reports utilization per processor type (CP, IFL, zIIP/IIP, ICF). Discriminate via `mainframe.cpu.type`. Not all types are installed on every CPC. |
| **Virtual Flash Memory / SCM** | `storage-vfm-total` is `0` on CPCs without Storage Class Memory configured. Filter zero values to avoid emitting meaningless metric points. |
| **HMC API version gate** | `network-physical-adapter-port` and `partition-attached-network-interface` metric groups require HMC API version ≥ 2.14. Check `GET /api` for `api-version`. |
| **Metrics context lifecycle** | A metrics context (`POST /api/metrics/context`) must be renewed every 24 hours. The `zhmc-prometheus-exporter` manages lifecycle automatically. Custom collectors must handle context expiry (HTTP 404 on the context URI). |
| **Humidity unit** | `humidity-percentage` returns a value in `[0.0, 1.0]` (already a ratio), not in the 0–100 range its name implies. The OTel metric `mainframe.host.humidity` has unit `1`; emit directly without scaling. |

---

## 7. Relationship to Generated Registry Documentation

The signal-level details (instrument type, unit, stability, entity association, attribute
list) are authoritative in the generated registry pages under `docs/registry/mainframe/` and
`docs/registry/virtualization/`. Each metric and attribute defined in `model/mainframe/`
carries an `annotations.hmc_source` block that records the exact HMC object class, metric
group, field name, operating mode, and minimum HMC version required.

When the upstream Weaver template package adds support for rendering custom annotation blocks,
those `hmc_source` annotations will be surfaced directly in the generated metric pages. Until
then, the full cross-reference is maintained in
[hmc-api-signal-mapping.md](hmc-api-signal-mapping.md).
