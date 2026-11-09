# Repository conventions

These instructions guide both human contributors and AI assistants
(including GitHub's Copilot code reviewer) working in this repository.

## Repository overview

This repo defines the OpenTelemetry semantic conventions for mainframes
(IBM Z and LinuxONE) and the cross-platform virtualization conventions they
build on. Changes flow through several coupled surfaces:

- `model/<namespace>/*.yaml` — source of truth for attributes, entities,
  metrics, spans and events, in Weaver's `definition/2` format. Namespaces
  are `mainframe`, `virtualization` and `zos`. Upstream OpenTelemetry
  conventions are reused or refined (`entity_refinements`,
  `metric_refinements`) rather than duplicated.
- `docs/registry/` — generated from the model via Weaver
  (`make generate-all`). Generated registry pages should not be hand-edited.
- `docs/*.md` — hand-written background and mapping documents.
- `reference/` — reference implementations that generate representative
  synthetic telemetry for the conventions.

## PR scope

- Keep PRs small and focused. Do not mix unrelated convention changes; see
  the "Keep PRs small" guidance in `CONTRIBUTING.md`.
- Non-editorial convention changes need a Towncrier fragment under `changelog.d/`.
  Editorial-only changes (typos, rewording, tooling) do not need one.
- Convention changes under `model/` need regenerated `docs/registry/` pages
  (`make generate-all`) and must pass `make check-policies`.

## Code style

- Prefer simple syntax over dense or clever equivalents.
- Do not use `try`/`except` to swallow exceptions. Errors should bubble up
  and fail loudly unless there is a clear reason to handle them.
- Use explicit, descriptive names over compact ones.

## What not to flag in review

- Generated files under `docs/registry/`
  — review the model changes that produced them instead.
