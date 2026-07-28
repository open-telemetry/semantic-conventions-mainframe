"""
Report updater: ``uv run update-reports``

Reads all committed ``scenarios/*/data.json`` files and regenerates the
``<!-- status:begin --> … <!-- status:end -->`` section in ``reference/README.md``.

The report lists every unique metric name found across all scenarios, grouped
by entity type, and which scenarios exercise each metric.
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

REFERENCE_DIR = Path(__file__).parents[2]
SCENARIOS_DIR = REFERENCE_DIR / "scenarios"
README = REFERENCE_DIR / "README.md"

_BEGIN = "<!-- status:begin -->"
_END = "<!-- status:end -->"


def _load_data() -> dict[str, list[dict]]:
    """Return {scenario_name: [data_point, …]} for all committed data.json files."""
    result: dict[str, list[dict]] = {}
    for data_file in sorted(SCENARIOS_DIR.glob("*/data.json")):
        name = data_file.parent.name
        result[name] = json.loads(data_file.read_text())
    return result


def _namespace(metric_name: str) -> str:
    """Extract the second-level namespace of a metric name.

    e.g. ``mainframe.host.cpu.active.count`` → ``mainframe.host``
         ``mainframe.partition.nic.bytes.sent`` → ``mainframe.partition.nic``
         ``mainframe.adapter.port.bytes.sent`` → ``mainframe.adapter.port``
    """
    parts = metric_name.split(".")
    # Use up to 3 parts as the namespace key (e.g. mainframe.adapter.port)
    return ".".join(parts[:3])


def _build_report(data: dict[str, list[dict]]) -> str:
    """Build the markdown content between the status markers."""
    # metric_name → set of scenario names
    coverage: dict[str, set[str]] = defaultdict(set)
    for scenario, points in data.items():
        for pt in points:
            coverage[pt["name"]].add(scenario)

    if not coverage:
        return "### Metrics\n\nNo scenarios have been run yet.\n"

    # Group by namespace
    by_ns: dict[str, list[str]] = defaultdict(list)
    for metric in sorted(coverage):
        by_ns[_namespace(metric)].append(metric)

    lines = ["### Metrics\n"]
    lines.append("| Metric | Scenarios |")
    lines.append("| --- | --- |")
    for ns in sorted(by_ns):
        for metric in by_ns[ns]:
            scenarios_str = ", ".join(f"`{s}`" for s in sorted(coverage[metric]))
            lines.append(f"| `{metric}` | {scenarios_str} |")

    lines.append("")
    return "\n".join(lines)


def main() -> None:
    data = _load_data()
    if not data:
        print("No data.json files found under scenarios/. Run some scenarios first.")
        return

    report = _build_report(data)

    readme_text = README.read_text()
    pattern = re.compile(
        rf"{re.escape(_BEGIN)}.*?{re.escape(_END)}", re.DOTALL
    )
    replacement = f"{_BEGIN}\n{report}\n{_END}"
    if not pattern.search(readme_text):
        print(f"ERROR: markers {_BEGIN!r} / {_END!r} not found in {README}",
              file=sys.stderr)
        sys.exit(1)

    new_text = pattern.sub(replacement, readme_text)
    README.write_text(new_text)
    total = sum(len(pts) for pts in data.values())
    metrics = len({pt["name"] for pts in data.values() for pt in pts})
    print(f"Updated {README.name}: {metrics} metrics across {len(data)} scenarios "
          f"({total} total data points).")
