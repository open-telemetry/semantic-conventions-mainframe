"""The runner's own logic: conformance.yaml, the coverage model, and reducing a weaver report."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from semconv_mainframe.live_check import (
    Observed,
    SpecError,
    check,
    classify_metric,
    coverage_model,
    load_spec,
    observe,
    reduce,
)

FIXTURES = Path(__file__).parent / "fixtures"
CPC = {"virtualization.platform.id": "3931-45A01", "host.name": "CPC01", "mainframe.host.machine_type": "3931"}
CP0 = {"virtualization.platform.id": "3931-45A01", "mainframe.cpu.name": "CP0", "mainframe.cpu.type": "cp"}


@pytest.fixture(scope="module")
def model() -> dict:
    return coverage_model(yaml.safe_load((FIXTURES / "resolved_registry.yaml").read_text()))


def _attrs(values: dict, advice: tuple[dict, ...] = ()) -> list[dict]:
    result = {"all_advice": list(advice)}
    return [{"name": k, "value": v, "live_check_result": result} for k, v in values.items()]


def _metric(name: str, *points: dict) -> dict:
    return {"metric": {"name": name, "data_points": [{"attributes": _attrs(p)} for p in points]}}


def _report(*samples: dict) -> dict:
    return {"samples": list(samples), "statistics": {}}


def _resource(values: dict, advice: tuple[dict, ...] = ()) -> dict:
    return {"resource": {"attributes": _attrs(values, advice)}}


def _write_spec(tmp_path: Path, body: dict) -> Path:
    (tmp_path / "conformance.yaml").write_text(yaml.safe_dump(body))
    return tmp_path


def test_coverage_model_keys_refinements_by_id_and_merges_entities(model: dict) -> None:
    assert model["metrics"]["refinement.virtualization.hw.host.power"]["name"] == "hw.host.power"
    assert model["metrics"]["refinement.fixture.cpu.system.cpu.utilization"]["attributes"] == {
        "cpu.mode": "conditionally_required"
    }
    platform = model["entities"]["virtualization.platform"]
    assert platform["identity"] == {"virtualization.platform.id": "required"}
    assert platform["description"] == {"host.name": "recommended", "mainframe.host.machine_type": "opt_in"}


def test_classify_metric_picks_the_refinement_of_the_resource_entity(model: dict) -> None:
    cpu, cpc = set(CP0), set(CPC)
    assert classify_metric("system.cpu.utilization", cpu, {"cpu.mode"}, model) == (
        "refinement.fixture.cpu.system.cpu.utilization"
    )
    assert classify_metric("system.cpu.utilization", cpc, {"cpu.mode", "mainframe.cpu.type"}, model) == (
        "refinement.mainframe.system.cpu.utilization"
    )
    assert classify_metric("system.memory.usage", cpc, set(), model) is None


def test_observe_pairs_data_points_with_the_preceding_resource(model: dict) -> None:
    observed = observe(
        _report(
            _resource(CPC),
            _metric("hw.host.power", {"hw.id": "cpc", "not.declared": 1}),
            _metric("system.cpu.utilization", {"cpu.mode": "user", "mainframe.cpu.type": "cp"}),
            _resource(CP0),
            _metric("system.cpu.utilization", {"cpu.mode": "user"}),
            _metric("mainframe.cpu.utilization", {"mainframe.cpu.name": "CP0"}),
        ),
        model,
    )
    data = reduce(observed, model)
    assert data["metrics"] == {
        "mainframe.cpu.utilization": ["mainframe.cpu.name"],
        "refinement.fixture.cpu.system.cpu.utilization": ["cpu.mode"],
        "refinement.mainframe.system.cpu.utilization": ["cpu.mode", "mainframe.cpu.type"],
        "refinement.virtualization.hw.host.power": ["hw.id"],
    }
    assert data["entities"] == {
        "mainframe.cpu": {
            "identity": ["mainframe.cpu.name", "virtualization.platform.id"],
            "description": ["mainframe.cpu.type"],
        },
        "virtualization.platform": {
            "identity": ["virtualization.platform.id"],
            "description": ["host.name", "mainframe.host.machine_type"],
        },
    }
    assert observed.metric_names == {"hw.host.power", "system.cpu.utilization", "mainframe.cpu.utilization"}
    assert list(data) == ["spans", "events", "metrics", "entities", "findings"]


def test_only_violations_become_findings(model: dict) -> None:
    advice = (
        {"id": "not_stable", "level": "improvement", "message": "dev", "signal_type": "resource"},
        {"id": "missing_attribute", "level": "violation", "message": "Attribute 'x' does not exist.",
         "signal_type": "resource", "context": {"attribute_key": "x"}},
    )  # fmt: skip
    observed = observe(_report(_resource({"x": 1}, advice)), model)
    observe(_report(_resource({"x": 1}, advice)), model, observed)  # the same finding twice is one
    assert reduce(observed, model)["findings"] == [
        {
            "id": "missing_attribute",
            "message": "Attribute 'x' does not exist.",
            "signal_type": "resource",
            "context": {"attribute_key": "x"},
        }
    ]


def test_load_spec(tmp_path: Path) -> None:
    spec = load_spec(
        _write_spec(
            tmp_path,
            {
                "runner": "mainframe-conformance",
                "instrumented_library": "hmc",
                "scenarios": {"cpc": {"run": "python scenario.py", "metrics": ["a"]}},
                "expected_violations": [{"id": "missing_attribute", "reason": "why"}],
            },
        )
    )
    assert spec.instrumented_library == "hmc"
    assert spec.scenarios["cpc"].metrics == ("a",)
    assert spec.scenarios["cpc"].events is None
    assert spec.expected_violations[0].context is None


@pytest.mark.parametrize(
    "body",
    [
        {"runner": "genai-conformance", "scenarios": {"a": {"run": "x"}}},
        {"server": {"run": "mock"}, "scenarios": {"a": {"run": "x"}}},
        {"scenarios": {"a": {"run": "x", "spans": []}}},
        {"scenarios": {"a": {}}},
        {"scenarios": {}},
    ],
)
def test_load_spec_rejects_what_this_runner_cannot_do(tmp_path: Path, body: dict) -> None:
    with pytest.raises(SpecError):
        load_spec(_write_spec(tmp_path, body))


def test_check_declared_metrics_and_violations(tmp_path: Path, model: dict) -> None:
    spec = load_spec(
        _write_spec(
            tmp_path,
            {
                "scenarios": {
                    "cpc": {
                        "run": "true",
                        "metrics": ["hw.host.power", "mainframe.host.cpu.active.count"],
                        "expected_violations": [
                            {"id": "gone", "reason": "fixed upstream"},
                            {"id": "missing_attribute", "context": {"attribute_key": "y"}, "reason": "known"},
                        ],
                    }
                }
            },
        )
    )
    advice = tuple(
        {"id": "missing_attribute", "level": "violation", "message": key, "context": {"attribute_key": key}}
        for key in ("x", "y")
    )
    observed = observe(_report(_resource(CPC, advice), _metric("hw.host.power", {}), _metric("extra")), model)
    failures, violations = check(spec.scenarios["cpc"], spec, observed)
    assert failures == [
        "declared metric mainframe.host.cpu.active.count was not emitted",
        "undeclared metric extra was emitted",
        "expected violation gone was not reported (fixed upstream)",
    ]
    assert violations == ["missing_attribute: x"]
    assert check(spec.scenarios["cpc"], spec, Observed(metric_names={"hw.host.power"}))[1] == []
