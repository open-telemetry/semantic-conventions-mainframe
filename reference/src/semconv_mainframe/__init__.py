"""Shared support code for the Mainframe OTel reference scenarios."""

from __future__ import annotations

from pathlib import Path

REFERENCE_ROOT = Path(__file__).resolve().parent.parent.parent
SCENARIOS_DIR = REFERENCE_ROOT / "scenarios"
SEMCONV_ROOT = REFERENCE_ROOT.parent
MODEL_ROOT = SEMCONV_ROOT / "model"
# Build artifacts derived from model/: resolved on demand, never committed.
CACHE_DIR = REFERENCE_ROOT / ".cache"


def reference_data_file(library: str) -> Path:
    return SCENARIOS_DIR / library / "data.json"


def reference_project_dir(library: str) -> Path:
    return SCENARIOS_DIR / library


def reference_scenario_file(library: str) -> Path:
    return SCENARIOS_DIR / library / "scenario.py"


__all__ = [
    "CACHE_DIR",
    "MODEL_ROOT",
    "REFERENCE_ROOT",
    "SCENARIOS_DIR",
    "SEMCONV_ROOT",
    "reference_data_file",
    "reference_project_dir",
    "reference_scenario_file",
]
