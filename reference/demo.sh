#!/usr/bin/env bash
# =============================================================================
# IBM Z Mainframe Semantic Conventions Reference Stack Demo Runner
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.yaml"
SIMULATOR_SCRIPT="${SCRIPT_DIR}/otel_semconv_sim.py"
SIMULATOR_CONFIG="${SCRIPT_DIR}/simulator_config.yaml"

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
        for i in $(seq 1 30); do
            if nc -z localhost 4318 2>/dev/null || curl -s http://localhost:4318 >/dev/null 2>&1; then
                break
            fi
            sleep 1
        done

        echo ""
        echo "Stack is running!"
        echo " - Grafana Dashboard : http://localhost:3000"
        echo " - Prometheus Targets: http://localhost:9090/targets"
        echo " - OTLP HTTP Endpoint: http://localhost:4318"
        echo " - OTLP gRPC Endpoint: localhost:4317"
        echo ""
        echo "To emit continuous realistic IBM Z telemetry into the stack, run:"
        echo "  python3 ${SIMULATOR_SCRIPT} --config ${SIMULATOR_CONFIG}"
        ;;

    stop)
        echo "Stopping Reference Observability Stack..."
        ${COMPOSE_CMD} -f "${COMPOSE_FILE}" down
        echo "Stack stopped."
        ;;

    emit-once)
        echo "Emitting a single high-fidelity telemetry batch to the local stack..."
        python3 "${SIMULATOR_SCRIPT}" --config "${SIMULATOR_CONFIG}" --once
        ;;

    emit-continuous)
        INTERVAL="${2:-10}"
        echo "Starting continuous telemetry simulation loop (every ${INTERVAL}s)..."
        python3 "${SIMULATOR_SCRIPT}" --config "${SIMULATOR_CONFIG}" --interval "${INTERVAL}"
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
