"""The entity topology a scenario emits for: which entities exist, and how they nest.

A topology file lists entity nodes::

    - entity: virtualization.platform
      attributes: {virtualization.platform.id: 3931-45A01, host.id: 3931-45A01}
      children:
        - entity: mainframe.cpu
          each:                     # one sibling node per entry
            - {mainframe.cpu.name: CP00, mainframe.cpu.type: cp}
            - {mainframe.cpu.name: IFL00, mainframe.cpu.type: ifl}

Every node becomes one OTLP resource carrying exactly the attributes its
entity declares (identity and description). A node takes a declared attribute
it does not set from its nearest ancestor that has it, which is how a
processor gets the ``virtualization.platform.id`` of its CPC. Nodes are
checked against the registry: the entity must exist, every attribute must be
declared by it and valid for its type, the identity must be complete and
unique.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from semconv_mainframe.emitter.registry import AttributeValue, Registry


class TopologyError(ValueError):
    """A topology that does not fit the registry."""


@dataclass
class Node:
    entity_type: str
    attributes: dict[str, AttributeValue]
    identity: tuple[str, ...]
    children: list[Node] = field(default_factory=list)

    @property
    def identity_key(self) -> tuple[Any, ...]:
        return (self.entity_type, *(str(self.attributes[k]) for k in self.identity))

    def walk(self) -> Iterator[Node]:
        yield self
        for child in self.children:
            yield from child.walk()


def _build(spec: Mapping[str, Any], inherited: Mapping[str, Any], registry: Registry, where: str) -> list[Node]:
    entity_type = spec.get("entity")
    entity = registry.entities.get(str(entity_type))
    if entity is None:
        raise TopologyError(f"{where}: unknown entity type {entity_type!r}")
    unknown_keys = sorted(set(spec) - {"entity", "attributes", "each", "children"})
    if unknown_keys:
        raise TopologyError(f"{where}: unknown keys {unknown_keys}")
    nodes = []
    for index, variant in enumerate(spec.get("each") or [{}]):
        own = {**(spec.get("attributes") or {}), **variant}
        label = f"{where}[{index}]" if "each" in spec else where
        for key, value in own.items():
            declared = entity.attributes.get(key)
            if declared is None:
                raise TopologyError(f"{label}: {entity_type} declares no attribute {key!r}")
            if not declared.accepts(value):
                raise TopologyError(f"{label}: {value!r} is not a valid {declared.type} for {key}")
        context = {**inherited, **own}
        attributes = {k: context[k] for k in (*entity.identity, *entity.description) if k in context}
        missing = [k for k in entity.identity if k not in attributes]
        if missing:
            raise TopologyError(f"{label}: {entity_type} identity attributes {missing} are not set")
        node = Node(str(entity_type), attributes, entity.identity)
        for child_index, child in enumerate(spec.get("children") or []):
            node.children += _build(child, context, registry, f"{label}.children[{child_index}]")
        nodes.append(node)
    return nodes


def build_topology(config: list[Mapping[str, Any]], registry: Registry) -> list[Node]:
    """The root nodes of a topology, checked against ``registry``."""
    roots = [node for i, spec in enumerate(config) for node in _build(spec, {}, registry, f"topology[{i}]")]
    seen: set[tuple[Any, ...]] = set()
    for node in (n for root in roots for n in root.walk()):
        if node.identity_key in seen:
            raise TopologyError(f"two {node.entity_type} nodes share the identity {node.identity_key[1:]}")
        seen.add(node.identity_key)
    return roots


def load_topology(path: Path, registry: Registry) -> list[Node]:
    return build_topology(yaml.safe_load(path.read_text(encoding="utf-8")) or [], registry)
