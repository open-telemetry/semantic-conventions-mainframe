"""Weaver invocation: the pinned release on PATH, or the pinned container image.

The Makefile runs weaver from the ``otel/weaver`` image so that contributors do
not need to install it; CI installs the pinned release instead. Both are
supported here, in that order of preference: a ``weaver`` on PATH at the pinned
version, else the image through podman or docker.

Weaver always runs with the repository root as its working directory, so every
path handed to it is relative to that root -- the same convention as the
Makefile, and what lets the relative ``registry_path`` in
``model/manifest.yaml`` resolve.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Sequence
from functools import cache
from pathlib import Path

from semconv_mainframe import SEMCONV_ROOT
from semconv_mainframe.versions import require_pin

logger = logging.getLogger(__name__)

WEAVER_VERSION = require_pin("WEAVER_VERSION")
WEAVER_IMAGE = f"otel/weaver:{WEAVER_VERSION}"
# Where the repository root is mounted inside the container.
CONTAINER_WORKDIR = "/workspace"


def _normalize_version(version: str) -> str:
    """Normalize optional leading-v version strings for comparisons."""
    return version[1:] if version.startswith("v") else version


def _weaver_binary_name() -> str:
    """Return the platform-specific Weaver binary name."""
    return "weaver.exe" if sys.platform == "win32" else "weaver"


def _weaver_version(binary: str | Path) -> str:
    """Return the normalized version reported by a Weaver binary, or an empty string."""
    try:
        proc = subprocess.run(
            [str(binary), "--version"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return ""

    output = f"{proc.stdout}\n{proc.stderr}"
    match = re.search(r"\bv?(\d+\.\d+\.\d+)\b", output)
    return match.group(1) if match else ""


def _container_runtime() -> str | None:
    """podman or docker, as the Makefile picks it; ``CONTAINER_RUNTIME`` overrides."""
    return os.environ.get("CONTAINER_RUNTIME") or shutil.which("podman") or shutil.which("docker")


@cache
def ensure_weaver() -> Path | None:
    """The pinned Weaver binary on PATH, or None when weaver has to run in a container."""
    system_weaver = shutil.which(_weaver_binary_name())
    if system_weaver and _weaver_version(system_weaver) == _normalize_version(WEAVER_VERSION):
        return Path(system_weaver)
    if _container_runtime():
        return None
    if system_weaver:
        logger.warning("Using %s although it is not Weaver %s", system_weaver, WEAVER_VERSION)
        return Path(system_weaver)
    raise RuntimeError(
        f"Weaver {WEAVER_VERSION} is required: install it "
        "(https://github.com/open-telemetry/weaver/releases) or install podman or docker "
        f"to run the {WEAVER_IMAGE} image."
    )


def in_container() -> bool:
    return ensure_weaver() is None


def weaver_command(args: Sequence[str], *, ports: Sequence[int] = ()) -> list[str]:
    """The argv running ``weaver <args>`` from the repository root.

    ``ports`` are published on the loopback interface when weaver runs in a
    container, under the same numbers, so callers address both cases alike.
    """
    binary = ensure_weaver()
    if binary is not None:
        return [str(binary), *args]
    runtime = _container_runtime()
    assert runtime is not None  # ensure_weaver() raised otherwise
    command = [runtime, "run", "--rm", "-v", f"{SEMCONV_ROOT}:{CONTAINER_WORKDIR}", "-w", CONTAINER_WORKDIR]
    command += ["-e", "HOME=/tmp"]
    if hasattr(os, "getuid"):
        command += ["-u", f"{os.getuid()}:{os.getgid()}"]
    for port in ports:
        command += ["-p", f"127.0.0.1:{port}:{port}"]
    return [*command, WEAVER_IMAGE, *args]


def run_weaver(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    """Run a one-shot weaver command, raising with its output when it fails."""
    completed = subprocess.run(weaver_command(args), cwd=SEMCONV_ROOT, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"weaver {' '.join(args)} failed:\n{completed.stderr.strip() or completed.stdout.strip()}")
    return completed
