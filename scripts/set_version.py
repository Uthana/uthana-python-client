#!/usr/bin/env python3
"""Bump project.version in pyproject.toml. No git operations.

Usage:
    uv run python scripts/set_version.py 1.2.3
    make set-version VERSION=1.2.3
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"
SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-rc\.(0|[1-9]\d*))?$")

version = (sys.argv[1] if len(sys.argv) > 1 else "").strip().lstrip("v")
if not SEMVER_RE.match(version):
    sys.exit("Usage: uv run python scripts/set_version.py SEMVER  (e.g. 1.2.3 or 1.2.3-rc.0)")

content = PYPROJECT.read_text(encoding="utf-8")
updated = re.sub(r'(?m)^version = "[^"]+"', f'version = "{version}"', content, count=1)
if updated == content:
    print(f"set-version: already at {version}")
else:
    PYPROJECT.write_text(updated, encoding="utf-8")
    print(f"set-version: bumped to {version}")
