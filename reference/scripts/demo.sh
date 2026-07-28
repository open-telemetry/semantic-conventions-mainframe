#!/usr/bin/env bash
#
# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0
#
# Run the mainframe semantic conventions reference demo.
#
# Starts the local observability stack (OTel Collector + Prometheus + Grafana),
# waits for the collector to be ready, emits one round of synthetic telemetry
# for all 77 mainframe metrics via `weaver registry emit`, and prints the
# Grafana URL.
#
# Usage:
#   ./scripts/demo.sh              # run from the repository root
#   ./scripts/demo.sh --down       # tear down the stack and exit
#
# Prerequisites:
#   - podman >= 5.0  (https://podman.io)
#   - podman-compose >= 1.0  (uv tool install podman-compose)
#
# The script delegates to Makefile targets so all version pins in versions.env
# and the podman-compose / Weaver configuration remain the single source of
# truth.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Prepend the uv tool bin directory so tools installed with
# `uv tool install` (e.g. podman-compose) are found even when
# ~/.local/bin is not on the caller's PATH.
UV_TOOL_BIN="$(uv tool dir --bin 2>/dev/null || true)"
if [[ -n "$UV_TOOL_BIN" ]]; then
    PATH="$UV_TOOL_BIN:$PATH"
fi

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

die() { echo "❌  $*" >&2; exit 1; }

require_cmd() {
    command -v "$1" >/dev/null 2>&1 || die "'$1' not found. $2"
}

# ---------------------------------------------------------------------------
# Prerequisites
# ---------------------------------------------------------------------------

require_cmd podman \
    "Install podman from https://podman.io"
require_cmd podman-compose \
    "Install with: uv tool install podman-compose  (then add ~/.local/bin to PATH)"
require_cmd make \
    "GNU Make is required."

# ---------------------------------------------------------------------------
# Argument handling
# ---------------------------------------------------------------------------

if [[ "${1:-}" == "--down" ]]; then
    echo "Stopping the reference stack..."
    make -C "$REPO_ROOT" stack-down
    echo "✔ Stack stopped."
    exit 0
fi

if [[ $# -gt 0 ]]; then
    die "Unknown argument: $1. Usage: $0 [--down]"
fi

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

cd "$REPO_ROOT"
make demo
