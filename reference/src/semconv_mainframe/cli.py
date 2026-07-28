"""
CLI entry point: ``uv run run-scenario <scenario>``

Runs a named scenario from ``scenarios/<scenario>/scenario.py`` and writes
its output to ``scenarios/<scenario>/data.json``.

Usage::

    uv run run-scenario host
    uv run run-scenario partition
    uv run run-scenario network
    uv run run-scenario storage
    uv run run-scenario --all
    uv run run-scenario --all --keep-going
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

SCENARIOS_DIR = Path(__file__).parents[2] / "scenarios"
_KNOWN = ["host", "partition", "network", "storage"]


def _run_one(name: str) -> bool:
    """Import and run ``scenarios/<name>/scenario.py``. Returns True on success."""
    scenario_dir = SCENARIOS_DIR / name
    scenario_file = scenario_dir / "scenario.py"
    if not scenario_file.exists():
        print(f"ERROR: scenario '{name}' not found at {scenario_file}", file=sys.stderr)
        return False

    # Ensure the shared framework is importable from the scenario
    src_dir = Path(__file__).parents[2] / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

    spec = importlib.util.spec_from_file_location(f"scenario_{name}", scenario_file)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
        mod.main()
        return True
    except Exception as exc:
        print(f"ERROR running scenario '{name}': {exc}", file=sys.stderr)
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Run mainframe reference scenarios.")
    parser.add_argument("scenario", nargs="?", choices=_KNOWN,
                        help="Scenario to run (host, partition, network, storage).")
    parser.add_argument("--all", action="store_true", help="Run all known scenarios.")
    parser.add_argument("--keep-going", action="store_true",
                        help="Continue past failures and report at end.")
    args = parser.parse_args()

    if args.all:
        names = _KNOWN
    elif args.scenario:
        names = [args.scenario]
    else:
        parser.error("Specify a scenario name or --all.")

    failures = []
    for name in names:
        print(f"--- Running scenario: {name} ---")
        ok = _run_one(name)
        if not ok:
            failures.append(name)
            if not args.keep_going:
                sys.exit(1)

    if failures:
        print(f"\nFailed scenarios: {', '.join(failures)}", file=sys.stderr)
        sys.exit(1)
    print("\nAll scenarios passed.")
