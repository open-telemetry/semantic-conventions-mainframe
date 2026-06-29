# Contributing to the Reference Scenarios

This directory contains the runnable reference scenarios and the tooling
used to validate them against the Mainframe semantic conventions.

If you are changing the semantic conventions themselves under `model/` or
`docs/`, use the repository-level guide in [../CONTRIBUTING.md](../CONTRIBUTING.md).

<!-- TODO: Remove comment, once reference implementation is decided 

## Structure

```text
pyproject.toml           # Tooling project metadata
src/
  semconv_mainframe/     # Shared framework, CLI modules, and mock server
scenarios/
  <feature>/             # Reference scenarios
```

Within each scenario directory:

- `scenario.py` — SDK invocation + manual OTel spans
- `pyproject.toml` — Dependencies
- `uv.lock` — Locked transitive dependency graph (committed)
- `data.json` — Committed results

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (uv will fetch the Python 3.12 interpreter declared in `pyproject.toml` on first run).

Run the commands below from this `reference/` directory.

## Running scenarios

First-time setup creates `.venv` and installs the tooling:

```bash
uv sync
```

Run a single feature, or all libraries:

```bash
uv run run-scenario openai          # one feature
uv run run-scenario --all           # all libraries
uv run run-scenario --all --keep-going   # continue through failures, report at end
```

`uv run run-scenario <feature>` runs the selected scenario under
[scenarios/](scenarios/) against a local mock LLM server, validates the
emitted telemetry, and writes the results that feed the checked-in reports.

## Linting

Lint and format the Python code under `src/semconv_mainframe/` and `scenarios/`:

```bash
uv tool run --from ruff ruff check --fix src/semconv_mainframe scenarios
uv tool run --from ruff ruff format src/semconv_mainframe scenarios
```

## Updating reports

Regenerate the checked-in status section in `README.md` after updating committed
`data.json` files:

```bash
uv run update-reports
```

## Contribution expectations

- Keep reference coverage honest. Only emit spans and attributes that the
  feature or reference code can actually produce.
- Prefer focused updates to the affected feature under `scenarios/<feature>/`.
- After regenerating `scenarios/*/data.json`, run `uv run update-reports` and
  commit both alongside your change.

If a feature emits unrelated native telemetry that obscures the intended
validation surface, suppress that feature-owned telemetry in the reference
scenario rather than changing the semantic conventions to match it.

## Adding or updating a feature

Reference scenarios are both validation inputs and examples for instrumentation
authors, so keep them minimal and readable.

When adding a new reference scenario:

1. Create `scenarios/<feature>/scenario.py`.
2. Create `scenarios/<feature>/pyproject.toml` declaring the SDK dependencies plus
   `mainframe-reference-shared` (sourced from the shared project at `shared/`).
   The OTel SDK pin is provided transitively by `mainframe-reference-shared`; do
   not re-declare it here unless the feature needs a non-default version.

   ```toml
   [project]
   name = "<feature>-reference-test"
   version = "0"
   requires-python = ">=3.12"
   dependencies = [
       "<sdk>==<pinned-version>",
       "mainframe-reference-shared",
   ]

   [tool.uv.sources]
   mainframe-reference-shared = { path = "../../shared", editable = true }

   [tool.uv]
   package = false
   ```

   If the SDK under test requires a specific OTel version that differs
   from the default pin in [shared/pyproject.toml](./shared/pyproject.toml),
   add `override-dependencies` to the existing `[tool.uv]` table:

   ```toml
   [tool.uv]
   package = false
   override-dependencies = [
       "opentelemetry-api==<required>",
       "opentelemetry-sdk==<required>",
       "opentelemetry-exporter-otlp-proto-grpc==<required>",
   ]
   ```

3. Run `uv lock` inside `scenarios/<feature>/` to generate the committed
   `uv.lock`. Re-run it whenever you change dependencies; `run-scenario` uses
   `uv sync --frozen` and will fail if the lockfile is stale.
4. Run `uv run run-scenario <feature>` to generate `scenarios/<feature>/data.json`.
5. Regenerate `README.md` with `uv run update-reports`.

-->