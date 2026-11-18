"""What attributes each span, event, metric and entity type in ``model/`` declares.

Read from the coverage model: weaver's own resolution of ``model/``, and the
same view a run is reduced against, so the reports and ``data.json`` can never
disagree about what a signal declares. It is a build artifact, resolved into
``reference/.cache/`` whenever ``model/`` is newer.

Resolving it shells out to weaver, so the specs are built on first use rather
than at import: importing this module does no work.

Unlike the GenAI reports, which cover a curated list of signals, these cover
every signal ``model/`` declares, metric refinements under their own id; the
labels are derived from the registry.

Ordering convention: every attribute / signal list written to a committed
artifact (``scenarios/<lib>/data.json``, the generated status reports, the
README injection) is sorted alphabetically. Please preserve this when adding
new emitters -- downstream diffs and `git diff --exit-code` in CI rely on a
single deterministic order.
"""

from __future__ import annotations

import json
from functools import cache
from typing import Any

from semconv_mainframe.attribute_spec import AttributeSpec
from semconv_mainframe.conformance import coverage_model


def _spec(attributes: dict[str, str], registry_id: str, label: str) -> AttributeSpec:
    buckets: dict[str, list[str]] = {
        "required": [],
        "conditionally_required": [],
        "recommended": [],
        "opt_in": [],
    }
    for name, level in sorted(attributes.items()):
        buckets[level.removesuffix("_conditional")].append(name)
    return AttributeSpec(
        label=label,
        required=tuple(buckets["required"]),
        conditionally_required=tuple(buckets["conditionally_required"]),
        recommended=tuple(buckets["recommended"]),
        opt_in=tuple(buckets["opt_in"]),
        registry_id=registry_id,
    )


def metric_label(metric_id: str, metric: dict[str, Any]) -> str:
    """A metric's name, plus the entities a refinement scopes it to."""
    if metric_id == metric["name"]:
        return metric_id
    return f"{metric['name']} on {', '.join(metric['entity_associations'])}"


@cache
def _model() -> dict[str, dict]:
    return json.loads(coverage_model().read_text(encoding="utf-8"))


@cache
def span_specs() -> dict[str, AttributeSpec]:
    return {key: _spec(span["attributes"], key, key) for key, span in sorted(_model()["spans"].items())}


@cache
def event_specs() -> dict[str, AttributeSpec]:
    return {name: _spec(event["attributes"], name, name) for name, event in sorted(_model()["events"].items())}


@cache
def metric_specs() -> dict[str, AttributeSpec]:
    return {
        key: _spec(metric["attributes"], key, metric_label(key, metric))
        for key, metric in sorted(_model()["metrics"].items(), key=lambda item: (item[1]["name"], item[0]))
    }


@cache
def entity_specs() -> dict[str, AttributeSpec]:
    return {
        name: _spec({**entity["description"], **entity["identity"]}, name, name)
        for name, entity in sorted(_model()["entities"].items())
    }
