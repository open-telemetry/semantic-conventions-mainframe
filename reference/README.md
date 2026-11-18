# Semantic Conventions Mainframe Reference Implementations

Validates OpenTelemetry Semantic Conventions for Mainframe <!-- TODO [OpenTelemetry Semantic Conventions for Mainframe](https://opentelemetry.io/docs/specs/semconv/mainframe/) -->
against representative, synthetic telemetry, showing which entities, metrics
and attributes each scenario of the mainframe, its software and infrastructure
supports.

Each scenario under `scenarios/<scenario>/` contains a small reference
implementation (`scenario.py`) that emits OpenTelemetry telemetry, plus a
`conformance.yaml` saying how to run it and what it must produce. The tooling
runs each scenario against [OTel Weaver](https://github.com/open-telemetry/weaver)
live-check, validates the captured telemetry against the semantic conventions
in [../model/](../model/), and writes the per-scenario results to
`scenarios/<scenario>/data.json`, which feed the status reports below.

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to run scenarios and add new ones.

## Reports

Generated from committed `scenarios/*/data.json` files. Do not edit this section by hand.
Run `uv run update-reports` (or `make generate-reference-reports` from the
repository root) to regenerate. Every signal [../model/](../model/) declares is
listed; metric refinements are listed by the entities they are refined for.

<!-- status:begin -->
### Entities

| Entity | Libraries |
| --- | --- |
| zos.software | (none) |
<!-- status:end -->
