#!/usr/bin/env python3
"""Report generation: README.md index and per-type detail pages.

Usage:
    uv run update-reports [--output FILE]
    python -m semconv_mainframe.report [--output FILE]

Builds deterministic markdown pages from committed scenarios/*/data.json files:
  - Injects a summary index between markers in README.md, listing every signal
    model/ declares and the scenarios that emit it.
  - Writes one detail page per signal that at least one scenario emits under
    reports/, and removes pages no longer generated.
"""

from __future__ import annotations

import argparse
import os
from collections.abc import Callable
from pathlib import Path

from semconv_mainframe import (
    REFERENCE_ROOT,
    SCENARIOS_DIR,
)
from semconv_mainframe.attribute_spec import AttributeSpec, RequirementLevel
from semconv_mainframe.data_files import (
    ScenarioDataEntry,
    entity_type_order,
    event_type_order,
    load_scenario_data_files,
    metric_type_order,
    span_type_order,
)
from semconv_mainframe.semconv_model import (
    entity_specs,
    event_specs,
    metric_specs,
    span_specs,
)

# ── Report page generation ───────────────────────────────────────────


DISPLAY_HIDDEN_ATTRS = frozenset({"error.type"})
EMPTY_TABLE_VALUE = "(none)"

OUTPUT_FILE = REFERENCE_ROOT / "README.md"
BEGIN_MARKER = "<!-- status:begin -->"
END_MARKER = "<!-- status:end -->"
LEVEL_ORDER = (
    RequirementLevel.REQUIRED,
    RequirementLevel.CONDITIONALLY_REQUIRED,
    RequirementLevel.RECOMMENDED,
    RequirementLevel.OPT_IN,
)
LEVEL_LABELS = {
    RequirementLevel.REQUIRED: "Required",
    RequirementLevel.CONDITIONALLY_REQUIRED: "Conditionally Required",
    RequirementLevel.RECOMMENDED: "Recommended",
    RequirementLevel.OPT_IN: "Opt-In",
}


def _spans_of(entry: ScenarioDataEntry) -> dict[str, dict[str, str]]:
    return entry.spans


def _events_of(entry: ScenarioDataEntry) -> dict[str, dict[str, str]]:
    return entry.events


def _entities_of(entry: ScenarioDataEntry) -> dict[str, dict[str, str]]:
    return entry.entities


def _metrics_of(entry: ScenarioDataEntry) -> dict[str, dict[str, str]]:
    return entry.metrics


# Registry namespaces this repository documents under docs/registry/<namespace>/.
LOCAL_NAMESPACES = ("mainframe", "virtualization", "zos")


def semconv_doc_link(type_key: str, signal_kind: str) -> str | None:
    """Relative path from reports/ to the generated registry page + anchor of a signal."""
    refinement = type_key.startswith("refinement.")
    namespace = type_key.removeprefix("refinement.").split(".", 1)[0]
    if namespace not in LOCAL_NAMESPACES:
        return None
    page = {"Metric": "metric", "Entity": "entity", "Event": "event", "Span": "span"}[signal_kind]
    page = f"{page}-refinements" if refinement else {"entity": "entities"}.get(page, f"{page}s")
    anchor = "".join(c for c in type_key if c.isalnum() or c in "-_")
    return f"../../docs/registry/{namespace}/{page}.md#{anchor}"


def _entry_sort_key(entry: ScenarioDataEntry) -> tuple[str, str]:
    return (entry.library.lower(), entry.library)


def _table_escape(value: str) -> str:
    return value.replace("|", "\\|")


def _supporting_libraries(
    entries: list[ScenarioDataEntry],
    type_key: str,
    attr_name: str,
    by_signal: Callable[[ScenarioDataEntry], dict[str, dict[str, str]]],
) -> list[ScenarioDataEntry]:
    return [entry for entry in entries if by_signal(entry).get(type_key, {}).get(attr_name) == "present"]


def _scenario_reference_path(scenario: str, output_dir: Path) -> str:
    scenario_path = SCENARIOS_DIR / scenario / "scenario.py"
    return Path(os.path.relpath(scenario_path, output_dir)).as_posix()


def _reference_key(library: str, scenario: str) -> str:
    return library if library == scenario else f"{library}@{scenario}"


def _supporting_library_refs(
    entries: list[ScenarioDataEntry],
    signal_kind: str,
    type_key: str,
    attr_name: str,
    used_references: set[tuple[str, str]],
) -> str:
    """Return a comma-separated list of short reference-style library links.

    The visible label remains the grouped instrumented library. The reference
    key also includes the scenario so two scenarios for one library can link to
    different files on the same report page.
    """
    if not entries:
        return EMPTY_TABLE_VALUE
    references = []
    for entry in entries:
        scenarios = entry.sources.get(signal_kind, {}).get(type_key, {}).get(attr_name, (entry.library,))
        for scenario in scenarios:
            used_references.add((entry.library, scenario))
            reference_key = _reference_key(entry.library, scenario)
            if reference_key == entry.library:
                references.append(f"[{entry.library}]")
            else:
                references.append(f"[{entry.library}][{reference_key}]")
    return ", ".join(references)


def _link_reference_block(references: set[tuple[str, str]], output_dir: Path) -> list[str]:
    """Return scenario-specific link-reference definitions."""
    if not references:
        return []
    return [
        f"[{_reference_key(library, scenario)}]: {_scenario_reference_path(scenario, output_dir)}"
        for library, scenario in sorted(references)
    ]


def _render_signal_section(
    entries: list[ScenarioDataEntry],
    type_key: str,
    spec: AttributeSpec,
    output_dir: Path,
    signal_kind: str,
    by_signal: Callable[[ScenarioDataEntry], dict[str, dict[str, str]]],
) -> list[str]:
    lines = [f"# {spec.label} {signal_kind}", ""]
    doc_link = semconv_doc_link(type_key, signal_kind)
    if doc_link:
        lines.append(f"> **[Semantic Convention]({doc_link})**")
        lines.append("")

    signal_kind_key = {
        "Span": "spans",
        "Event": "events",
        "Entity": "entities",
        "Metric": "metrics",
    }[signal_kind]
    used_references: set[tuple[str, str]] = set()
    for level in LEVEL_ORDER:
        attr_names = [a for a in spec.attrs_for_requirement_level(level) if a not in DISPLAY_HIDDEN_ATTRS]
        if not attr_names:
            continue

        lines.extend(
            [
                f"## {LEVEL_LABELS[level]}",
                "",
                "| Attribute | Supporting Libraries |",
                "| --- | --- |",
            ]
        )
        for attr_name in attr_names:
            libraries = _supporting_libraries(entries, type_key, attr_name, by_signal)
            library_refs = _supporting_library_refs(
                libraries,
                signal_kind_key,
                type_key,
                attr_name,
                used_references,
            )
            lines.append(f"| {_table_escape(attr_name)} | {library_refs} |")
        lines.append("")

    ref_lines = _link_reference_block(used_references, output_dir)
    if ref_lines:
        lines.extend(ref_lines)
        lines.append("")

    return lines


def _type_slug(type_key: str) -> str:
    """Convert a type key like 'mainframe.cpu.utilization' to a filename slug."""
    return type_key.replace("_", "-").replace(".", "-")


def _report_filename(type_key: str, signal_kind: str) -> str:
    return f"{_type_slug(type_key)}-{signal_kind}.md"


def _get_supporting_entries(
    entries: list[ScenarioDataEntry],
    type_key: str,
    spec: AttributeSpec,
    by_signal: Callable[[ScenarioDataEntry], dict[str, dict[str, str]]],
) -> list[ScenarioDataEntry]:
    """Return libraries that emit at least one required attribute for this signal type."""
    required_attrs = spec.attrs_for_requirement_level(RequirementLevel.REQUIRED)
    if not required_attrs:
        required_attrs = spec.attrs_for_requirement_level(RequirementLevel.CONDITIONALLY_REQUIRED)
    supporting = set()
    for attr_name in required_attrs:
        for entry in entries:
            if by_signal(entry).get(type_key, {}).get(attr_name) == "present":
                supporting.add(entry.library)
    return [e for e in entries if e.library in supporting]


def _generate_detail_page(lines: list[str]) -> str:
    return "\n".join(lines).rstrip() + "\n"


def _library_dir_links(entries: list[ScenarioDataEntry]) -> str:
    if not entries:
        return EMPTY_TABLE_VALUE
    return ", ".join(e.library for e in entries)


def _signal_kinds() -> list[tuple[str, str, list[tuple[str, AttributeSpec]], Callable]]:
    """(heading, signal kind, ordered specs, accessor) for every kind model/ declares signals of."""
    kinds = [
        ("Spans", "Span", [(key, span_specs()[key]) for key in span_type_order()], _spans_of),
        ("Events", "Event", [(key, event_specs()[key]) for key in event_type_order()], _events_of),
        ("Entities", "Entity", [(key, entity_specs()[key]) for key in entity_type_order()], _entities_of),
        ("Metrics", "Metric", [(key, metric_specs()[key]) for key in metric_type_order()], _metrics_of),
    ]
    return [kind for kind in kinds if kind[2]]


def _supporting(
    entries: list[ScenarioDataEntry],
    signal_kind: str,
    type_key: str,
    spec: AttributeSpec,
    by_signal: Callable[[ScenarioDataEntry], dict[str, dict[str, str]]],
) -> list[ScenarioDataEntry]:
    if signal_kind == "Metric":
        # Metrics carry few required attributes, so support is keyed on whether
        # the library emits the metric at all (key present in data), not on a
        # required-attribute fallback like the other signals.
        return [e for e in entries if type_key in by_signal(e)]
    return _get_supporting_entries(entries, type_key, spec, by_signal)


def generate_index_markdown(
    test_data_entries: list[ScenarioDataEntry],
) -> str:
    entries = sorted(test_data_entries, key=_entry_sort_key)
    lines = []
    for heading, signal_kind, specs, by_signal in _signal_kinds():
        lines.extend(["", f"### {heading}", "", f"| {signal_kind} | Libraries |", "| --- | --- |"])
        for type_key, spec in specs:
            supporting = _supporting(entries, signal_kind, type_key, spec, by_signal)
            filename = _report_filename(type_key, signal_kind.lower())
            label = f"[{spec.label}](reports/{filename})" if supporting else _table_escape(spec.label)
            lines.append(f"| {label} | {_library_dir_links(supporting)} |")

    lines.append("")
    return "\n".join(lines)


def write_report_pages(output_dir: Path) -> None:
    entries = sorted(load_scenario_data_files(), key=_entry_sort_key)
    reports_dir = output_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    for stale in reports_dir.glob("*.md"):
        stale.unlink()

    for _, signal_kind, specs, by_signal in _signal_kinds():
        for type_key, spec in specs:
            if not _supporting(entries, signal_kind, type_key, spec, by_signal):
                continue
            page_path = reports_dir / _report_filename(type_key, signal_kind.lower())
            page_lines = _render_signal_section(entries, type_key, spec, reports_dir, signal_kind, by_signal)
            page_path.write_text(_generate_detail_page(page_lines), encoding="utf-8")


def write_status_report(output_file: Path) -> None:
    output_dir = output_file.parent

    # Generate detail pages
    write_report_pages(output_dir)

    # Inject index into README.md
    content = output_file.read_text(encoding="utf-8")
    begin_idx = content.find(BEGIN_MARKER)
    end_idx = content.find(END_MARKER)
    if begin_idx == -1 or end_idx == -1:
        raise ValueError(f"{output_file} is missing {BEGIN_MARKER} / {END_MARKER} markers")

    generated = generate_index_markdown(load_scenario_data_files())
    new_content = content[: begin_idx + len(BEGIN_MARKER)] + generated + content[end_idx:]
    output_file.write_text(new_content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate checked-in markdown status report")
    parser.add_argument(
        "--output",
        default=str(OUTPUT_FILE),
        help="Markdown file to write (default: reference/README.md)",
    )
    args = parser.parse_args()

    output_file = Path(args.output)
    write_status_report(output_file)
    print(f"Status report written to {output_file}")


if __name__ == "__main__":
    main()
