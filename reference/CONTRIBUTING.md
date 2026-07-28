# Contributing to the Reference Stack

This directory contains the podman-compose observability stack that validates
the Mainframe semantic conventions end-to-end. There is no Python source code
here — Weaver itself emits the telemetry.

If you are changing the semantic conventions themselves under `model/` or
`docs/`, use the repository-level guide in [../CONTRIBUTING.md](../CONTRIBUTING.md).

## Adding or updating a dashboard

1. Edit or create a dashboard JSON under [`../dashboards/mainframe/`](../dashboards/mainframe/).
2. Dashboards are provisioned from that directory at stack startup. Run
   `make stack-down && make stack-up` to reload, or use Grafana's reload API.
3. Ensure the datasource variable in the JSON is `${DS_PROMETHEUS}` — that is
   the uid auto-provisioned by `grafana/provisioning/datasources/prometheus.yaml`.

## Changing stack image versions

Image versions are pinned in [`../versions.env`](../versions.env) under the
`# --- Reference observability stack image versions ---` section.
Renovate opens PRs to bump them automatically; you can also edit by hand.

## Testing locally

```bash
make demo          # start stack + emit + print URL (one command)
make stack-down    # stop when done
```

For a clean restart (including wiping stored Prometheus and Grafana data):

```bash
make stack-down
podman volume rm mainframe-otelcol-data mainframe-prometheus-data mainframe-grafana-data 2>/dev/null; true
make demo
```
