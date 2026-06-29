# Semantic Conventions Mainframe Reference Implementations

Validates [OpenTelemetry Semantic Conventions for Mainframe](https://opentelemetry.io/docs/specs/semconv/mainframe/)
against representative, synthetic telemetry, showing entities and attributes supported for supported feature of the mainframe, software and infrastructure.

Each feature under [scenarios/](scenarios/) contains a small reference implementation
(`scenario.py`) that exercises the SDK against a deterministic local mock server
and emits OpenTelemetry spans, metrics, and logs. The tooling validates the
captured telemetry against the semantic conventions in [../model/](../model/)
using [OTel Weaver](https://github.com/open-telemetry/weaver) and writes the
per-library results to `scenarios/<library>/data.json`, which feed the status
reports below.

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to run scenarios and add new libraries.

## Reports

Generated from committed `scenarios/*/data.json` files. Do not edit this section by hand.
Run `uv run update-reports` to regenerate.

<!-- status:begin -->
### Spans

TO BE DONE

| Span | Libraries |
| --- | --- |

### Metrics

### Events

TO BE DONE

| Event | Libraries |
<!-- status:end -->
