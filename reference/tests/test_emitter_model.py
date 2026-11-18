"""The emitter's registry loader and topology, against small fixtures rather than model/."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from semconv_mainframe.emitter import Registry, TopologyError, build_topology, load_topology

FIXTURES = Path(__file__).parent / "fixtures"
CPC = {"entity": "virtualization.platform", "attributes": {"virtualization.platform.id": "3931-45A01"}}
BAD_CPU = {"entity": "mainframe.cpu", "each": [{"mainframe.cpu.name": "CP0", "mainframe.cpu.type": "zap"}]}


@pytest.fixture(scope="module")
def registry() -> Registry:
    return Registry.load(FIXTURES / "resolved_registry.yaml")


def test_refinements_of_upstream_metrics_are_emittable(registry: Registry) -> None:
    # P12: a refinement carries the instrument, unit and attributes of the
    # upstream signal it refines, whatever file format upstream defines it in.
    power = registry.metrics["refinement.virtualization.hw.host.power"]
    assert (power.name, power.instrument, power.unit, power.is_refinement) == ("hw.host.power", "gauge", "W", True)
    assert power.attributes["hw.id"].requirement_level == "required"
    assert power.attributes["hw.id"].examples == ("cpc",)
    assert [m.id for m in registry.metrics_for("virtualization.platform")] == [
        "mainframe.host.cpu.active.count",
        "refinement.mainframe.system.cpu.utilization",
        "refinement.virtualization.hw.host.power",
    ]


def test_value_types_and_enum_members(registry: Registry) -> None:
    assert registry.metrics["mainframe.host.cpu.active.count"].value_type == "int"
    assert registry.metrics["mainframe.cpu.utilization"].value_type == "double"
    assert registry.metrics["refinement.virtualization.hw.host.power"].value_type == "double"  # not annotated
    cpu_type = registry.metrics["mainframe.host.cpu.active.count"].attributes["mainframe.cpu.type"]
    assert (cpu_type.type, cpu_type.members) == ("enum", ("cp", "ifl"))
    assert cpu_type.accepts("cp") and not cpu_type.accepts("zap")
    conditional = registry.metrics["refinement.fixture.cpu.system.cpu.utilization"].attributes["cpu.mode"]
    assert conditional.requirement_level == "conditionally_required"


def test_entity_refinements_merge_by_type(registry: Registry) -> None:
    assert registry.schema_url == "https://opentelemetry.io/schemas/fixture/0.0.1"
    platform = registry.entities["virtualization.platform"]
    assert platform.identity == ("virtualization.platform.id",)
    assert platform.description == ("host.name", "mainframe.host.machine_type")


def test_topology_inherits_declared_attributes_only(registry: Registry) -> None:
    (cpc,) = load_topology(FIXTURES / "topology.yaml", registry)
    assert cpc.attributes == {
        "virtualization.platform.id": "3931-45A01",
        "host.name": "CPC01",
        "mainframe.host.machine_type": "3931",
    }
    assert [cpu.attributes for cpu in cpc.children] == [
        {"mainframe.cpu.name": "CP00", "virtualization.platform.id": "3931-45A01", "mainframe.cpu.type": "cp"},
        {"mainframe.cpu.name": "IFL00", "virtualization.platform.id": "3931-45A01", "mainframe.cpu.type": "ifl"},
    ]
    assert [n.entity_type for n in cpc.walk()] == ["virtualization.platform", "mainframe.cpu", "mainframe.cpu"]
    assert cpc.children[1].identity_key == ("mainframe.cpu", "IFL00", "3931-45A01")


@pytest.mark.parametrize(
    ("config", "message"),
    [
        ([{"entity": "mainframe.lpar"}], "unknown entity type"),
        ([{**CPC, "attributes": {**CPC["attributes"], "host.id": "x"}}], "declares no attribute 'host.id'"),
        ([{"entity": "mainframe.cpu", "attributes": {"mainframe.cpu.name": "CP00"}}], "identity attributes"),
        ([{**CPC, "children": [{**BAD_CPU}]}], "not a valid enum"),
        ([CPC, CPC], "share the identity"),
        ([{**CPC, "count": 2}], "unknown keys"),
    ],
)
def test_topology_errors(registry: Registry, config: list, message: str) -> None:
    with pytest.raises(TopologyError, match=message):
        build_topology(yaml.safe_load(yaml.safe_dump(config)), registry)
