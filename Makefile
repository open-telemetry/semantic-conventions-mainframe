# Mainframe Semantic Conventions - Makefile
# Requires: podman or docker.
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
# Use podman if available, fall back to docker.
CONTAINER_RUNTIME := $(shell command -v podman 2>/dev/null || command -v docker 2>/dev/null)
WEAVER_IMAGE := otel/weaver:$(WEAVER_VERSION)
WEAVER := $(CONTAINER_RUNTIME) run --rm \
	-u $(shell id -u):$(shell id -g) \
	-v "$(CURDIR):/workspace" \
	-w /workspace \
	-e HOME=/tmp \
	$(WEAVER_IMAGE)

# Shared docs template from opentelemetry-weaver-packages, pinned to the same
# commit as the policy repo so a single renovate PR bumps both in lock-step.
WEAVER_PACKAGES_TEMPLATE := https://github.com/open-telemetry/opentelemetry-weaver-packages.git@$(WEAVER_PACKAGES_REF)[templates/docs]

# Local cache of policies fetched from upstream (gitignored)
LOCAL_POLICIES := .build/weaver-policies
LOCAL_POLICY_STAMP := $(LOCAL_POLICIES)/.$(POLICY_REPO_REF)

# Baseline registry for the backwards-compatibility policy. Override on the
# command line to compare against a different ref or fork.
BASELINE_REGISTRY := https://github.com/open-telemetry/semantic-conventions-mainframe.git[model]

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

.PHONY: check-policies generate-registry generate-docs generate-reference-reports generate-all \
        clean filter-upstream package-dev emit

# Release version = last path segment of the top-level schema_url in
# model/manifest.yaml. E.g. `mainframe-dev/0.1.0-dev` -> `0.1.0-dev`.
VERSION := $(shell awk '/^schema_url:/ { n = split($$2, parts, "/"); print parts[n]; exit }' model/manifest.yaml)
RESOLVED_SCHEMA_URI := https://github.com/open-telemetry/semantic-conventions-mainframe/releases/download/v$(VERSION)/resolved.yaml
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
# from SEMCONV_VERSION (e.g. v1.44.0 -> 1.44.0) to form the schema URL.
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
# NOTE: --baseline-registry flag is intentionally disabled until deprecated entries
# are removed from the model. To re-enable: add the flag to the command below and
# remove the final `\` from the --policy line.
check-policies: $(LOCAL_POLICY_STAMP) $(SC_UPSTREAM_STAMP)
	$(WEAVER) registry check \
		-r ./model \
		--v2 \
		--debug \
		--diagnostic-format gh_workflow_command \
		--diagnostic-stdout true \
		--policy $(LOCAL_POLICIES)/policies/check \
		--policy policies/check/json-schema-annotations

# Generate the attribute registry pages under docs/registry/ from the local
# template package under templates/docs. That package is a copy of the upstream
# weaver-packages markdown template extended to also render entity and metric
# refinements pages (entity-refinements.md, metric-refinements.md per namespace).
# See templates/docs/markdown/weaver.yaml for the full list of generated files.
# Upstream attributes link to the attribute pages of the pinned
# semantic-conventions release; the URL is derived from SEMCONV_VERSION.
UPSTREAM_DOCS_URL := https://github.com/open-telemetry/semantic-conventions/blob/$(SEMCONV_VERSION)/docs/registry/attributes/{namespace}.md
generate-registry: $(SC_UPSTREAM_STAMP)
	$(WEAVER) registry generate \
		-r ./model \
		--v2 \
		-t './templates/docs' \
		--param registry_base_url=/docs/registry \
		--param 'upstream_docs_url=$(UPSTREAM_DOCS_URL)' \
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

# Update reference reports (README.md and reports/) from data.json files.
generate-reference-reports:
# TODO:	cd reference && uv run --frozen update-reports

# Run every regeneration the repo owns (weaver-driven + reports).
# CI checks that all committed outputs match what this target generates.
# NOTE: generate-docs (weaver update-markdown) is intentionally excluded here.
# That command is for hand-written signal docs under docs/ with <!-- weaver -->
# snippet markers. Currently docs/ contains only the auto-generated docs/registry/
# tree, so running update-markdown on docs/ would re-process those generated
# files and produce a non-idempotent result. Re-add generate-docs to this
# target once hand-written docs with snippet markers exist outside docs/registry/.
generate-all: generate-registry generate-reference-reports

# Resolve the registry and emit one synthetic data point per metric, span, and
# log to stdout or a live OTLP collector.
#
#   make emit                                      # emit to stdout (default)
#   make emit OTLP_ENDPOINT=http://host.containers.internal:4317
#
# NOTE: Weaver runs inside a container (Podman or Docker), so 'localhost'
# inside that container refers to the container itself, not the host. To reach
# a collector on the host use the host gateway alias:
#   Podman: OTLP_ENDPOINT=http://host.containers.internal:4317
#   Docker: OTLP_ENDPOINT=http://host.docker.internal:4317
OTLP_ENDPOINT ?=
emit: $(SC_UPSTREAM_STAMP)
	$(WEAVER) registry emit \
		-r ./model \
		--v2 \
		--skip-policies \
		$(if $(OTLP_ENDPOINT),--endpoint $(OTLP_ENDPOINT),--stdout)

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

# Remove generated docs, the local .build/ tree (Weaver-fetched templates/policies
# plus any hand-created weaver-min-repro* dirs), reference-project caches, and
# Python bytecode trees under the entire repo.
#
# `clean` does NOT touch `reference/.venv`; rebuilding it requires a fresh
# `uv sync` which re-downloads every tooling dependency. Remove it manually
# (`rm -rf reference/.venv`) for a full reset.
clean:
	rm -rf docs/registry
	rm -rf .build
	rm -rf reference/.cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name '*.egg-info' -prune -exec rm -rf {} +
	find . -type d -name .ruff_cache -prune -exec rm -rf {} +
