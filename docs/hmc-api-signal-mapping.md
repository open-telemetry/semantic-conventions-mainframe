<!---
This file is hand-authored. Do NOT regenerate or overwrite with Weaver.
Its tables are derived from the `annotations.hmc_source` blocks in the model and
must be kept in step with them by hand. When the upstream Weaver template package
can render custom annotation blocks, these tables should be generated and this
file reduced to narrative.

Scope: ONLY signals that have an IBM Z HMC Web Services API source appear here.
The model under model/ intentionally contains further definitions — cross-platform
virtualization metrics and upstream refinements for other hypervisors — that have
no HMC source and are out of scope for this document.

See docs/hmc-api-background.md for architecture, entity construction, and
collector pipeline details.
--->

# IBM Z HMC Web Services API — OTel Signal Mapping

This document maps OpenTelemetry signals defined in this repository to the IBM Z
Hardware Management Console (HMC) Web Services API metric-group field or managed
object property that is their source.

**Primary reference:** *IBM Z and LinuxONE Hardware Management Console Web Services
API*, SC27-2646-01, version 2.17.0. Field names, units and table numbers are taken
from Chapter 9, "Metric groups" (Tables 72–84) and from the managed object
descriptions.

**Secondary reference:** the [zhmc-prometheus-exporter](https://github.com/zhmcclient/zhmc-prometheus-exporter)
project, whose `metrics.yaml` defines synthetic resource groups (`cpc-resource`,
`logical-partition-resource`, `partition-resource`, `storagegroup-resource`) built
from managed object properties. Several object property names in Part 2 were
confirmed against it. Note that those synthetic group names are **not** HMC API
metric groups and are not used as source identifiers here.

## Scope

- **In scope:** every definition in `model/` carrying an `annotations.hmc_source`
  block — 145 source entries, including 8 upstream metric refinements.
- **Out of scope:** definitions with no HMC source. The model deliberately covers
  more ground than the HMC API — cross-platform `virtualization.*` metrics, and
  upstream refinements (`container.*`, `hw.*`) that apply to hypervisors other
  than PR/SM. Their absence here is not a gap.
- **Authority:** `annotations.hmc_source` in the model is the machine-readable
  source of truth. If this document and the model disagree, the model wins.

## Columns

- **OTel Signal** — metric name, attribute key, or the upstream metric a local
  refinement extends (marked *refinement*)
- **Shape** — instrument and UCUM unit; refinements inherit both from upstream
- **Target Entity** — the OTel entity the signal is associated with
- **HMC Field / Property** — field within the metric group, or property of the object
- **Mode** — `classic`, `dpm`, or `all`
- **Transformation** — conversion applied between the HMC value and the OTel value

A ⚠ marks a field name not located verbatim in SC27-2646-01.

---

## Part 1 — Metric groups

One section per metric group declared in SC27-2646-01. All 13 of the 13 declared
groups are used by this repository.

### `channel-usage` — Channels (Table 72)

| OTel Signal | Shape | Target Entity | HMC Field | Mode | Transformation |
| --- | --- | --- | --- | --- | --- |
| `mainframe.channel.mode` | attribute | *(attribute)* | `shared-channel` | classic | None |
| `mainframe.channel.owning.partition` | attribute | *(attribute)* | `logical-partition-name` | classic | None |
| `mainframe.channel.utilization` | gauge / `1` | `mainframe.channel` | `channel-usage` | classic | `value / 100` (% → 1) |


### `cpc-usage-overview` — CPC overview (Table 73)

| OTel Signal | Shape | Target Entity | HMC Field | Mode | Transformation |
| --- | --- | --- | --- | --- | --- |
| `mainframe.host.channel.utilization` | gauge / `1` | `virtualization.platform` | `channel-usage` | classic | `value / 100` (% → 1) |
| `mainframe.host.cpu.utilization` | gauge / `1` | `virtualization.platform` | `cp-all-processor-usage` | classic | `value / 100` (% → 1) |
| `mainframe.host.cpu.utilization` | gauge / `1` | `virtualization.platform` | `cp-dedicated-processor-usage` | classic | `value / 100` (% → 1) |
| `mainframe.host.cpu.utilization` | gauge / `1` | `virtualization.platform` | `cp-shared-processor-usage` | classic | `value / 100` (% → 1) |
| `mainframe.host.cpu.utilization` | gauge / `1` | `virtualization.platform` | `icf-all-processor-usage` | classic | `value / 100` (% → 1) |
| `mainframe.host.cpu.utilization` | gauge / `1` | `virtualization.platform` | `icf-dedicated-processor-usage` | classic | `value / 100` (% → 1) |
| `mainframe.host.cpu.utilization` | gauge / `1` | `virtualization.platform` | `icf-shared-processor-usage` | classic | `value / 100` (% → 1) |
| `mainframe.host.cpu.utilization` | gauge / `1` | `virtualization.platform` | `ifl-all-processor-usage` | classic | `value / 100` (% → 1) |
| `mainframe.host.cpu.utilization` | gauge / `1` | `virtualization.platform` | `ifl-dedicated-processor-usage` | classic | `value / 100` (% → 1) |
| `mainframe.host.cpu.utilization` | gauge / `1` | `virtualization.platform` | `ifl-shared-processor-usage` | classic | `value / 100` (% → 1) |
| `mainframe.host.cpu.utilization` | gauge / `1` | `virtualization.platform` | `iip-all-processor-usage` | classic | `value / 100` (% → 1) |
| `mainframe.host.cpu.utilization` | gauge / `1` | `virtualization.platform` | `iip-dedicated-processor-usage` | classic | `value / 100` (% → 1) |
| `mainframe.host.cpu.utilization` | gauge / `1` | `virtualization.platform` | `iip-shared-processor-usage` | classic | `value / 100` (% → 1) |


### `dpm-system-usage-overview` — DPM system overview (Table 74)

| OTel Signal | Shape | Target Entity | HMC Field | Mode | Transformation |
| --- | --- | --- | --- | --- | --- |
| `mainframe.host.adapter.utilization` | gauge / `1` | `virtualization.platform` | `accelerator-usage` | dpm | `value / 100` (% → 1) |
| `mainframe.host.adapter.utilization` | gauge / `1` | `virtualization.platform` | `crypto-usage` | dpm | `value / 100` (% → 1) |
| `mainframe.host.adapter.utilization` | gauge / `1` | `virtualization.platform` | `network-usage` | dpm | `value / 100` (% → 1) |
| `mainframe.host.adapter.utilization` | gauge / `1` | `virtualization.platform` | `storage-usage` | dpm | `value / 100` (% → 1) |


### `logical-partition-usage` — Logical partitions (Table 75)

| OTel Signal | Shape | Target Entity | HMC Field | Mode | Transformation |
| --- | --- | --- | --- | --- | --- |
| `mainframe.partition.cpu.utilization` | gauge / `1` | `virtualization.partition` | `cp-processor-usage` | classic | `value / 100` (% → 1) |
| `mainframe.partition.cpu.utilization` | gauge / `1` | `virtualization.partition` | `icf-processor-usage` | classic | `value / 100` (% → 1) |
| `mainframe.partition.cpu.utilization` | gauge / `1` | `virtualization.partition` | `ifl-processor-usage` | classic | `value / 100` (% → 1) |
| `mainframe.partition.cpu.utilization` | gauge / `1` | `virtualization.partition` | `iip-processor-usage` | classic | `value / 100` (% → 1) |
| `mainframe.partition.power.usage` | gauge / `W` | `virtualization.partition` | `power-consumption` | classic | None |


### `partition-usage` — Partitions, DPM (Table 76)

| OTel Signal | Shape | Target Entity | HMC Field | Mode | Transformation |
| --- | --- | --- | --- | --- | --- |
| `mainframe.partition.adapter.utilization` | gauge / `1` | `virtualization.partition` | `accelerator-usage` | dpm | `value / 100` (% → 1) |
| `mainframe.partition.adapter.utilization` | gauge / `1` | `virtualization.partition` | `crypto-usage` | dpm | `value / 100` (% → 1) |
| `mainframe.partition.adapter.utilization` | gauge / `1` | `virtualization.partition` | `network-usage` | dpm | `value / 100` (% → 1) |
| `mainframe.partition.adapter.utilization` | gauge / `1` | `virtualization.partition` | `storage-usage` | dpm | `value / 100` (% → 1) |
| `mainframe.partition.cpu.utilization` | gauge / `1` | `virtualization.partition` | `processor-usage` | dpm | `value / 100` (% → 1) |


### `zcpc-environmentals-and-power` — zCPC environmentals and power (Table 77)

| OTel Signal | Shape | Target Entity | HMC Field | Mode | Transformation |
| --- | --- | --- | --- | --- | --- |
| `mainframe.host.dewpoint` | gauge / `Cel` | `virtualization.platform` | `dew-point` | all | None |
| `mainframe.host.heatload` | gauge / `J/h` | `virtualization.platform` | `heat-load` | all | `value * 1055.06` (BTU/h → J/h) |
| `mainframe.host.heatload` | gauge / `J/h` | `virtualization.platform` | `heat-load-forced-air` | all | `value * 1055.06` (BTU/h → J/h) |
| `mainframe.host.heatload` | gauge / `J/h` | `virtualization.platform` | `heat-load-water` | all | `value * 1055.06` (BTU/h → J/h) |
| `mainframe.host.humidity` | gauge / `1` | `virtualization.platform` | `humidity` | all | `value / 100` (% → 1) |
| `mainframe.host.power.usage` | gauge / `W` | `virtualization.platform` | `power` | all | None |
| `mainframe.host.power.usage` | gauge / `W` | `virtualization.platform` | `total-infrastructure-power-consumption` | all | None |
| `mainframe.host.power.usage` | gauge / `W` | `virtualization.platform` | `total-partition-power-consumption` | all | None |
| `mainframe.host.power.usage` | gauge / `W` | `virtualization.platform` | `total-unassigned-power-consumption` | all | None |


### `environmental-power-status` — Power status (Table 78)

| OTel Signal | Shape | Target Entity | HMC Field | Mode | Transformation |
| --- | --- | --- | --- | --- | --- |
| `mainframe.host.power.cord` | attribute | *(attribute)* | `linecord-{one\|two\|three\|four\|five\|six\|seven\|eight}-power-phase-{A\|B\|C}` | all | None |
| `mainframe.host.power.cord.usage` | gauge / `W` | `virtualization.platform` | `linecord-{one\|two\|three\|four\|five\|six\|seven\|eight}-power-phase-{A\|B\|C}` | all | None |
| `mainframe.host.power.phase` | attribute | *(attribute)* | `linecord-{one\|two\|three\|four\|five\|six\|seven\|eight}-power-phase-{A\|B\|C}` | all | None |


### `zcpc-processor-usage` — zCPC processors (Table 79)

| OTel Signal | Shape | Target Entity | HMC Field | Mode | Transformation |
| --- | --- | --- | --- | --- | --- |
| `mainframe.cpu.smt_mode.utilization` | gauge / `1` | `mainframe.cpu` | `smt-usage` | all | `value / 100` (% → 1) |
| `mainframe.cpu.thread0.utilization` | gauge / `1` | `mainframe.cpu` | `thread-0-usage` | all | `value / 100` (% → 1) |
| `mainframe.cpu.thread1.utilization` | gauge / `1` | `mainframe.cpu` | `thread-1-usage` | all | `value / 100` (% → 1) |
| `mainframe.cpu.utilization` | gauge / `1` | `mainframe.cpu` | `processor-usage` | all | `value / 100` (% → 1) |


### `crypto-usage` — Cryptos (Table 80)

| OTel Signal | Shape | Target Entity | HMC Field | Mode | Transformation |
| --- | --- | --- | --- | --- | --- |
| `mainframe.adapter.utilization` | gauge / `1` | `mainframe.adapter` | `adapter-usage` | classic | `value / 100` (% → 1) |


### `adapter-usage` — Adapters, DPM (Table 81)

| OTel Signal | Shape | Target Entity | HMC Field | Mode | Transformation |
| --- | --- | --- | --- | --- | --- |
| `mainframe.adapter.utilization` | gauge / `1` | `mainframe.adapter` | `adapter-usage` | dpm | `value / 100` (% → 1) |


### `flash-memory-usage` — Flash memory adapters (Table 82)

| OTel Signal | Shape | Target Entity | HMC Field | Mode | Transformation |
| --- | --- | --- | --- | --- | --- |
| `mainframe.adapter.utilization` | gauge / `1` | `mainframe.adapter` | `adapter-usage` | classic | `value / 100` (% → 1) |


### `network-physical-adapter-port` — Network adapter port (Table 83)

| OTel Signal | Shape | Target Entity | HMC Field | Mode | Transformation |
| --- | --- | --- | --- | --- | --- |
| `mainframe.adapter.port.id` | attribute | *(attribute)* | `network-port-id` | dpm | None |
| `system.network.errors`<br/>*(refinement)* | *inherited* | `mainframe.adapter.port` | `packets-received-discarded` | dpm | None |
| `system.network.errors`<br/>*(refinement)* | *inherited* | `mainframe.adapter.port` | `packets-sent-discarded` | dpm | None |
| `system.network.io`<br/>*(refinement)* | *inherited* | `mainframe.adapter.port` | `bytes-received` | dpm | None |
| `system.network.io`<br/>*(refinement)* | *inherited* | `mainframe.adapter.port` | `bytes-sent` | dpm | None |
| `system.network.packet.count`<br/>*(refinement)* | *inherited* | `mainframe.adapter.port` | `packets-received` | dpm | None |
| `system.network.packet.count`<br/>*(refinement)* | *inherited* | `mainframe.adapter.port` | `packets-sent` | dpm | None |
| `system.network.packet.dropped`<br/>*(refinement)* | *inherited* | `mainframe.adapter.port` | `packets-received-dropped` | dpm | None |
| `system.network.packet.dropped`<br/>*(refinement)* | *inherited* | `mainframe.adapter.port` | `packets-sent-dropped` | dpm | None |


### `partition-attached-network-interface` — Network interface (Table 84)

| OTel Signal | Shape | Target Entity | HMC Field | Mode | Transformation |
| --- | --- | --- | --- | --- | --- |
| `mainframe.partition.nic.name` | attribute | *(attribute)* | `nic-id` | dpm | None |
| `system.network.errors`<br/>*(refinement)* | *inherited* | `mainframe.partition.nic` | `packets-received-discarded` | dpm | None |
| `system.network.errors`<br/>*(refinement)* | *inherited* | `mainframe.partition.nic` | `packets-sent-discarded` | dpm | None |
| `system.network.io`<br/>*(refinement)* | *inherited* | `mainframe.partition.nic` | `bytes-received` | dpm | None |
| `system.network.io`<br/>*(refinement)* | *inherited* | `mainframe.partition.nic` | `bytes-sent` | dpm | None |
| `system.network.packet.count`<br/>*(refinement)* | *inherited* | `mainframe.partition.nic` | `packets-received` | dpm | None |
| `system.network.packet.count`<br/>*(refinement)* | *inherited* | `mainframe.partition.nic` | `packets-sent` | dpm | None |
| `system.network.packet.dropped`<br/>*(refinement)* | *inherited* | `mainframe.partition.nic` | `packets-received-dropped` | dpm | None |
| `system.network.packet.dropped`<br/>*(refinement)* | *inherited* | `mainframe.partition.nic` | `packets-sent-dropped` | dpm | None |

---

## Part 2 — Managed object properties

Signals sourced from a managed object property rather than a metric group. Object
class names follow the spelling used in SC27-2646-01.

### `adapter` — Adapter

| OTel Signal | Shape | Target Entity | HMC Property | Mode | Transformation |
| --- | --- | --- | --- | --- | --- |
| `mainframe.adapter.name` | attribute | *(attribute)* | `adapter-id` | all | None |
| `mainframe.adapter.owning.partition` | attribute | *(attribute)* | `partitions-assigned-to-adapter` | dpm | None |
| `mainframe.adapter.physical_channel.status.code` | gauge / `1` | `mainframe.adapter` | `physical-channel-status` | dpm | None |
| `mainframe.adapter.status` | attribute | *(attribute)* | `status` | dpm | None |
| `mainframe.adapter.status.code` | gauge / `1` | `mainframe.adapter` | `status` | dpm | None |
| `mainframe.adapter.type` | attribute | *(attribute)* | `type` | all | None |
| `mainframe.channel.type` | attribute | *(attribute)* | `type` | all | None |


### `channel-path` — Channel path

| OTel Signal | Shape | Target Entity | HMC Property | Mode | Transformation |
| --- | --- | --- | --- | --- | --- |
| `mainframe.channel.id` | attribute | *(attribute)* | `channel-path-id` | all | None |
| `mainframe.channel.name` | attribute | *(attribute)* | `channel-path-id` | all | None |


### `cpc` — CPC

| OTel Signal | Shape | Target Entity | HMC Property | Mode | Transformation |
| --- | --- | --- | --- | --- | --- |
| `mainframe.host.cpu.active.count` | updowncounter / `{cpu}` | `virtualization.platform` | `processor-count-general-purpose` | all | None |
| `mainframe.host.cpu.active.count` | updowncounter / `{cpu}` | `virtualization.platform` | `processor-count-icf` | all | None |
| `mainframe.host.cpu.active.count` | updowncounter / `{cpu}` | `virtualization.platform` | `processor-count-ifl` | all | None |
| `mainframe.host.cpu.active.count` | updowncounter / `{cpu}` | `virtualization.platform` | `processor-count-iip` | all | None |
| `mainframe.host.cpu.active.count` | updowncounter / `{cpu}` | `virtualization.platform` | `processor-count-service-assist` | all | None |
| `mainframe.host.cpu.defective.count` | updowncounter / `{cpu}` | `virtualization.platform` | `processor-count-defective` | all | None |
| `mainframe.host.cpu.ifp.count` | updowncounter / `{cpu}` | `virtualization.platform` | `processor-count-cbp` | all | None |
| `mainframe.host.cpu.sap.count` | updowncounter / `{cpu}` | `virtualization.platform` | `processor-count-service-assist` | all | None |
| `mainframe.host.cpu.spare.count` | updowncounter / `{cpu}` | `virtualization.platform` | `processor-count-spare` | all | None |
| `mainframe.host.heatload.type` | attribute | *(attribute)* | `heat-load` | all | None |
| `mainframe.host.machine_model` | attribute | *(attribute)* | `machine-model` | all | None |
| `mainframe.host.machine_type` | attribute | *(attribute)* | `machine-type` | all | None |
| `mainframe.host.memory.size` | gauge / `MiBy` | `virtualization.platform` | `storage-customer` | all | None |
| `mainframe.host.memory.size` | gauge / `MiBy` | `virtualization.platform` | `storage-customer-available` | all | None |
| `mainframe.host.memory.size` | gauge / `MiBy` | `virtualization.platform` | `storage-customer-central` | all | None |
| `mainframe.host.memory.size` | gauge / `MiBy` | `virtualization.platform` | `storage-customer-expanded` | all | None |
| `mainframe.host.memory.size` | gauge / `MiBy` | `virtualization.platform` | `storage-hardware-system-area` | all | None |
| `mainframe.host.memory.size` | gauge / `MiBy` | `virtualization.platform` | `storage-total-installed` | all | None |
| `mainframe.host.memory.vfm.increment.size` | gauge / `GiBy` | `virtualization.platform` | `storage-vfm-increment-size` | all | None |
| `mainframe.host.memory.vfm.size` | gauge / `GiBy` | `virtualization.platform` | `storage-vfm-total` | all | None |
| `mainframe.host.power.usage.type` | attribute | *(attribute)* | `power` | all | None |
| `mainframe.host.serial_number` | attribute | *(attribute)* | `serial-number` | all | None |
| `mainframe.host.status.unacceptable` | gauge / `1` | `virtualization.platform` | `has-unacceptable-status` | all | None |
| `mainframe.memory.type` | attribute | *(attribute)* | `storage-total-installed` | all | None |
| `virtualization.platform.memory.total` | gauge / `MiBy` | `virtualization.platform` | `storage-total-installed` | all | None |
| `virtualization.platform.memory.used` | gauge / `MiBy` | `virtualization.platform` | `storage-customer-central` | all | None |
| `virtualization.platform.memory.used` | gauge / `MiBy` | `virtualization.platform` | `storage-customer-expanded` | all | None |


### `logical-partition` — Logical partition

| OTel Signal | Shape | Target Entity | HMC Property | Mode | Transformation |
| --- | --- | --- | --- | --- | --- |
| `mainframe.partition.capacity.defined` | gauge / `{MSU}/h` | `virtualization.partition` | `defined-capacity` | classic | None |
| `mainframe.partition.cpu.capped.count` | updowncounter / `{cpu}` | `virtualization.partition` | `absolute-general-purpose-capping` | classic | None |
| `mainframe.partition.cpu.capped.count` | updowncounter / `{cpu}` | `virtualization.partition` | `absolute-icf-capping` | classic | None |
| `mainframe.partition.cpu.capped.count` | updowncounter / `{cpu}` | `virtualization.partition` | `absolute-ifl-capping` | classic | None |
| `mainframe.partition.cpu.capped.count` | updowncounter / `{cpu}` | `virtualization.partition` | `absolute-ziip-capping` | classic | None |
| `mainframe.partition.cpu.reserved.count` | updowncounter / `{cpu}` | `virtualization.partition` | `number-reserved-general-purpose-processors` | classic | None |
| `mainframe.partition.cpu.reserved.count` | updowncounter / `{cpu}` | `virtualization.partition` | `number-reserved-icf-processors` | classic | None |
| `mainframe.partition.cpu.reserved.count` | updowncounter / `{cpu}` | `virtualization.partition` | `number-reserved-ifl-processors` | classic | None |
| `mainframe.partition.cpu.reserved.count` | updowncounter / `{cpu}` | `virtualization.partition` | `number-reserved-ziip-processors` | classic | None |
| `mainframe.partition.cpu.virtual.count` | updowncounter / `{cpu}` | `virtualization.partition` | `number-general-purpose-processors` | classic | None |
| `mainframe.partition.cpu.virtual.count` | updowncounter / `{cpu}` | `virtualization.partition` | `number-icf-processors` | classic | None |
| `mainframe.partition.cpu.virtual.count` | updowncounter / `{cpu}` | `virtualization.partition` | `number-ifl-processors` | classic | None |
| `mainframe.partition.cpu.virtual.count` | updowncounter / `{cpu}` | `virtualization.partition` | `number-ziip-processors` | classic | None |
| `mainframe.partition.memory.size` | gauge / `MiBy` | `virtualization.partition` | `storage-central-allocation` | classic | None |
| `mainframe.partition.memory.size` | gauge / `MiBy` | `virtualization.partition` | `storage-expanded-allocation` | classic | None |
| `mainframe.partition.number` | attribute | *(attribute)* | `partition-number` | classic | None |
| `mainframe.partition.type` | attribute | *(attribute)* | `activation-mode` | classic | None |
| `mainframe.partition.wlm.enabled` | gauge / `1` | `virtualization.partition` | `workload-manager-enabled` | classic | None |
| `mainframe.zvm.hypervisor.name` | attribute | *(attribute)* | `name` | classic | None |


### `partition` — Partition (DPM)

| OTel Signal | Shape | Target Entity | HMC Property | Mode | Transformation |
| --- | --- | --- | --- | --- | --- |
| `mainframe.partition.cpu.capped.count` | updowncounter / `{cpu}` | `virtualization.partition` | `absolute-processing-capping` | dpm | None |
| `mainframe.partition.cpu.mode` | gauge / `1` | `virtualization.partition` | `processor-mode` | dpm | None |
| `mainframe.partition.cpu.threads_per_processor` | gauge / `{thread}` | `virtualization.partition` | `threads-per-processor` | dpm | None |
| `mainframe.partition.cpu.virtual.count` | updowncounter / `{cpu}` | `virtualization.partition` | `cp-processors` | dpm | None |
| `mainframe.partition.cpu.virtual.count` | updowncounter / `{cpu}` | `virtualization.partition` | `ifl-processors` | dpm | None |
| `mainframe.partition.memory.size` | gauge / `MiBy` | `virtualization.partition` | `initial-memory` | dpm | None |
| `mainframe.partition.memory.size` | gauge / `MiBy` | `virtualization.partition` | `maximum-memory` | dpm | None |
| `mainframe.partition.memory.size` | gauge / `MiBy` | `virtualization.partition` | `reserved-memory` | dpm | None |
| `mainframe.partition.memory.type` | attribute | *(attribute)* | `storage-central-allocation` | all | None |
| `mainframe.partition.name` | attribute | *(attribute)* | `name` | all | None |
| `mainframe.partition.status` | attribute | *(attribute)* | `status` | all | None |
| `mainframe.partition.status.code` | gauge / `1` | `virtualization.partition` | `status` | all | None |
| `mainframe.partition.status.unacceptable` | gauge / `1` | `virtualization.partition` | `has-unacceptable-status` | all | None |
| `mainframe.partition.weight.type` | attribute | *(attribute)* | `initial-processing-weight` | all | None |


### `processor` — Processor

| OTel Signal | Shape | Target Entity | HMC Property | Mode | Transformation |
| --- | --- | --- | --- | --- | --- |
| `mainframe.cpu.name` | attribute | *(attribute)* | `name` | all | None |
| `mainframe.cpu.sharing.mode` | attribute | *(attribute)* | `allocation-type` | all | None |
| `mainframe.cpu.type` | attribute | *(attribute)* | `type` | all | None |


### `storage-group` — Storage group

| OTel Signal | Shape | Target Entity | HMC Property | Mode | Transformation |
| --- | --- | --- | --- | --- | --- |
| `mainframe.storage.fulfillment.state` | attribute | *(attribute)* | `fulfillment-state` | dpm | None |
| `mainframe.storage.group.name` | attribute | *(attribute)* | `name` | dpm | None |
| `mainframe.storage.group.type` | attribute | *(attribute)* | `type` | dpm | None |


### `storage-volume` — Storage volume

| OTel Signal | Shape | Target Entity | HMC Property | Mode | Transformation |
| --- | --- | --- | --- | --- | --- |
| `mainframe.storage.group.volume.capacity` | updowncounter / `By` | `mainframe.storage.group.volume` | `size` | dpm | None |
| `mainframe.storage.group.volume.name` | attribute | *(attribute)* | `name` | dpm | None |


### `virtual-switch` — Virtual switch

| OTel Signal | Shape | Target Entity | HMC Property | Mode | Transformation |
| --- | --- | --- | --- | --- | --- |
| `mainframe.vswitch.name` | attribute | *(attribute)* | `name` | all | None |

---

## Summary

| Category | Count |
| --- | --- |
| Source entries mapped to a metric group (Part 1) | 67 |
| Source entries mapped to an object property (Part 2) | 78 |
| **Total `annotations.hmc_source` entries in the model** | **145** |

Counts are derived from the model, not maintained by hand. Regenerate them
whenever `annotations.hmc_source` blocks are added or removed.

## Known gaps

The following definitions have **no** known HMC API source and therefore do not
appear above. They are listed so the gap stays visible rather than being mistaken
for an omission:

| Definition | Why |
| --- | --- |
| `mainframe.storage.group.capacity` | SC27-2646-01 defines no storage-group capacity property; the exporter's `storagegroup-resource` exposes only `type`, `fulfillment-state`, `shared` and `max-partitions`. Derive by summing the group's volume `size` values. |
| `mainframe.storage.group.usage` | As above — no allocation property is exposed. |
| `mainframe.smc.type` | No SMC telemetry metric group is declared in SC27-2646-01. |
| `mainframe.crypto.function` *(removed)* | The algorithm family is not exposed; `crypto-type` on the adapter object is the operating mode, not the algorithm. |
| `mainframe.zvm.guest.userid` | No z/VM guest name property is exposed by the HMC API. |
| Four `virtualization.*` metrics | Accepted as unsourced in commit 43f1d02. |
