# virtualization.platform Entity

> **[Semantic Convention](../../docs/registry/virtualization/entities.md#virtualizationplatform)**

## Required

| Attribute | Supporting Libraries |
| --- | --- |
| virtualization.platform.id | [hmc] |

## Recommended

| Attribute | Supporting Libraries |
| --- | --- |
| host.arch | [hmc] |
| host.id | [hmc] |
| host.name | [hmc] |
| host.type | [hmc] |
| mainframe.host.machine_model | [hmc] |
| mainframe.host.machine_type | [hmc] |
| mainframe.host.serial_number | [hmc] |
| virtualization.platform.firmware.version | [hmc] |
| virtualization.platform.serial_number | [hmc] |
| virtualization.system.name | [hmc] |

## Opt-In

| Attribute | Supporting Libraries |
| --- | --- |
| virtualization.platform.model | (none) |
| virtualization.platform.name | (none) |

[hmc]: ../scenarios/hmc/scenario.py
