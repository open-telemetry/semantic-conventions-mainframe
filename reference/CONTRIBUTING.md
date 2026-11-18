# Contributing to the Reference Scenarios

This directory contains the runnable reference scenarios and the tooling
used to validate them against the Mainframe semantic conventions.

If you are changing the semantic conventions themselves under `model/` or
`docs/`, use the repository-level guide in [../CONTRIBUTING.md](../CONTRIBUTING.md).

## Structure

```text
pyproject.toml           # Tooling project metadata
uv.lock                  # Locked tooling dependencies (committed)
src/
  semconv_mainframe/     # Scenario discovery, live-check runner, report generation
tests/                   # Unit tests for the tooling
scenarios/
  <scenario>/            # Reference scenarios
reports/                 # Generated per-signal report pages
```

Within each scenario directory:

- `conformance.yaml` — How to run the scenario and what it must produce
- `scenario.py` — The reference implementation that emits the telemetry
- `data.json` — Committed results

The tooling is a port of the reference framework of
[semantic-conventions-genai](https://github.com/open-telemetry/semantic-conventions-genai/tree/e6658f14c9d9ea0760825f029cb82e7673f48fab/reference)
(`run-scenario`, `update-reports`, `conformance.yaml`, `data.json`).

## The live-check runner

GenAI runs its scenarios under the shared
[conformance runner](https://github.com/open-telemetry/semantic-conventions-conformance),
which has no mainframe domain yet. `run-scenario` therefore runs the subset of
it this repository needs ([`conformance.py`](src/semconv_mainframe/conformance.py)):
for every scenario in a `conformance.yaml` it starts
`weaver registry live-check` against the working tree's `model/`, runs the
scenario's `run` command with `OTEL_EXPORTER_OTLP_ENDPOINT` pointing at it
(OTLP/gRPC), and reduces Weaver's report into `data.json` in the shape the
shared runner writes. Raw Weaver reports are left under
`scenarios/<scenario>/output/weaver-reports/`.

`conformance.yaml` supports these keys of the shared runner:

```yaml
runner: mainframe-conformance        # optional; the only accepted value
instrumented_library: <scenario>     # what the reports list the scenario as
instrumentation_library: reference
env: {NAME: value}                   # scenario environment (the real one wins)
scenarios:
  <name>:
    run: <shell command, run in the scenario directory>
    metrics: [<metric name>, ...]    # optional; checked exactly
    events: [<event name>, ...]      # optional; checked exactly
    expected_violations:             # Weaver violations this scenario must report
      - {id: <finding id>, context: {...}, reason: <why>}
expected_violations: [...]           # suppress findings for every scenario
```

Spans, mock servers and `setup` commands are not supported yet. A metric
refinement is recorded in `data.json` under its own id, attributed by the
entity identity on the resource that carried the data point.

Weaver is the release pinned in [../versions.env](../versions.env): the
`weaver` on `PATH` if it is that version (CI installs it), otherwise the
`otel/weaver` image through podman or docker, as the Makefile runs it.
The model depends on the filtered upstream registry, so run
`make filter-upstream` from the repository root once before the first run.

Violations are reported as warnings, not failures. Pass `--strict` to fail on
them, as CI does. A scenario that crashes or misses what its
`conformance.yaml` declares fails either way.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (uv will fetch the Python 3.12 interpreter declared in `pyproject.toml` on first run).
- Weaver, or podman / docker (see above).

Run the commands below from this `reference/` directory.

## Running scenarios

First-time setup creates `.venv` and installs the tooling:

```bash
uv sync
```

Run a single scenario, or all of them:

```bash
uv run run-scenario <scenario>          # one scenario directory
uv run run-scenario <scenario> --scenario <name>   # one scenario of it (data.json is kept)
uv run run-scenario --all               # all scenario directories
uv run run-scenario --all --keep-going  # continue through failures, report at end
```

## Linting and tests

Lint and format the Python code in this directory (`src/`, `scenarios/`,
`tests/`), and run the unit tests:

```bash
uv tool run --from ruff ruff check --fix
uv tool run --from ruff ruff format
uv run --extra dev pytest
```

## Updating reports

Regenerate the checked-in status section in `README.md` and the pages under
`reports/` after updating committed `data.json` files or `model/`:

```bash
uv run update-reports
```

`make generate-reference-reports` (part of `make generate-all`) runs the same
from the repository root.

## Contribution expectations

- Keep reference coverage honest. Only emit signals and attributes that the
  data source the scenario stands for can actually produce.
- Prefer focused updates to the affected scenario under `scenarios/<scenario>/`.
- After regenerating `scenarios/*/data.json`, run `uv run update-reports` and
  commit both alongside your change.

## Adding a scenario

Reference scenarios are both validation inputs and examples for instrumentation
authors, so keep them minimal and readable.

1. Create `scenarios/<scenario>/scenario.py`. It exports OTLP/gRPC to
   `OTEL_EXPORTER_OTLP_ENDPOINT` and exits non-zero when it cannot.
2. Create `scenarios/<scenario>/conformance.yaml` (see above) with
   `run: uv run --frozen --project ../.. python scenario.py` to run it in
   this project's environment.
3. Run `uv run run-scenario <scenario>` to generate `scenarios/<scenario>/data.json`.
4. Regenerate `README.md` and `reports/` with `uv run update-reports`.
