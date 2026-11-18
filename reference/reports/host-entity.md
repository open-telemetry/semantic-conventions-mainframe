# host Entity

## Required

| Attribute | Supporting Libraries |
| --- | --- |
| host.id | [hmc] |

## Recommended

| Attribute | Supporting Libraries |
| --- | --- |
| host.arch | [hmc] |
| host.image.id | (none) |
| host.image.name | (none) |
| host.image.version | (none) |
| host.name | [hmc] |
| host.type | [hmc] |
| mainframe.host.machine_model | [hmc] |
| mainframe.host.machine_type | [hmc] |
| mainframe.host.serial_number | [hmc] |
| virtualization.partition.name | (none) |
| virtualization.platform.firmware.version | [hmc] |
| virtualization.platform.serial_number | [hmc] |
| virtualization.system.name | [hmc] |
| virtualization.vm.name | (none) |

## Opt-In

| Attribute | Supporting Libraries |
| --- | --- |
| host.ip | (none) |
| host.mac | (none) |
| virtualization.partition.type | (none) |
| virtualization.vm.state | (none) |

[hmc]: ../scenarios/hmc/scenario.py
