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
    emitter/             # Model-driven synthetic emitter used by the HMC scenario
tests/                   # Unit tests for the tooling
scenarios/
  <scenario>/            # Reference scenarios
reports/                 # Generated per-signal report pages
stack/                   # Local Collector, Prometheus and Grafana (see stack/README.md)
demo.sh                  # Sends the HMC scenario to the stack
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

## The HMC scenario and the synthetic emitter

[scenarios/hmc/](scenarios/hmc/) stands for an IBM Z HMC-based collector
observing one CPC. Its `scenario.py` drives the emitter in
[src/semconv_mainframe/emitter/](src/semconv_mainframe/emitter/) with two
files of its own:

- [`topology.yaml`](scenarios/hmc/topology.yaml) lists the entities, nested
  as they are on the machine. Each node becomes one OTLP resource carrying
  exactly the attributes its entity declares; a node takes a declared
  attribute it does not set from its nearest ancestor (the CPC's
  `virtualization.platform.id`, say). Identities follow the model: the CPC is
  `<machine type>-<serial>` (`3931-45A01`, also `host.id`), partitions are
  identified by LPAR name, adapters by PCHID, channels by `CSS.CHPID`. Nodes
  are checked against the registry: unknown entities or attributes, invalid
  enum values and incomplete or duplicate identities are errors.
- [`workload.yaml`](scenarios/hmc/workload.yaml) says which values each metric
  takes. The first rule matching a metric definition (by `metric` regex on its
  id or name, `instrument`, `entity`) decides; `unit` is required and must equal
  the unit the model declares, so byte quantities are emitted in bytes (`By`)
  and ratios in `1`. A metric no rule matches is an error. A counter needs a
  `counter` generator, so it stays monotonic.

The emitter reads the registry as `weaver registry resolve --v2` resolves
`model/` (cached under `.cache/`), so upstream signals arrive resolved whatever
file format upstream defines them in, and every refinement is emitted with the
attributes of the signal it refines. Definitions sharing a wire name on one
entity -- a base metric and its refinement -- are emitted as one metric with
each definition's series. `scenario.py` fails when a metric definition
associated with an entity of the topology would emit no data point, and
[tests/test_hmc_scenario.py](tests/test_hmc_scenario.py) asserts that every
metric and every metric refinement in the model is emitted.

When the model changes:

1. Add a topology node for a new entity, or a workload rule for a new metric
   (`uv run --extra dev pytest tests/test_hmc_scenario.py` says what is missing).
2. Update the `metrics:` list in `scenarios/hmc/conformance.yaml` if a wire
   name was added or removed.
3. Run `uv run run-scenario hmc --strict` and `uv run update-reports`, and
   commit `data.json`, `README.md` and `reports/`.

## Demo

[demo.sh](demo.sh) runs the same emitter against the local reference stack in
[stack/](stack/) instead of Weaver: `start` materializes the filtered upstream
registry (`make filter-upstream`) and runs `make stack-up`; `emit-once` and
`emit-continuous [secs]` send the HMC scenario to `OTLP_ENDPOINT` (default
`http://localhost:4317`); `stop` runs `make stack-down`. The emitter can also be
run directly:

```bash
uv run python -m semconv_mainframe.emitter \
    --topology scenarios/hmc/topology.yaml --workload scenarios/hmc/workload.yaml \
    --endpoint http://localhost:4317 --cycles 1
```

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
