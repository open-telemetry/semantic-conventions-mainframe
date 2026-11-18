#!/usr/bin/env bash
# Look at the HMC reference scenario's telemetry in the local reference stack
# (OpenTelemetry Collector -> Prometheus -> Grafana, see stack/README.md).
#
#   reference/demo.sh start                    # materialize the upstream registry, start the stack
#   reference/demo.sh emit-once                # send one collection of the HMC scenario
#   reference/demo.sh emit-continuous [secs]   # send a collection every secs (default 60) until Ctrl-C
#   reference/demo.sh stop                     # stop and remove the stack
#
# Requires uv, make, and podman (with podman-compose) or docker. Set
# OTLP_ENDPOINT to send somewhere other than the stack's collector.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SCENARIO_DIR="${SCRIPT_DIR}/scenarios/hmc"
OTLP_ENDPOINT="${OTLP_ENDPOINT:-http://localhost:4317}"

usage() {
    sed -n '2,11s/^# \{0,1\}//p' "${BASH_SOURCE[0]}" >&2
    exit 1
}

run_make() {
    make -C "${REPO_ROOT}" --no-print-directory "$@"
}

# The model depends on the filtered upstream semantic conventions, which the
# emitter needs to resolve it. A no-op once they are in place.
materialize_upstream() {
    run_make filter-upstream
}

collector_listening() {
    local hostport="${OTLP_ENDPOINT#*://}"
    hostport="${hostport%%/*}"
    (exec 3<>"/dev/tcp/${hostport%:*}/${hostport##*:}") 2>/dev/null
}

require_collector() {
    if ! collector_listening; then
        echo "Error: nothing is listening on ${OTLP_ENDPOINT}; start the stack first:" >&2
        echo "  ${SCRIPT_DIR}/demo.sh start" >&2
        exit 1
    fi
}

emit() {
    if ! command -v uv >/dev/null 2>&1; then
        echo "Error: uv is required (https://docs.astral.sh/uv/)." >&2
        exit 1
    fi
    materialize_upstream
    require_collector
    (cd "${SCRIPT_DIR}" && uv run --frozen python -m semconv_mainframe.emitter \
        --topology "${SCENARIO_DIR}/topology.yaml" \
        --workload "${SCENARIO_DIR}/workload.yaml" \
        --endpoint "${OTLP_ENDPOINT}" "$@")
}

case "${1:-}" in
    start)
        materialize_upstream
        run_make stack-up
        echo "Waiting for the collector on ${OTLP_ENDPOINT}..."
        for _ in $(seq 1 60); do
            collector_listening && break
            sleep 1
        done
        require_collector
        echo "Stack is running. Send the HMC scenario with:"
        echo "  ${SCRIPT_DIR}/demo.sh emit-once"
        ;;
    stop)
        run_make stack-down
        ;;
    emit-once)
        emit --cycles 1
        ;;
    emit-continuous)
        emit --cycles 0 --interval "${2:-60}"
        ;;
    *)
        usage
        ;;
esac
