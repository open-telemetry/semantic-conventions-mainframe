#!/usr/bin/env bash
# =============================================================================
# IBM Z Mainframe Semantic Conventions Reference Stack Demo Runner
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.yaml"

# Source version pins from versions.env so Renovate-managed image tags are
# picked up even when invoking demo.sh directly (without going through Make).
if [[ -f "${REPO_ROOT}/versions.env" ]]; then
    # shellcheck disable=SC1091
    set -a
    # Strip Make variable syntax (e.g. WEAVER_PACKAGES_REF=$(POLICY_REPO_REF))
    # and export only plain key=value lines.
    while IFS='=' read -r key value; do
        [[ "$key" =~ ^[A-Z_][A-Z0-9_]*$ ]] && [[ ! "$value" =~ ^\$\( ]] && export "${key}=${value}"
    done < <(grep -v '^#' "${REPO_ROOT}/versions.env" | grep '=')
    set +a
fi
SIMULATOR_SCRIPT="${SCRIPT_DIR}/otel_semconv_sim.py"
SIMULATOR_CONFIG="${SCRIPT_DIR}/simulator_config.yaml"

# Check that the OTLP endpoint the simulator exports to is actually listening.
# Without this the simulator runs to completion, fails on every export and exits
# 1 with a bare "Connection refused", which reads like a simulator bug rather
# than a stack that was never started.
require_stack() {
    local endpoint host port
    endpoint="$(sed -n 's|.*http_endpoint:[[:space:]]*"\{0,1\}\(http://[^"]*\)"\{0,1\}.*|\1|p' \
        "${SIMULATOR_CONFIG}" | head -1)"
    endpoint="${endpoint:-http://localhost:4318}"
    host="$(echo "${endpoint}" | sed -E 's|https?://||; s|:.*||')"
    port="$(echo "${endpoint}" | sed -E 's|.*:([0-9]+).*|\1|')"
    if ! (exec 3<>"/dev/tcp/${host}/${port}") 2>/dev/null; then
        echo "Error: nothing is listening on ${endpoint}." >&2
        echo "The simulator exports over OTLP, so the collector stack must be running:" >&2
        echo "  ${SCRIPT_DIR}/demo.sh start" >&2
        exit 1
    fi
}

# Run the simulator through the project environment.
#
# The simulator needs PyYAML, which is declared in reference/pyproject.toml and
# pinned in reference/uv.lock but is usually absent from the bare system
# interpreter. Prefer `uv run`, which resolves that environment; fall back to
# python3 only when it can already import yaml, and otherwise say exactly what
# to install rather than failing inside the simulator.
run_simulator() {
    if command -v uv >/dev/null 2>&1; then
        uv run --project "${SCRIPT_DIR}" --quiet python "${SIMULATOR_SCRIPT}" "$@"
    elif python3 -c "import yaml" >/dev/null 2>&1; then
        python3 "${SIMULATOR_SCRIPT}" "$@"
    else
        echo "Error: the simulator requires PyYAML, which is not available." >&2
        echo "Install uv (https://docs.astral.sh/uv/) and re-run, or install the" >&2
        echo "dependencies into your interpreter:" >&2
        echo "  python3 -m pip install -r <(echo pyyaml)" >&2
        echo "  # or: cd ${SCRIPT_DIR} && uv sync" >&2
        exit 1
    fi
}

# Container compose binary detection
if command -v podman-compose >/dev/null 2>&1; then
    COMPOSE_CMD="podman-compose"
elif command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
else
    echo "Error: Neither podman-compose nor docker compose was found." >&2
    exit 1
fi

case "${1:-}" in
    start)
        echo "================================================================="
        echo "Starting Mainframe Observability Reference Stack..."
        echo "================================================================="
        ${COMPOSE_CMD} -f "${COMPOSE_FILE}" up -d

        echo "Waiting for OpenTelemetry Collector to be ready on port 4318..."
        collector_ready=0
        for i in $(seq 1 30); do
            if nc -z localhost 4318 2>/dev/null || curl -s http://localhost:4318 >/dev/null 2>&1; then
                collector_ready=1
                break
            fi
            sleep 1
        done

        if [ "${collector_ready}" -eq 0 ]; then
            echo "ERROR: OpenTelemetry Collector did not become ready within 30 seconds." >&2
            echo "Check container logs: ${COMPOSE_CMD} -f \"${COMPOSE_FILE}\" logs otel-collector" >&2
            exit 1
        fi

        echo ""
        echo "Stack is running!"
        echo " - Grafana Dashboard : http://localhost:3000"
        echo " - Prometheus Targets: http://localhost:9090/targets"
        echo " - OTLP HTTP Endpoint: http://localhost:4318"
        echo " - OTLP gRPC Endpoint: localhost:4317"
        echo ""
        echo "To emit continuous realistic IBM Z telemetry into the stack, run:"
        echo "  ${SCRIPT_DIR}/demo.sh emit-continuous"
        ;;

    stop)
        echo "Stopping Reference Observability Stack..."
        ${COMPOSE_CMD} -f "${COMPOSE_FILE}" down
        echo "Stack stopped."
        ;;

    emit-once)
        echo "Emitting a single high-fidelity telemetry batch to the local stack..."
        # The upstream OTel semconv registry stubs must be materialized so that
        # metric_refinements: ref: entries (system.*, hw.*, container.*) can be
        # resolved into MetricDef objects.  Without them the simulator silently
        # skips all upstream-backed signals and exits successfully.
        UPSTREAM_DIR="${REPO_ROOT}/.build/sc-upstream-filtered"
        if [[ ! -d "${UPSTREAM_DIR}" ]]; then
            echo "ERROR: upstream semconv registry not materialized." >&2
            echo "Run 'make filter-upstream' from the repository root first:" >&2
            echo "  cd $(cd "${REPO_ROOT}" && pwd) && make filter-upstream" >&2
            exit 1
        fi
        require_stack
        run_simulator --config "${SIMULATOR_CONFIG}" --once
        ;;

    emit-continuous)
        INTERVAL="${2:-10}"
        echo "Starting continuous telemetry simulation loop (every ${INTERVAL}s)..."
        require_stack
        run_simulator --config "${SIMULATOR_CONFIG}" --interval "${INTERVAL}"
        ;;

    weaver-emit)
        echo "Invoking Weaver to emit sample contract validation signals..."
        make -C "${REPO_ROOT}" stack-emit
        ;;

    *)
        echo "Usage: $0 {start|stop|emit-once|emit-continuous [interval_sec]|weaver-emit}"
        exit 1
        ;;
esac
