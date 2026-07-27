
# Entities: `mainframe`

This document describes the `mainframe` entities.


## `mainframe.adapter` ![Development](https://img.shields.io/badge/-development-blue)

A mainframe adapter, representing the physical I/O adapter that connects the Central Processor Complex (CPC) to peripheral devices.


| Property | Value |
|----------|-------|
| Stability | Development |




### Identity

| Attribute | Type | Requirement Level | Description |
|-----------|------|-------------------|-------------|
| `mainframe.adapter.name` | `string` | Required | The name of the I/O adapter in the form CSS.Chpid. |



### Description

| Attribute | Type | Requirement Level | Description |
|-----------|------|-------------------|-------------|
| `mainframe.adapter.type` | Enum | Required | Type of the adapter. |
| `mainframe.channel.owning.partition` | `string` | Recommended | The partition that owns the I/O channel, in case the channel is dedicated to a specific partition. If the channel is shared, this attribute is set to 'shared'. |



## `mainframe.channel` ![Development](https://img.shields.io/badge/-development-blue)

A mainframe channel, representing the physical I/O channel that connects the Central Processor Complex (CPC) to peripheral devices.


| Property | Value |
|----------|-------|
| Stability | Development |




### Identity

| Attribute | Type | Requirement Level | Description |
|-----------|------|-------------------|-------------|
| `mainframe.channel.name` | `string` | Required | The name of the I/O channel in the form CSS.Chpid. |



### Description

| Attribute | Type | Requirement Level | Description |
|-----------|------|-------------------|-------------|
| `mainframe.channel.mode` | Enum | Required | Mode the I/O channel is operating in. The mode can be either 'dedicated' or 'shared'. |
| `mainframe.channel.owning.partition` | `string` | Recommended | The partition that owns the I/O channel, in case the channel is dedicated to a specific partition. If the channel is shared, this attribute is set to 'shared'. |



## `mainframe.cpu` ![Development](https://img.shields.io/badge/-development-blue)

A mainframe CPU, representing the physical CPU within the Central Processor Complex (CPC).


| Property | Value |
|----------|-------|
| Stability | Development |




### Identity

| Attribute | Type | Requirement Level | Description |
|-----------|------|-------------------|-------------|
| `mainframe.cpu.name` | `string` | Required | The name of the processor in the form processor-type + processor ID. |



### Description

| Attribute | Type | Requirement Level | Description |
|-----------|------|-------------------|-------------|
| `mainframe.cpu.type` | Enum | Required | Type of mainframe processor. |



## `mainframe.host` ![Development](https://img.shields.io/badge/-development-blue)

A mainframe host, representing the pyhsical machine, also known as the Central Processor Complex (CPC).


| Property | Value |
|----------|-------|
| Stability | Development |




### Identity

| Attribute | Type | Requirement Level | Description |
|-----------|------|-------------------|-------------|
| `host.name` | `string` | Required | Name of the host. On Unix systems, it may contain what the hostname command returns, or the fully qualified hostname, or another name specified by the user. |



### Description

| Attribute | Type | Requirement Level | Description |
|-----------|------|-------------------|-------------|
| `host.arch` | Enum | Recommended | The CPU architecture the host system is running on. |
| `host.id` | `string` | Recommended | Unique host ID. For Cloud, this must be the instance_id assigned by the cloud provider. For non-containerized systems, this should be the `machine-id`. See the table below for the sources to use to determine the `machine-id` based on operating system. |
| `host.type` | `string` | Recommended | Type of host. For Cloud, this must be the machine type. |
| `mainframe.host.machine_model` | `string` | Recommended | IBM machine model of the Central Processor Complex (CPC). |
| `mainframe.host.machine_type` | `string` | Recommended | Four-digit IBM machine type of the Central Processor Complex (CPC). |
| `mainframe.host.serial_number` | `string` | Recommended | Serial number of the central processing complex (CPC). |


