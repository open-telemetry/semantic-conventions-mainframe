# virtualization.vm Entity

> **[Semantic Convention](../../docs/registry/virtualization/entities.md#virtualizationvm)**

## Required

| Attribute | Supporting Libraries |
| --- | --- |
| virtualization.vm.id | [hmc] |

## Recommended

| Attribute | Supporting Libraries |
| --- | --- |
| mainframe.zvm.guest.userid | [hmc] |
| mainframe.zvm.hypervisor.name | [hmc] |
| virtualization.system.name | [hmc] |
| virtualization.vm.cpu.count | [hmc] |
| virtualization.vm.instance_id | (none) |
| virtualization.vm.machine_type | [hmc] |
| virtualization.vm.memory.size | [hmc] |
| virtualization.vm.name | [hmc] |
| virtualization.vm.nested_virtualization.enabled | [hmc] |
| virtualization.vm.state | [hmc] |

[hmc]: ../scenarios/hmc/scenario.py
