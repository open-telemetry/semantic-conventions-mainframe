"""The registry the emitter emits from: weaver's resolution of ``model/``.

The emitter reads ``weaver registry resolve --v2`` output rather than the YAML
under ``model/``. Upstream definitions then arrive resolved whichever file
format upstream uses for them -- v1 ``groups:`` or ``definition/2`` -- and a
refinement arrives with the attributes, instrument and unit of the upstream
signal it refines. Hand-parsing only the v1 format is what left the ``hw.*``
refinements unemitted before (review finding P12).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

AttributeValue = str | int | float | bool | list[str]
_PY_TYPES: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "int": (int,),
    "double": (float, int),
    "boolean": (bool,),
    "string[]": (list,),
}


@dataclass(frozen=True)
class AttributeDef:
    key: str
    type: str  # a primitive type name, or "enum"
    requirement_level: str = "recommended"
    members: tuple[str | int, ...] = ()
    examples: tuple[Any, ...] = ()

    @classmethod
    def from_resolved(cls, attribute: Mapping[str, Any]) -> AttributeDef:
        declared = attribute.get("type", "string")
        level = attribute.get("requirement_level", "recommended")
        examples = attribute.get("examples")
        return cls(
            key=attribute["key"],
            type="enum" if isinstance(declared, dict) else str(declared),
            requirement_level=str(next(iter(level))) if isinstance(level, dict) else str(level),
            members=tuple(m["value"] for m in declared.get("members", [])) if isinstance(declared, dict) else (),
            examples=tuple(examples if isinstance(examples, list) else [examples] if examples is not None else []),
        )

    def accepts(self, value: object) -> bool:
        """Whether ``value`` is valid for this attribute: a member of an enum, else of its type."""
        if self.type == "enum":
            return value in self.members
        types = _PY_TYPES.get(self.type)
        return types is None or (isinstance(value, types) and not (isinstance(value, bool) and bool not in types))


@dataclass(frozen=True)
class MetricDef:
    id: str
    name: str
    instrument: str  # gauge, counter, updowncounter or histogram
    unit: str
    entity_associations: tuple[str, ...]
    attributes: Mapping[str, AttributeDef]
    value_type: str = "double"  # or "int", from the code_generation annotation

    @property
    def is_refinement(self) -> bool:
        return self.id != self.name


@dataclass(frozen=True)
class EntityDef:
    type: str
    identity: tuple[str, ...]
    description: tuple[str, ...]
    attributes: Mapping[str, AttributeDef]


@dataclass(frozen=True)
class Registry:
    metrics: Mapping[str, MetricDef]
    entities: Mapping[str, EntityDef]
    schema_url: str = ""

    @classmethod
    def from_resolved(cls, resolved: Mapping[str, Any]) -> Registry:
        """Every metric (refinements under their own id) and entity type (refinements merged)."""
        refinements = resolved.get("refinements", {})
        metrics = {}
        for metric in refinements.get("metrics", []):
            annotations = metric.get("annotations") or {}
            metrics[metric["id"]] = MetricDef(
                id=metric["id"],
                name=metric["name"],
                instrument=metric["instrument"],
                unit=metric.get("unit", "1"),
                entity_associations=tuple(metric.get("entity_associations") or ()),
                attributes={a["key"]: AttributeDef.from_resolved(a) for a in metric.get("attributes") or []},
                value_type=(annotations.get("code_generation") or {}).get("metric_value_type", "double"),
            )
        identity: dict[str, dict[str, None]] = {}
        description: dict[str, dict[str, None]] = {}
        attributes: dict[str, dict[str, AttributeDef]] = {}
        for entity in refinements.get("entities", []):
            kind = entity["type"]
            for section, keys in (("identity", identity), ("description", description)):
                for attribute in entity.get(section) or []:
                    keys.setdefault(kind, {})[attribute["key"]] = None
                    attributes.setdefault(kind, {})[attribute["key"]] = AttributeDef.from_resolved(attribute)
        entities = {
            kind: EntityDef(
                type=kind,
                identity=tuple(identity.get(kind, {})),
                description=tuple(k for k in description.get(kind, {}) if k not in identity.get(kind, {})),
                attributes=attributes.get(kind, {}),
            )
            for kind in attributes
        }
        return cls(metrics=metrics, entities=entities, schema_url=str(resolved.get("schema_url") or ""))

    @classmethod
    def load(cls, path: Path) -> Registry:
        """A resolved registry file, JSON as weaver writes it or YAML."""
        text = path.read_text(encoding="utf-8")
        return cls.from_resolved(json.loads(text) if path.suffix == ".json" else yaml.safe_load(text))

    @classmethod
    def from_model(cls) -> Registry:
        """The working tree's ``model/``, resolved by weaver (cached under ``reference/.cache``)."""
        # Imported here: the emitter itself needs no weaver.
        from semconv_mainframe.conformance import resolved_registry

        return cls.load(resolved_registry())

    def metrics_for(self, entity_type: str) -> list[MetricDef]:
        """Every metric definition associated with ``entity_type``, by id."""
        return [m for _, m in sorted(self.metrics.items()) if entity_type in m.entity_associations]
