# Mainframe Semantic Conventions - Makefile
# Requires: podman (https://podman.io) and podman-compose (https://github.com/containers/podman-compose).
# The Weaver version is pinned in versions.env (WEAVER_VERSION) and run via
# the otel/weaver container image — contributors do not need to install weaver locally.

# Shared external version pins. Override on the command line when needed, e.g.
# `make check-policies SEMCONV_VERSION=v1.40.0`.
VERSION_PINS_FILE := versions.env
include $(VERSION_PINS_FILE)

# Run weaver via the pinned container image. The repo is bind-mounted at
# /workspace and that is the working directory, so every relative path the
# targets below pass to weaver (./model, .build/..., docs/, docs/registry)
# resolves the same way it would for a host-installed weaver.
WEAVER_IMAGE := otel/weaver:$(WEAVER_VERSION)
WEAVER := podman run --rm \
	-u $(shell id -u):$(shell id -g) \
	-v "$(CURDIR):/workspace" \
	-w /workspace \
	-e HOME=/tmp \
	$(WEAVER_IMAGE)

# podman-compose binary. Override if installed elsewhere:
#   make stack-up COMPOSE=/usr/local/bin/podman-compose
COMPOSE ?= podman-compose

# Compose project file for the reference observability stack.
# Use absolute path so podman-compose resolves bind-mount paths relative to
# the reference/ directory regardless of where make is invoked from.
COMPOSE_FILE := $(CURDIR)/reference/docker-compose.yaml

# Shared docs template from opentelemetry-weaver-packages, pinned to the same
# commit as the policy repo so a single renovate PR bumps both in lock-step.
WEAVER_PACKAGES_TEMPLATE := https://github.com/open-telemetry/opentelemetry-weaver-packages.git@$(WEAVER_PACKAGES_REF)[templates/docs]

# Local cache of policies fetched from upstream (gitignored)
LOCAL_POLICIES := .build/weaver-policies
LOCAL_POLICY_STAMP := $(LOCAL_POLICIES)/.$(POLICY_REPO_REF)

# Baseline registry for the backwards-compatibility policy. Override on the
# command line to compare against a different ref or fork.
BASELINE_REGISTRY := https://github.com/trask/semantic-conventions-mainframe.git[model]

# Filtered copy of the upstream semantic-conventions model. We clone the
# pinned upstream registry and delete the subdirectories that have been
# migrated into this repo.
#
# This repo is the new home for Mainframe semantic conventions. The
# definitions here are the canonical ones going forward; the matching
# definitions still living in open-telemetry/semantic-conventions will be
# removed once the migration completes. Until then, the pinned upstream
# registry we depend on for shared attributes (server.*, error.type, etc.)
# also still contains Mainframe groups that overlap with ours.
# Feeding both copies to Weaver would mean resolving the same id twice, so
# we strip the now-local subdirectories out of the upstream copy before
# Weaver sees it. When upstream finishes removing these definitions this
# filter becomes a no-op and can be deleted.
SC_UPSTREAM_CHECKOUT := .build/sc-upstream-$(SEMCONV_VERSION)
SC_UPSTREAM_FILTERED := .build/sc-upstream-filtered
SC_UPSTREAM_STAMP := $(SC_UPSTREAM_FILTERED)/.stamp-$(SEMCONV_VERSION)

# Upstream directories whose contents now live in this repo. Delete these
# from the filtered copy so their group ids do not collide with ours.
SC_UPSTREAM_MIGRATED_DIRS := mainframe zos ibm tps

# Group-level migrations: upstream namespaces where we own only a subset of
# the groups inside a shared registry file. Each entry is `<file>:<group_id>`,
# relative to upstream `model/`. The filtered upstream copy has each listed
# group stripped from its file so Weaver does not see two definitions of the
# same group id.
SC_UPSTREAM_MIGRATED_GROUPS := # aws/registry.yaml:registry.aws.bedrock

.PHONY: check-policies generate-registry generate-docs generate-json-schemas generate-all \
        clean filter-upstream package-dev emit stack-emit stack-up stack-down demo

# Release version = last path segment of the top-level schema_url in
# model/manifest.yaml. E.g. `mainframe-dev/1.42.0-dev` -> `1.42.0-dev`.
VERSION := $(shell awk '/^schema_url:/ { n = split($$2, parts, "/"); print parts[n]; exit }' model/manifest.yaml)
RESOLVED_SCHEMA_URI := https://github.com/open-telemetry/semantic-conventions-genai/releases/download/v$(VERSION)/resolved.yaml
PACKAGE_OUTPUT := .build/package

# Work around a Weaver 0.23.0 panic when `registry check` fetches a pinned remote
# policy pack by commit SHA. Keep the policy source pinned, but materialize it as
# a local checkout before running validation.
$(LOCAL_POLICY_STAMP): $(VERSION_PINS_FILE)
	@mkdir -p .build
	rm -rf $(LOCAL_POLICIES)
	git init -q $(LOCAL_POLICIES)
	cd $(LOCAL_POLICIES) && git remote add origin $(POLICY_REPO_URL)
	cd $(LOCAL_POLICIES) && git fetch --depth 1 origin $(POLICY_REPO_REF)
	cd $(LOCAL_POLICIES) && git checkout --detach FETCH_HEAD
	touch $(LOCAL_POLICY_STAMP)

# Clone upstream semantic-conventions at the pinned version and drop the
# subdirectories that have been migrated into this repo. See the long
# comment on SC_UPSTREAM_FILTERED above.
# Derive the upstream schema URL from the version tag: strip the leading 'v'
# from SEMCONV_VERSION (e.g. v1.42.0 -> 1.42.0) to form the schema URL.
SEMCONV_SCHEMA_VERSION := $(SEMCONV_VERSION:v%=%)

$(SC_UPSTREAM_STAMP): $(VERSION_PINS_FILE)
	@mkdir -p .build
	rm -rf $(SC_UPSTREAM_CHECKOUT) $(SC_UPSTREAM_FILTERED)
	git clone --depth 1 --branch $(SEMCONV_VERSION) \
		https://github.com/open-telemetry/semantic-conventions.git \
		$(SC_UPSTREAM_CHECKOUT)
	cp -r $(SC_UPSTREAM_CHECKOUT)/model $(SC_UPSTREAM_FILTERED)
	cd $(SC_UPSTREAM_FILTERED) && rm -rf $(SC_UPSTREAM_MIGRATED_DIRS)
	@# Strip group-level migrated entries (file:group_id) from the filtered
	@# upstream copy. Awk slices out each `  - id: <group_id>` block up to the
	@# next sibling group at the same indent (or EOF).
	@for entry in $(SC_UPSTREAM_MIGRATED_GROUPS); do \
		file=$${entry%%:*}; gid=$${entry##*:}; \
		target=$(SC_UPSTREAM_FILTERED)/$$file; \
		if [ -f "$$target" ]; then \
			awk -v gid="$$gid" 'BEGIN{skip=0} \
				/^  - id: / { skip = ($$0 == "  - id: " gid) } \
				!skip { print }' "$$target" > "$$target.tmp" && \
			mv "$$target.tmp" "$$target"; \
		fi; \
	done
	@# Patch the upstream dependency schema_url in manifest.yaml to match
	@# SEMCONV_VERSION so it never needs to be updated by hand.
	sed -i.bak \
		's|schema_url: https://opentelemetry.io/schemas/[0-9][0-9.]*|schema_url: https://opentelemetry.io/schemas/$(SEMCONV_SCHEMA_VERSION)|' \
		model/manifest.yaml && rm -f model/manifest.yaml.bak
	touch $(SC_UPSTREAM_STAMP)

filter-upstream: $(SC_UPSTREAM_STAMP)

# Validate the model and run shared policies
check-policies: $(LOCAL_POLICY_STAMP) $(SC_UPSTREAM_STAMP)
	$(WEAVER) registry check \
		-r ./model \
		--v2 \
		--debug --debug
		--diagnostic-format gh_workflow_command
		--diagnostic-stdout true
		--policy $(LOCAL_POLICIES)/policies/check \
		--policy policies/check/json-schema-annotations
		--baseline-registry '$(BASELINE_REGISTRY)' \ uncomment after removing deprecated entries

# Generate the attribute registry pages under docs/registry/ from the shared
# upstream weaver-packages markdown template.
generate-registry: $(SC_UPSTREAM_STAMP)
	$(WEAVER) registry generate \
		-r ./model \
		--v2 \
		-t '$(WEAVER_PACKAGES_TEMPLATE)' \
		--param registry_base_url=/docs/registry \
		markdown \
		./docs/registry

# Refresh the weaver snippet tables embedded in hand-written signal docs under
# docs/ (rewritten in place between <!-- weaver ... --> markers).
generate-docs: $(SC_UPSTREAM_STAMP)
	$(WEAVER) registry update-markdown \
		-r ./model \
		--v2 \
		-t '$(WEAVER_PACKAGES_TEMPLATE)' \
		--target markdown \
		--param registry_base_url=/docs/registry \
		docs

# Regenerate the JSON schemas under model/gen-ai/ from the pydantic models in
# docs/gen-ai/non-normative/models.py.
generate-json-schemas:
# TODO:	cd docs/gen-ai/non-normative && uv run models.py $(CURDIR)/model/gen-ai

# Run every regeneration the repo owns (weaver-driven + pydantic-driven).
# CI checks that all committed outputs match what this target generates.
generate-all: generate-registry generate-docs generate-json-schemas

# Resolve the registry and emit one synthetic data point per metric, span, and
# log to stdout or a live OTLP collector.
#
#   make emit                                      # emit to stdout (default)
#   make emit OTLP_ENDPOINT=http://localhost:4317  # emit to the local stack
#
# NOTE: Weaver runs inside a Podman container, so 'localhost' inside that
# container refers to the container itself, not the host.  When targeting the
# reference stack use OTLP_ENDPOINT=http://host.containers.internal:4317
# (Podman's host gateway alias), which make stack-emit sets automatically.
OTLP_ENDPOINT ?=
emit: $(SC_UPSTREAM_STAMP)
	$(WEAVER) registry emit \
		-r ./model \
		--v2 \
		--skip-policies \
		$(if $(OTLP_ENDPOINT),--endpoint $(OTLP_ENDPOINT),--stdout)

# Emit synthetic telemetry into the running reference stack.
# Uses host.containers.internal so the Weaver container can reach the
# OTel Collector running on the host network.
stack-emit: $(SC_UPSTREAM_STAMP)
	$(WEAVER) registry emit \
		-r ./model \
		--v2 \
		--skip-policies \
		--endpoint http://host.containers.internal:4317

# Package the registry into a publication artifact. The version comes from
# model/manifest.yaml's schema_url; bump it there to cut a new release.
package-dev: $(SC_UPSTREAM_STAMP)
	@mkdir -p .build
	rm -rf $(PACKAGE_OUTPUT)
	$(WEAVER) registry package \
		-r ./model \
		--v2 \
		--resolved-schema-uri '$(RESOLVED_SCHEMA_URI)' \
		-o ./$(PACKAGE_OUTPUT)
	@echo "Packaged version $(VERSION) -> $(PACKAGE_OUTPUT)"

# --- Reference observability stack -----------------------------------------

# Export all versions.env variables so podman-compose can expand them inside
# docker-compose.yaml (${OTELCOL_VERSION}, ${PROMETHEUS_VERSION}, etc.).
export OTELCOL_VERSION
export PROMETHEUS_VERSION
export GRAFANA_VERSION

# Start the OTel Collector + Prometheus + Grafana stack in the background.
# Grafana will be available at http://localhost:3000 (admin/admin).
stack-up:
	$(COMPOSE) -f $(COMPOSE_FILE) up -d
	@echo ""
	@echo "Stack is up. Grafana: http://localhost:3000  (admin / admin)"
	@echo "Run 'make stack-emit' to send synthetic telemetry into the stack."

# Stop and remove the stack containers (volumes are preserved).
stack-down:
	$(COMPOSE) -f $(COMPOSE_FILE) down

# One-shot demo: start the stack, wait for the collector to be ready,
# emit synthetic telemetry, then print the Grafana URL.
demo: stack-up
	@echo "Waiting for OTel Collector gRPC port to be ready..."
	@for i in $$(seq 1 30); do \
	    nc -z localhost 4317 2>/dev/null && break; \
	    sleep 1; \
	done
	$(MAKE) stack-emit
	@echo ""
	@echo "Telemetry emitted. Open Grafana: http://localhost:3000"
	@echo "  Login: admin / admin"
	@echo "  Dashboards → Mainframe → pick any dashboard"

# ---------------------------------------------------------------------------

# Remove generated docs, the local .build/ tree (Weaver-fetched templates/policies
# plus any hand-created weaver-min-repro* dirs), and Python bytecode trees.
clean:
	rm -rf docs/registry
	rm -rf .build
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name '*.egg-info' -prune -exec rm -rf {} +
	find . -type d -name .ruff_cache -prune -exec rm -rf {} +
