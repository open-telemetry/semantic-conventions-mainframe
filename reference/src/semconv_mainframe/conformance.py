"""Running a scenario directory under Weaver live-check.

The GenAI reference scenarios run under the shared conformance runner from
`open-telemetry/semantic-conventions-conformance
<https://github.com/open-telemetry/semantic-conventions-conformance>`_. That
runner has no mainframe domain yet, so this module runs the subset of it this
repository uses -- a scenario's ``run`` command against a fresh
``weaver registry live-check`` per scenario -- reading the same
``conformance.yaml`` keys and writing ``data.json`` in the same shape (see
:mod:`semconv_mainframe.live_check`).

Every run validates against the working tree's ``model/`` together with the
filtered upstream registry it depends on (``make filter-upstream``), so a
change to the conventions takes effect immediately. ``--include-unreferenced``
makes the upstream signals this registry refines known to live-check.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from semconv_mainframe import CACHE_DIR, MODEL_ROOT, SEMCONV_ROOT
from semconv_mainframe.live_check import Observed, PackageSpec, ScenarioSpec, check, load_spec, observe, reduce
from semconv_mainframe.live_check import coverage_model as build_coverage_model
from semconv_mainframe.weaver import in_container, run_weaver, weaver_command

logger = logging.getLogger(__name__)

# model/ as weaver resolves it, and what it declares per signal. Build
# artifacts: derived from model/, cached, never committed.
RESOLVED_REGISTRY = CACHE_DIR / "resolved-registry.json"
COVERAGE_MODEL = CACHE_DIR / "coverage-model.json"
UPSTREAM_REGISTRY = SEMCONV_ROOT / ".build" / "sc-upstream-filtered"

WEAVER_STARTUP_TIMEOUT_SECONDS = 300  # a first run may pull the weaver image
WEAVER_STOP_TIMEOUT_SECONDS = 120
WEAVER_INACTIVITY_TIMEOUT_SECONDS = 300
SCENARIO_TIMEOUT_SECONDS = 600
REPORT_DIR = Path("output") / "weaver-reports"
_OTLP_SIGNAL_ENV = tuple(
    f"OTEL_EXPORTER_OTLP_{signal}_{setting}"
    for signal in ("TRACES", "METRICS", "LOGS")
    for setting in ("ENDPOINT", "PROTOCOL")
)


def _relative(path: Path) -> str:
    """``path`` as weaver sees it from the repository root."""
    return path.resolve().relative_to(SEMCONV_ROOT.resolve()).as_posix()


def _is_stale(output: Path) -> bool:
    """True unless ``output`` is there and newer than all source dependencies."""
    if not output.is_file():
        return True
    resolved_at = output.stat().st_mtime
    versions_env = SEMCONV_ROOT / "versions.env"
    if versions_env.is_file() and versions_env.stat().st_mtime > resolved_at:
        return True
    return any(source.stat().st_mtime > resolved_at for source in MODEL_ROOT.rglob("*") if source.is_file())


def resolved_registry(output: Path = RESOLVED_REGISTRY) -> Path:
    """``weaver registry resolve --v2`` of ``model/``, resolved again if the cache is stale."""
    if not _is_stale(output):
        return output
    if not UPSTREAM_REGISTRY.is_dir():
        raise RuntimeError(f"{UPSTREAM_REGISTRY} is missing; run `make filter-upstream` from {SEMCONV_ROOT}")
    output.unlink(missing_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Resolving %s into %s", MODEL_ROOT, output)
    run_weaver(["registry", "resolve", "--quiet", "--v2", "-r", "./model", "--format", "json", "-o", _relative(output)])
    return output


def coverage_model(output: Path = COVERAGE_MODEL) -> Path:
    """The coverage model for ``model/``: what each signal declares (see live_check)."""
    registry = resolved_registry()
    if output.is_file() and output.stat().st_mtime >= registry.stat().st_mtime:
        return output
    model = build_coverage_model(json.loads(registry.read_text(encoding="utf-8")))
    output.write_text(json.dumps(model, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


def _free_ports(count: int) -> list[int]:
    """Ask the OS for unused loopback TCP ports to reduce collisions in CI."""
    sockets: list[socket.socket] = []
    try:
        for _ in range(count):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(("127.0.0.1", 0))
            sockets.append(sock)
        return [sock.getsockname()[1] for sock in sockets]
    finally:
        for sock in sockets:
            sock.close()


def _admin(port: int, path: str, method: str = "GET") -> bool:
    request = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method=method)
    try:
        with urllib.request.urlopen(request, timeout=WEAVER_STOP_TIMEOUT_SECONDS if method == "POST" else 2):
            return True
    except (OSError, urllib.error.URLError, TimeoutError):
        return False


def _wait_for_weaver(admin_port: int, proc: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + WEAVER_STARTUP_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"weaver live-check exited during startup (exit {proc.returncode})")
        if _admin(admin_port, "/health"):
            return
        time.sleep(1)
    raise RuntimeError(f"weaver live-check was not ready after {WEAVER_STARTUP_TIMEOUT_SECONDS}s")


def _stop_weaver(admin_port: int, proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is None and _admin(admin_port, "/stop", "POST"):
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            _admin(admin_port, "/shutdown", "POST")  # Weaver >= 0.27 waits for this after /stop
    try:
        proc.wait(timeout=WEAVER_STOP_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        proc.terminate()
        proc.wait()


def _scenario_env(spec: PackageSpec, scenario: ScenarioSpec, grpc_port: int) -> dict[str, str]:
    """Declared env, then the real environment, then what this run started -- each wins over the one before."""
    inherited = {
        k: v for k, v in os.environ.items() if k not in ("VIRTUAL_ENV", "PYTHONHOME", "PYTHONPATH", *_OTLP_SIGNAL_ENV)
    }
    return {
        **spec.env,
        **scenario.env,
        **inherited,
        "OTEL_EXPORTER_OTLP_ENDPOINT": f"http://127.0.0.1:{grpc_port}",
        "OTEL_EXPORTER_OTLP_PROTOCOL": "grpc",
    }


def _live_check(spec: PackageSpec, scenario: ScenarioSpec, report_file: Path) -> int:
    """Run one scenario under its own live-check; write weaver's report; return the scenario's exit code."""
    grpc_port, admin_port = _free_ports(2)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    # Under the repository root, which is all a containerized weaver can see.
    with tempfile.TemporaryDirectory(dir=CACHE_DIR, prefix="live-check-") as tmp:
        command = weaver_command(
            [
                "registry", "live-check", "-r", "./model", "--v2", "--include-unreferenced",
                "--format", "json", "--output", _relative(Path(tmp)),
                "--otlp-grpc-address", "0.0.0.0" if in_container() else "127.0.0.1",
                "--otlp-grpc-port", str(grpc_port), "--admin-port", str(admin_port),
                "--inactivity-timeout", str(WEAVER_INACTIVITY_TIMEOUT_SECONDS),
            ],
            ports=(grpc_port, admin_port),
        )  # fmt: skip
        # Weaver's own diagnostics (definition/2 not yet stable, ...) only matter when it fails.
        log = (Path(tmp) / "weaver.log").open("w+", encoding="utf-8")
        proc = subprocess.Popen(command, cwd=SEMCONV_ROOT, stdout=log, stderr=subprocess.STDOUT)
        try:
            _wait_for_weaver(admin_port, proc)
            try:
                exit_code = subprocess.run(
                    scenario.run,
                    shell=True,
                    cwd=spec.directory,
                    env=_scenario_env(spec, scenario, grpc_port),
                    timeout=SCENARIO_TIMEOUT_SECONDS,
                    check=False,
                ).returncode
            except subprocess.TimeoutExpired:
                logger.error("%s: scenario timed out after %ss", scenario.name, SCENARIO_TIMEOUT_SECONDS)
                exit_code = 124
        except RuntimeError:
            log.seek(0)
            logger.error("weaver live-check output:\n%s", log.read())
            raise
        finally:
            _stop_weaver(admin_port, proc)
            log.close()
        produced = Path(tmp) / "live_check.json"
        if not produced.is_file():
            output = (Path(tmp) / "weaver.log").read_text(encoding="utf-8")
            raise RuntimeError(f"weaver live-check wrote no report for {scenario.name}:\n{output}")
        report_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(produced), report_file)
    return exit_code


def run(directory: Path, *, report_only: bool, extra_args: list[str] | None = None) -> int:
    """Run one conformance directory's scenarios; return the run's exit code."""
    parser = argparse.ArgumentParser(prog="run-scenario <library>")
    parser.add_argument("--scenario", action="append", help="Run only this scenario (repeatable)")
    args = parser.parse_args(extra_args or [])
    spec = load_spec(directory)
    selected = args.scenario or list(spec.scenarios)
    unknown = sorted(set(selected) - set(spec.scenarios))
    if unknown:
        raise RuntimeError(f"Unknown scenario(s) {unknown}; {directory.name} declares {sorted(spec.scenarios)}")

    model = json.loads(coverage_model().read_text(encoding="utf-8"))
    report_dir = directory / REPORT_DIR
    exit_code = 0
    for name in selected:
        scenario = spec.scenarios[name]
        report_file = report_dir / f"{name}.json"
        scenario_exit = _live_check(spec, scenario, report_file)
        observed = observe(json.loads(report_file.read_text(encoding="utf-8")), model)
        failures, violations = check(scenario, spec, observed)
        if scenario_exit != 0:
            failures.insert(0, f"scenario exited with code {scenario_exit}")
        marker = "✖" if failures else ("▲" if violations else "✔")
        print(f"{marker} {directory.name}/{name}")
        for line in failures + violations:
            print(f"    {line}")
        if failures or (violations and not report_only):
            exit_code = 1

    # The data file covers the whole directory, so only a complete run rewrites it.
    if set(selected) == set(spec.scenarios):
        observed = Observed()
        for name in spec.scenarios:
            observe(json.loads((report_dir / f"{name}.json").read_text(encoding="utf-8")), model, observed)
        data_file = directory / "data.json"
        data_file.write_text(json.dumps(reduce(observed, model), indent=2) + "\n", encoding="utf-8")
        logger.info("Updated %s", data_file)
    return exit_code
