"""Reports built from data files, against the fixture registry rather than model/."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from semconv_mainframe import report, run_scenario, scenarios, semconv_model
from semconv_mainframe.data_files import _normalize_scenario_data_entry
from semconv_mainframe.live_check import coverage_model

FIXTURES = Path(__file__).parent / "fixtures"
DATA = {
    "spans": {},
    "events": {},
    "metrics": {"refinement.virtualization.hw.host.power": ["hw.id"]},
    "entities": {"virtualization.platform": {"identity": ["virtualization.platform.id"], "description": []}},
    "findings": [],
}


@pytest.fixture(autouse=True)
def fixture_model():
    model = coverage_model(yaml.safe_load((FIXTURES / "resolved_registry.yaml").read_text()))
    for cached in (semconv_model._model, *(getattr(semconv_model, f"{k}_specs") for k in report_kinds())):
        cached.cache_clear()
    with patch.object(semconv_model, "_model", lambda: model):
        yield
    for k in report_kinds():
        getattr(semconv_model, f"{k}_specs").cache_clear()


def report_kinds() -> tuple[str, ...]:
    return ("span", "event", "metric", "entity")


def test_metric_specs_cover_every_definition_with_derived_labels() -> None:
    specs = semconv_model.metric_specs()
    assert specs["refinement.virtualization.hw.host.power"].label == "hw.host.power on virtualization.platform"
    assert specs["refinement.virtualization.hw.host.power"].required == ("hw.id",)
    assert specs["mainframe.cpu.utilization"].label == "mainframe.cpu.utilization"
    assert semconv_model.entity_specs()["mainframe.cpu"].required == (
        "mainframe.cpu.name",
        "virtualization.platform.id",
    )


def test_index_lists_every_signal_and_links_only_supported_ones() -> None:
    entry = _normalize_scenario_data_entry(DATA, "hmc")
    index = report.generate_index_markdown([entry])
    assert "### Spans" not in index  # the fixture registry declares none
    page = "reports/refinement-virtualization-hw-host-power-metric.md"
    assert f"| [hw.host.power on virtualization.platform]({page}) | hmc |" in index
    assert "| mainframe.cpu.utilization | (none) |" in index
    assert "| [virtualization.platform](reports/virtualization-platform-entity.md) | hmc |" in index


def test_report_pages_are_written_for_supported_signals_only(tmp_path: Path) -> None:
    scenario = tmp_path / "scenarios" / "hmc"
    scenario.mkdir(parents=True)
    (scenario / "data.json").write_text(json.dumps(DATA))
    (tmp_path / "reports").mkdir()
    (tmp_path / "reports" / "stale-metric.md").write_text("old")
    with patch("semconv_mainframe.data_files.SCENARIOS_DIR", tmp_path / "scenarios"):
        report.write_report_pages(tmp_path)
    pages = sorted(p.name for p in (tmp_path / "reports").iterdir())
    assert pages == ["refinement-virtualization-hw-host-power-metric.md", "virtualization-platform-entity.md"]
    page = (tmp_path / "reports" / pages[0]).read_text()
    assert "../../docs/registry/virtualization/metric-refinements.md#refinementvirtualizationhwhostpower" in page
    assert "| hw.id | [hmc] |" in page
    assert "| hw.name | (none) |" in page


def test_semconv_doc_links() -> None:
    assert (
        report.semconv_doc_link("mainframe.cpu", "Entity") == "../../docs/registry/mainframe/entities.md#mainframecpu"
    )
    assert report.semconv_doc_link("mainframe.cpu.smt_mode.utilization", "Metric").endswith(
        "mainframe/metrics.md#mainframecpusmt_modeutilization"
    )
    assert report.semconv_doc_link("host", "Entity") is None


def test_ci_matrix_with_no_scenarios(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    with patch.object(scenarios, "SCENARIOS_DIR", tmp_path / "missing"):
        assert run_scenario.main(["--print-ci-matrix"]) == 0
        assert json.loads(capsys.readouterr().out) == {"scenario": []}
        assert run_scenario.main(["hmc"]) == 1


def test_ci_matrix_lists_runnable_scenarios(tmp_path: Path) -> None:
    for name, files in {"hmc": ("conformance.yaml", "scenario.py"), "draft": ("scenario.py",)}.items():
        (tmp_path / name).mkdir()
        for file in files:
            (tmp_path / name / file).write_text("")
    with patch.object(scenarios, "SCENARIOS_DIR", tmp_path):
        assert scenarios.list_reference_libraries() == ["hmc"]
        assert scenarios.build_reference_scenario_matrix()["scenario"][0]["lib"] == "hmc"
