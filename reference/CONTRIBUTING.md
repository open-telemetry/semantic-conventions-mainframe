# Contributing to the Reference Stack

This directory contains the end-to-end observability stack that validates the
Mainframe OpenTelemetry Semantic Conventions defined in `../model/`. It is
composed of a simulator engine and a lightweight container stack.

---

## Table of contents

1. [How it works](#1-how-it-works)
2. [File map](#2-file-map)
3. [Simulator architecture](#3-simulator-architecture)
   - [Registry loading](#31-registry-loading)
   - [Topology graph](#32-topology-graph)
   - [Workload engine](#33-workload-engine)
   - [OTLP emission](#34-otlp-emission)
4. [Configuration reference](#4-configuration-reference)
   - [simulator_config.yaml](#41-simulator_configyaml)
   - [workload_profile.yaml](#42-workload_profileyaml)
5. [Common contribution tasks](#5-common-contribution-tasks)
   - [Add a new entity to the topology](#51-add-a-new-entity-to-the-topology)
   - [Add a namespace from a new model directory](#52-add-a-namespace-from-a-new-model-directory)
   - [Add or tune a workload rule](#53-add-or-tune-a-workload-rule)
   - [Extend the simulator engine](#54-extend-the-simulator-engine)
   - [Add a new container service](#55-add-a-new-container-service)
6. [Invariants and constraints](#6-invariants-and-constraints)
7. [Validating changes](#7-validating-changes)
8. [Upstream registry and metric refinements](#8-upstream-registry-and-metric-refinements)
9. [Name drift between spec and model](#9-name-drift-between-spec-and-model)

---

## 1. How it works

The simulator is **100% domain-agnostic**. It contains no hardcoded metric
names, entity types, or IBM-specific logic. Every signal it emits is derived
entirely from the YAML files in `../model/`.

At startup the simulator:

1. Loads the upstream OTel Semantic Conventions registry from
   `../.build/sc-upstream-filtered/` (v1 `groups:` format) as *stubs* —
   instrument, unit, and brief for every upstream metric.
2. Loads local v2 `definition/2` YAML files from each path listed under
   `spec.registry.paths` in `simulator_config.yaml`.
3. Resolves all `metric_refinements: ref:` entries: if the referenced metric
   name exists in the upstream stubs, a `MetricDef` is synthesised using the
   upstream instrument/unit and the refinement's `entity_associations`. This
   is how base metrics (`system.*`, `hw.*`, `container.*`) become emittable
   without duplicating their definitions in the local model.
4. Builds an entity topology graph from `spec.topology.entities[]` in
   `simulator_config.yaml`. Every node declares its `type`, `identity`, and
   `attributes`. Parent–child nesting is arbitrary depth.
5. For each entity type registered in the model, finds matching topology
   nodes, then emits every metric whose `entity_associations` includes that
   type.
6. For each (entity node, metric) pair, calls the `WorkloadEngine` to
   synthesise a realistic numeric value using the matching rule from
   `workload_profile.yaml` — or a unit-aware fallback if no rule matches.
7. Serialises all data points as OTLP/JSON and POSTs them to the configured
   HTTP endpoint.

The current model produces **119 unique metric names** emitted across
**32 resource batches** per cycle. The 32 batches come from the 13 entity
types that have associated metrics, instantiated across all topology nodes.

---

## 2. File map

| File | Role |
| --- | --- |
| `otel_semconv_sim.py` | Simulator engine — registry loader, topology graph, workload engine, OTLP serialiser |
| `simulator_config.yaml` | Topology definition, registry paths, namespace filters, OTLP endpoint |
| `workload_profile.yaml` | Declarative per-metric-pattern math generators |
| `demo.sh` | Convenience wrapper: `start`, `stop`, `emit-once`, `emit-continuous` |
| `docker-compose.yaml` | Container stack: OTel Collector → Prometheus → Grafana |
| `otelcol-config.yaml` | OTel Collector pipeline: OTLP HTTP/gRPC in → Prometheus scrape endpoint |
| `prometheus.yml` | Prometheus scrape config (scrapes collector at port 8889) |
| `grafana-datasources.yaml` | Grafana provisioning: Prometheus datasource at `http://prometheus:9090` |

---

## 3. Simulator architecture

### 3.1 Registry loading

`SemConvRegistry` is the schema ingestor. It exposes four methods called in
order by `SemConvSimulator._load_registry()`:

| Method | Input format | Purpose |
| --- | --- | --- |
| `load_upstream_directory(path)` | v1 `groups:` YAML | Populates `_upstream_metrics` stubs |
| `load_directory(path)` | v2 `definition/2` YAML | Parses attributes, entities, metrics, queues `metric_refinements` |
| `resolve_metric_refinements()` | — | Promotes queued refinements into `MetricDef` objects |
| `summary()` | — | Returns entity/attribute/metric counts for startup log |

**Key rule:** `load_file()` skips any file whose first-level key is not
`file_format: definition/2`. Files in `.build/sc-upstream-filtered/` use the
v1 `groups:` schema and are intentionally loaded only through
`load_upstream_directory()`.

**Refinement resolution detail:** `resolve_metric_refinements()` iterates
`_pending_refinements` (collected during `load_directory()`). For each
`ref: <name>` entry:

- If `<name>` is already in `self.metrics` (standalone `metrics:` entry),
  the existing `MetricDef` absorbs the additional `entity_associations` from
  the refinement.
- If `<name>` is only in `_upstream_metrics`, a new `MetricDef` is created
  using the upstream instrument and unit.
- If `<name>` is in neither, a DEBUG-level warning is emitted and the entry
  is skipped. This is not an error — the simulator is intentionally lenient
  about unknown upstream refs.

### 3.2 Topology graph

`TopologyGraph` is a DAG of `TopologyNode` objects built from
`spec.topology.entities[]` in `simulator_config.yaml`. Each node has:

- `entity_type` — must match a `type:` registered in the model entities.
- `identity` — key/value pairs that uniquely identify this instance.
- `attributes` — descriptive key/value pairs emitted as OTLP resource attributes.
- `children` — list of child `TopologyNode` objects (arbitrary depth).

`TopologyNode.get_all_resource_attributes()` merges `identity` + `attributes`
and adds `otel.entity.type` for every OTLP resource. `TopologyGraph.find_all(type)`
performs a depth-first search across all roots.

**Important:** A topology node whose `entity_type` is not registered in the
model emits no metrics — `find_all()` will find it but the `associated_metrics`
list will be empty. This is not an error.

### 3.3 Workload engine

`WorkloadEngine` matches metrics to rules in `workload_profile.yaml` and
produces numeric values. Rule matching is first-match-wins on `match:`:

| Match field | Behaviour |
| --- | --- |
| `pattern` | Regex search against `metric.name`. Evaluated first. |
| `unit` | Exact string match against `metric.unit`. |
| `type` | Exact string match against `metric.instrument` (`gauge`, `sum`, `histogram`). |

If no rule matches, `_default_fallback()` is called. The fallback is
unit-aware:

| Unit | Default behaviour |
| --- | --- |
| `1` | Sinusoidal 0–1 with Gaussian noise |
| `%` | Sinusoidal 0–100 with Gaussian noise |
| `By` / `bytes` | Gaussian around 16 GiB |
| `s` / `ms` / `us` | Gaussian around 5 ms |
| Any `sum` (monotonic) | Monotonically increasing counter, +10–50 per second |
| Anything else | `uniform(1, 100)` |

Available generator functions:

| Function | Key params | Best for |
| --- | --- | --- |
| `gaussian` | `mean`, `stddev`, `clamp_min`, `clamp_max` | Stable metrics with known steady-state values |
| `diurnal` | `min`, `max`, `base`, `amplitude`, `period`, `phase`, `noise_sigma` | Metrics that follow a daily utilisation cycle |
| `counter_accumulator` | `rate_generator.params.base`, `.amplitude`, `.period`, `.noise_sigma` | Monotonic counters with a diurnal rate variation |
| `pareto_spikes` | `baseline`, `spike_probability`, `spike_magnitude` | Error counters and rare-event flags |

Counter state is per `"{entity_id_key}:{metric.name}"` key so each topology
node maintains independent accumulation.

### 3.4 OTLP emission

`OTLPJsonClient` serialises data as OTLP/JSON (not proto-binary). Two
endpoints are used:

- `POST /v1/metrics` — one `resourceMetrics` entry per (entity type, topology node) pair.
- `POST /v1/logs` — one heartbeat log record per topology root node.

The instrument→OTLP mapping:

| `MetricDef.instrument` | OTLP representation |
| --- | --- |
| `gauge` | `gauge.dataPoints` |
| `sum` (monotonic) | `sum.dataPoints`, `aggregationTemporality: 2` (cumulative), `isMonotonic: true` |
| `sum` (non-monotonic) | `sum.dataPoints`, `aggregationTemporality: 2`, `isMonotonic: false` |
| anything else | falls back to `gauge.dataPoints` |

---

## 4. Configuration reference

### 4.1 simulator_config.yaml

```
apiVersion: semconv.simulation/v1alpha1
kind: SimulatorConfig
```

| Field | Type | Description |
| --- | --- | --- |
| `spec.registry.upstream_path` | string (relative path) | Path to the upstream v1 OTel registry. Resolved relative to this config file. Populated by `make filter-upstream`. Optional — simulator skips with a warning if absent. |
| `spec.registry.paths[]` | list of strings (relative paths) | Directories containing local v2 `definition/2` YAML model files. Resolved relative to this config file. |
| `spec.registry.schema_format` | string | Must be `definition/2`. Informational only — the loader checks file-level headers. |
| `spec.sampling_interval` | float (seconds) | How often to emit one telemetry cycle in continuous mode. |
| `spec.selection.signals` | list | Which signal types to emit. Supported: `metrics`, `logs`. |
| `spec.selection.include_namespaces[]` | list of regex strings | Only metrics whose name matches at least one pattern are emitted. Evaluated as `re.search()`. |
| `spec.selection.min_stability` | string | Minimum stability level to include. Currently accepted: `development`. |
| `spec.topology.entities[]` | list | Root entity nodes. Each entry: `type`, `identity` (map), `attributes` (map), `children[]` (recursive). |
| `spec.workload_profile_ref` | string (relative path) | Path to the workload profile YAML. Resolved relative to this config file. |
| `spec.exporter.otlp.http_endpoint` | string | OTLP HTTP endpoint, e.g. `http://localhost:4318`. |

**Topology node fields:**

```yaml
- type: <entity_type>          # must match a type: in ../model/
  identity:
    <attr_key>: <value>        # identity attributes (uniquely identify this instance)
  attributes:
    <attr_key>: <value>        # descriptive attributes
  children:                    # optional; arbitrary depth
    - type: ...
```

The `type` value must exactly match an entity `type:` declared in a v2
`entities:` block in the local model. Types that appear only in
`entity_refinements:` blocks are not registered in the model's entity index
and will produce no metrics.

### 4.2 workload_profile.yaml

```
apiVersion: semconv.simulation/v1alpha1
kind: WorkloadProfile
```

| Field | Description |
| --- | --- |
| `spec.default_sampling_interval` | Informational only; actual interval is set in `simulator_config.yaml`. |
| `spec.default_temporality` | Informational only; the simulator always emits cumulative for sums. |
| `spec.rules[]` | Ordered list of rules. First matching rule wins. |

Each rule:

```yaml
- match:
    pattern: "^regex$"        # regex on metric.name  (optional)
    unit: "W"                 # exact unit match      (optional)
    type: "gauge"             # exact instrument match (optional)
  generator:
    function: gaussian | diurnal | counter_accumulator | pareto_spikes
    params:
      ...
```

At least one of `pattern`, `unit`, or `type` must be present in `match:`.
If only `unit` and/or `type` are specified (no `pattern`), the rule matches
all metrics whose unit and instrument both satisfy the conditions.

---

## 5. Common contribution tasks

### 5.1 Add a new entity to the topology

**When:** A new entity type has been authored in `../model/` and you want the
simulator to emit its associated metrics.

1. Open `simulator_config.yaml`.
2. Under `spec.topology.entities[]`, add a node for the new entity type.
   Place it under the correct parent using `children:`, or as a root entry if
   the entity has no parent in the hierarchy.
3. Set `type:` to match the exact `type:` value from the entity's `entities:`
   block in the model YAML — not its `entity_refinements:` id.
4. Populate `identity:` with the attributes listed in the entity's
   `identity:` block.
5. Populate `attributes:` with any descriptive attributes you want carried in
   the OTLP resource.
6. Run `./demo.sh emit-once` and confirm the startup log shows the expected
   increase in emitted resource metric batches.

### 5.2 Add a namespace from a new model directory

**When:** A new namespace directory has been added under `../model/` (e.g.
`../model/zos/`).

1. In `simulator_config.yaml`, add the directory path to
   `spec.registry.paths[]`:
   ```yaml
   paths:
     - "../model/mainframe"
     - "../model/virtualization"
     - "../model/zos"           # ← new
   ```
2. Add the namespace regex to `spec.selection.include_namespaces[]`:
   ```yaml
   include_namespaces:
     - "^mainframe\\..*"
     - "^virtualization\\..*"
     - "^zos\\..*"             # ← new
   ```
3. Add topology nodes for the new entity types (see §5.1).
4. Add workload rules for the new metric patterns (see §5.3).
5. Run `./demo.sh emit-once` to verify.

### 5.3 Add or tune a workload rule

**When:** A new metric pattern is not covered by any existing rule, or the
default fallback produces unrealistic values for it.

Add a new entry to `spec.rules[]` in `workload_profile.yaml`. Rules are
evaluated in order; insert more specific rules before broader catch-alls.

Example — adding a rule for a new counter with a diurnal rate:

```yaml
- match:
    pattern: "^zos\\.wlm\\.cpu\\.time$"
  generator:
    function: counter_accumulator
    params:
      rate_generator:
        params:
          base: 500.0
          amplitude: 150.0
          period: 86400.0
          noise_sigma: 20.0
```

Example — adding a gauge rule matching a unit across all metrics with that unit:

```yaml
- match:
    unit: "{msu}"
  generator:
    function: gaussian
    params:
      mean: 1400.0
      stddev: 50.0
      clamp_min: 0.0
```

After adding rules, run `./demo.sh emit-once` and verify in Prometheus or the
simulator log that the metrics are emitting values within the expected range.

### 5.4 Extend the simulator engine

**When:** You need a new generator function, a new signal type (spans), or
changes to OTLP serialisation.

The engine is in `otel_semconv_sim.py`. The class structure is:

```
SemConvRegistry     — schema ingestor (load_directory, load_upstream_directory,
                      resolve_metric_refinements)
TopologyGraph       — DAG of TopologyNode instances built from config
WorkloadEngine      — rule-based value generator
OTLPJsonClient      — HTTP POST to /v1/metrics and /v1/logs
SemConvSimulator    — orchestrator (loads config, wires above, runs loop)
```

**Adding a generator function:** Add an `elif fn == "<name>":` branch in
`WorkloadEngine.compute_metric_value()`. The function receives `params` (dict
from the YAML rule) and must return a `float`.

**Adding a signal type (e.g. spans):** Add a `generate_spans_cycle()` method
to `SemConvSimulator` and a corresponding `export_traces()` method to
`OTLPJsonClient`. Follow the same resource-batching pattern used by
`generate_metrics_cycle()`.

**Extending the registry parser:** If the v2 YAML schema gains new top-level
keys, add parsing in `SemConvRegistry.load_file()`. Keep the v2/v1 format
separation: v1 files are never passed to `load_file()`.

The simulator has no test suite in this directory. After engine changes, run
the full validation sequence in §7.

### 5.5 Add a new container service

**When:** You want to add a backend (e.g. Jaeger for traces, Loki for logs)
to the stack.

1. Add the service block to `docker-compose.yaml`.
2. Add it to the `semconv-net` network.
3. If it requires Grafana provisioning, add a `volumes:` mount into
   `/etc/grafana/provisioning/datasources/` — do **not** introduce new
   dashboard JSON files (see §6).
4. Update `otelcol-config.yaml` if the collector needs to fan out to the new
   backend.
5. Document the new service's port in `README.md`.

---

## 6. Invariants and constraints

These invariants were established during implementation and must be preserved:

**Registry paths are relative to this directory.**
`simulator_config.yaml` uses `../model/mainframe`, `../model/virtualization`,
and `../.build/sc-upstream-filtered`. These paths resolve from the directory
containing `simulator_config.yaml`. Do not convert them to absolute paths or
move `simulator_config.yaml` without updating them.

**The upstream path is optional; absence is graceful.**
If `../.build/sc-upstream-filtered` does not exist (not yet populated by
`make filter-upstream`), the simulator logs a warning and continues. Only
`metric_refinements: ref:` entries for upstream metrics will be silently
skipped. Run `make filter-upstream` in `../` to populate it.

**`entity_associations` must use the entity `type` string, not the refinement id.**
`entity_refinements:` entries resolve into `refinements.entities[]` in the
Weaver model. The Rego policy engine and the simulator both read
`registry.entities[]`, populated only by standalone `entities:` blocks.
Writing `entity_associations: [refinement.some.id]` silently produces no
metric emissions — always use the `type` string (e.g. `virtualization.partition`).

**No hardcoded metric or entity names in the engine.**
`otel_semconv_sim.py` must remain domain-agnostic. Any mainframe-specific
knowledge belongs in `simulator_config.yaml` or `workload_profile.yaml`.
The only permitted appearance of domain strings in the Python source is in
`--help` text examples.

**No dashboard files in this directory.**
Demo users explore metrics via Grafana Explore at `http://localhost:3000/explore`.
Mainframe-specific Grafana dashboard JSON must not be committed here — the
Grafana container starts with only the Prometheus datasource provisioned.

**Do not commit test data, generated artefacts, or container volumes.**
The `__pycache__/` directory created by Python is `.gitignore`-exempt.
Nothing else transient (container volumes, exported metrics JSON, generated
OTLP payloads) belongs in this directory.

**Weaver policy baseline: 42 warnings.**
All pre-existing warnings are `UnstableFileFormat` (advisory for `definition/2`)
and `MissingRequirementLevelWarning` (advisory for entities without
`requirement_level:`). After any model change, `make check-policies` must
report `✔ No after_resolution policy violation` and must not increase the
warning count beyond the pre-existing baseline.

---

## 7. Validating changes

Run these checks in order before opening a pull request.

```bash
# 1. YAML syntax check — all config files
python3 -c "import yaml; [yaml.safe_load(open(f)) for f in \
  ['simulator_config.yaml','workload_profile.yaml', \
   'otelcol-config.yaml','prometheus.yml', \
   'grafana-datasources.yaml']]" \
  && echo "All YAML valid"

# 2. Simulator dry run (no OTLP endpoint required)
python3 otel_semconv_sim.py --config simulator_config.yaml --once

# 3. Full stack smoke test
./demo.sh start && sleep 5 && ./demo.sh emit-once && ./demo.sh stop

# 4. Weaver policy check (from the repository root)
cd .. && make check-policies
```

Expected simulator output for a clean run:

```
[INFO] Upstream registry: loaded 532 metric stubs from .build/sc-upstream-filtered
[INFO] Loaded 15 entities, 76 attributes, and 119 metrics (532 upstream stubs available).
[INFO] Active simulation metrics in scope: 119 / 119
[INFO] Emitted 32 resource metric batches. Status: OK
[INFO] Emitted 2 resource log records. Status: OK
```

The `Status: FAILED` lines during a dry run (no running collector) are
expected — the registry loading numbers and batch counts are what matter.

---

## 8. Upstream registry and metric refinements

The local model deliberately avoids re-defining upstream OTel metrics
(`system.*`, `hw.*`, `container.*`). Instead, `metric_refinements:` blocks
in `../model/mainframe/` and `../model/virtualization/` extend those metrics
with mainframe-specific `entity_associations` and attributes.

The simulator bridges this gap through the three-step load sequence described
in §3.1. The upstream registry at `../.build/sc-upstream-filtered/` is
populated by running:

```bash
cd ..
make filter-upstream
```

This clones the upstream `opentelemetry-specification/semantic-conventions`
at the pinned tag from `versions.env` and removes the sub-domains that have
been migrated into this repository.

**If the upstream path is absent:** The simulator emits all locally-defined
`metrics:` (the 83 authored metrics) but skips the 36 metrics that come
exclusively from `metric_refinements: ref:` resolution. Run
`make filter-upstream` to restore full coverage.

**Resolution order within `resolve_metric_refinements()`:**

1. If the `ref:` name already exists in `self.metrics` (a local `metrics:`
   entry), the refinement's `entity_associations` are merged in. The local
   definition's instrument and unit are preserved.
2. If the `ref:` name exists only in `_upstream_metrics`, a new `MetricDef`
   is synthesised from the upstream stub.
3. If the `ref:` name exists in neither, a DEBUG log is emitted. This is
   expected for `metric_refinements:` that reference metrics not yet
   included in the upstream snapshot.

---

## 9. Name drift between spec and model

All spec-to-model drifts have been fully resolved. The table below documents
each original drift, the interim state, and the final authoritative model name:

| Spec / original name | Final model name | Notes |
| --- | --- | --- |
| `mainframe.cpu.thread.utilization` | `mainframe.cpu.thread0.utilization` + `mainframe.cpu.thread1.utilization` | HMC API exposes no shared axis; two separate metrics is correct |
| `virtualization.partition.cpu.is_capped` | `virtualization.partition.cpu.is_capped` | Restored to `virtualization.partition` namespace — capping is a cross-platform concept |
| `virtualization.partition.cpu.weight` | `virtualization.partition.cpu.weight` | Restored to `virtualization.partition` namespace — scheduling weight is cross-platform; `mainframe.partition.weight.type` attribute retained for IBM Z weight category discrimination |
| `virtualization.storage_pool.capacity` | `virtualization.storage_pool.available` | `.capacity.` infix removed for consistency with `virtualization.platform.memory.*` pattern |
| `virtualization.storage_pool.usage` | `virtualization.storage_pool.used` | Renamed to `used` for consistency; mirrors `virtualization.platform.memory.used` |

Two metrics that were documented in the spec but absent from the model have been
authored, and the namespace corrections above net -1 metric (3 mainframe metrics
removed, 2 virtualization metrics added). The model now contains **83
locally-defined metrics**:

| Added metric | File | Notes |
| --- | --- | --- |
| `virtualization.partition.cpu.time` | `../model/virtualization/metrics_partition.yaml` | Cumulative IFL CPU time counter (seconds). |
| `virtualization.partition.cpu.weight` | `../model/virtualization/metrics_partition.yaml` | Moved from `mainframe.partition.cpu.weight.value`; cross-platform. |
| `virtualization.partition.cpu.is_capped` | `../model/virtualization/metrics_partition.yaml` | Moved from `mainframe.partition.cpu.is_capped` + `mainframe.partition.cpu.weight.is_capped`; cross-platform. |

---

## Related documentation

- [Repository CONTRIBUTING.md](../CONTRIBUTING.md) — model authoring workflow,
  Weaver validation, PR checklist
- [README.md](README.md) — quick start and component overview
- [Simulator configuration schema](simulator_config.yaml) — fully annotated
  example with all entity types from the current IBM Z topology
- [Workload profile](workload_profile.yaml) — fully annotated rules for all
  119 active metrics
