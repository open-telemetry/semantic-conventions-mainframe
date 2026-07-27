
# Metrics: `mainframe`

This document describes the `mainframe` metrics.


## `mainframe.adapter.utilization` ![Development](https://img.shields.io/badge/-development-blue)

The percentage of time the adapter was processing I/O.


**Instrument**: `gauge`

**Unit**: `1`


### Attributes

| Attribute | Type | Requirement Level | Description |
|-----------|------|-------------------|-------------|
| `mainframe.adapter.type` | Enum | Required | Type of the adapter. |



## `mainframe.channel.utilization` ![Development](https://img.shields.io/badge/-development-blue)

The percentage of time the channel was processing I/O.


**Instrument**: `gauge`

**Unit**: `1`


### Attributes

| Attribute | Type | Requirement Level | Description |
|-----------|------|-------------------|-------------|
| `mainframe.channel.mode` | Enum | Required | Mode the I/O channel is operating in. The mode can be either 'dedicated' or 'shared'. |



## `mainframe.cpu.smt_mode.utilization` ![Development](https://img.shields.io/badge/-development-blue)

The percentage of time the processor is running in simultaneous multithreading (SMT) mode. Set to -1 when SMT mode is not supported by the mainframe.


**Instrument**: `gauge`

**Unit**: `1`



## `mainframe.cpu.thread-0.utilization` ![Development](https://img.shields.io/badge/-development-blue)

The percent usage of thread 0 when the processor is running in simultaneous multithreading (SMT) mode. Set to -1 when SMT mode is not supported by the mainframe.


**Instrument**: `gauge`

**Unit**: `{cpu}`



## `mainframe.cpu.thread-1.utilization` ![Development](https://img.shields.io/badge/-development-blue)

The percent usage of thread 1 when the processor is running in simultaneous multithreading (SMT) mode. Set to -1 when SMT mode is not supported by the mainframe.


**Instrument**: `gauge`

**Unit**: `{cpu}`



## `mainframe.cpu.utilization` ![Development](https://img.shields.io/badge/-development-blue)

The percentage of time the CPU was processing I/O.


**Instrument**: `gauge`

**Unit**: `1`



## `mainframe.host.channel.utilization` ![Development](https://img.shields.io/badge/-development-blue)

The average percentage of time the channels of the mainframe system were processing I/O.


**Instrument**: `gauge`

**Unit**: `{cpu}`



## `mainframe.host.cpu.active.count` ![Development](https://img.shields.io/badge/-development-blue)

The number of active processors in the mainframe system of a specific type.


**Instrument**: `updowncounter`

**Unit**: `{cpu}`


### Attributes

| Attribute | Type | Requirement Level | Description |
|-----------|------|-------------------|-------------|
| `mainframe.cpu.type` | Enum | Required | Type of mainframe processor. |



## `mainframe.host.cpu.defective.count` ![Development](https://img.shields.io/badge/-development-blue)

The number of defective processors in the mainframe system.


**Instrument**: `updowncounter`

**Unit**: `{cpu}`



## `mainframe.host.cpu.spare.count` ![Development](https://img.shields.io/badge/-development-blue)

The number of spare processors in the mainframe system.


**Instrument**: `updowncounter`

**Unit**: `{cpu}`



## `mainframe.host.cpu.utilization` ![Development](https://img.shields.io/badge/-development-blue)

The utilization percentage for processors of the specified type. Set to -1 when no processors of this type are present.


**Instrument**: `gauge`

**Unit**: `{cpu}`


### Attributes

| Attribute | Type | Requirement Level | Description |
|-----------|------|-------------------|-------------|
| `mainframe.cpu.sharing.mode` | Enum | Required | Mode the processor is operating in. The mode can be either 'dedicated' or 'shared'. |
| `mainframe.cpu.type` | Enum | Required | Type of mainframe processor. |
| `cpu.mode` | Enum | Recommended | The mode of the CPU |
| `cpu.logical_number` | `int` | Opt-In | The logical CPU number [0..n-1] |



## `mainframe.host.dewpoint` ![Development](https://img.shields.io/badge/-development-blue)

Dew point temperature of the environment surrounding the mainframe system.


**Instrument**: `gauge`

**Unit**: `Cel`



## `mainframe.host.heatload` ![Development](https://img.shields.io/badge/-development-blue)

Heat load of the mainframe system in BTU/h.


**Instrument**: `gauge`

**Unit**: `BTU/h`


### Attributes

| Attribute | Type | Requirement Level | Description |
|-----------|------|-------------------|-------------|
| `mainframe.host.heatload.type` | Enum | Required | Type of heat load measurement for the Central Processor Complex (CPC). |



## `mainframe.host.humidity` ![Development](https://img.shields.io/badge/-development-blue)

Relative humidity of the environment surrounding the mainframe system.


**Instrument**: `gauge`

**Unit**: `1`



## `mainframe.host.memory.size` ![Development](https://img.shields.io/badge/-development-blue)

Size of memory in the mainframe system of a specific type.


**Instrument**: `gauge`

**Unit**: `MiBy`


### Attributes

| Attribute | Type | Requirement Level | Description |
|-----------|------|-------------------|-------------|
| `mainframe.memory.type` | Enum | Required | Type of mainframe memory. |



## `mainframe.host.memory.vfm.increment.size` ![Development](https://img.shields.io/badge/-development-blue)

Size of the IBM Virtual Flash Memory (VFM) memory increments of the mainframe system.


**Instrument**: `gauge`

**Unit**: `GiBy`



## `mainframe.host.memory.vfm.size` ![Development](https://img.shields.io/badge/-development-blue)

Total size of the installed IBM Virtual Flash Memory (VFM) memory in the mainframe system.


**Instrument**: `gauge`

**Unit**: `GiBy`



## `mainframe.host.power.cord.usage` ![Development](https://img.shields.io/badge/-development-blue)

Power cord usage of the mainframe system in Watts.


**Instrument**: `gauge`

**Unit**: `W`


### Attributes

| Attribute | Type | Requirement Level | Description |
|-----------|------|-------------------|-------------|
| `mainframe.host.power.cord` | Enum | Required | Identfies the power cord of the Central Processor Complex (CPC). |
| `mainframe.host.power.phase` | Enum | Required | Identifies the power phase of the Central Processor Complex (CPC). |



## `mainframe.host.power.usage` ![Development](https://img.shields.io/badge/-development-blue)

Power usage of the mainframe system in Watts.


**Instrument**: `gauge`

**Unit**: `W`


### Attributes

| Attribute | Type | Requirement Level | Description |
|-----------|------|-------------------|-------------|
| `mainframe.host.power.usage.type` | Enum | Required | Type of power usage measurement for the Central Processor Complex (CPC). |



## `mainframe.host.status` ![Development](https://img.shields.io/badge/-development-blue)

The status of the mainframe system.


**Instrument**: `gauge`

**Unit**: `1`



## `mainframe.host.status.unacceptable` ![Development](https://img.shields.io/badge/-development-blue)

Indicating whether the CPC has an unacceptable status.


**Instrument**: `updowncounter`

**Unit**: `1`



## `mainframe.host.temperature` ![Development](https://img.shields.io/badge/-development-blue)

The temperature of the mainframe system in degrees Celsius.


**Instrument**: `gauge`

**Unit**: `Cel`


### Attributes

| Attribute | Type | Requirement Level | Description |
|-----------|------|-------------------|-------------|
| `mainframe.host.temperature.type` | Enum | Required | Location of the Central Processor Complex (CPC). |



## `mainframe.partition.cpu.capped.count` ![Development](https://img.shields.io/badge/-development-blue)

Maximum number of processors of the specified typethat can be used if absolute capping is enabled, otherwise 0


**Instrument**: `updowncounter`

**Unit**: `{cpu}`


### Attributes

| Attribute | Type | Requirement Level | Description |
|-----------|------|-------------------|-------------|
| `mainframe.cpu.type` | Enum | Required | Type of mainframe processor. |



## `mainframe.partition.cpu.is_capped` ![Development](https://img.shields.io/badge/-development-blue)

Indicates whether absolute capping is enabled the processors of the specified type allocated to a partition (0=false, 1=true).


**Instrument**: `updowncounter`

**Unit**: `{cpu}`


### Attributes

| Attribute | Type | Requirement Level | Description |
|-----------|------|-------------------|-------------|
| `mainframe.cpu.type` | Enum | Required | Type of mainframe processor. |



## `mainframe.partition.cpu.reserved.count` ![Development](https://img.shields.io/badge/-development-blue)

The number of processors of the specified type reserved for the active partition.


**Instrument**: `updowncounter`

**Unit**: `{cpu}`


### Attributes

| Attribute | Type | Requirement Level | Description |
|-----------|------|-------------------|-------------|
| `mainframe.cpu.type` | Enum | Required | Type of mainframe processor. |



## `mainframe.partition.cpu.virtual.count` ![Development](https://img.shields.io/badge/-development-blue)

The number of virtual processors allocated to an active partition.


**Instrument**: `updowncounter`

**Unit**: `{cpu}`


### Attributes

| Attribute | Type | Requirement Level | Description |
|-----------|------|-------------------|-------------|
| `mainframe.cpu.type` | Enum | Required | Type of mainframe processor. |



## `mainframe.partition.cpu.weight` ![Development](https://img.shields.io/badge/-development-blue)

The weight of the active partition.


**Instrument**: `updowncounter`

**Unit**: `{cpu}`



## `mainframe.partition.cpu.weight.is_capped` ![Development](https://img.shields.io/badge/-development-blue)

Indicating whether the initial CP processing weight is capped (0=false, 1=true).


**Instrument**: `updowncounter`

**Unit**: `{cpu}`


