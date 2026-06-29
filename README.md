# OpenTelemetry Semantic Conventions Mainframe

Semantic Conventions for Mainframes, including spans, metrics, and events for IBM Z and LinuxONE software and infrastructure, and vendor-specific conventions.

This repository extends the [OpenTelemetry Semantic Conventions](https://github.com/open-telemetry/semantic-conventions)
with Mainframe-specific conventions, using
[Weaver](https://github.com/open-telemetry/weaver) to manage dependencies
on the core semantic conventions.

## Schema URL

TODO

## Read the docs

The human-readable version of the semantic conventions resides in the
[docs](docs/) folder. Major parts of these Markdown documents are generated
from the YAML definitions located in the [model](model/) folder.

Reference implementations and their tooling live under [reference](reference/). Real mainframe access is not expected for contributors or CI, reference implementations should generate representative synthetic telemetry that exercises the semantic conventions.

For the reference compliance matrix and per-signal support reports, see
[reference/README.md](reference/README.md).
For contribution guidance specific to the reference implementation, see
[reference/CONTRIBUTING.md](reference/CONTRIBUTING.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).