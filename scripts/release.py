#!/usr/bin/env python3
"""Publish helper for the uthana PyPI package.

Commands:

  publish [--dry-run] [--index pypi|testpypi]
      Removes dist/, runs uv build, then uv publish.
      --dry-run validates without uploading.
      Local uploads need a PyPI or TestPyPI API token (see README).

Examples:

    uv run python scripts/release.py publish --dry-run
    uv run python scripts/release.py publish
    uv run python scripts/release.py publish --index testpypi

Use uv run python scripts/release.py --help for full options.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT_DIR / "dist"

_PUBLISH_INDEX = {
    "pypi": ("https://upload.pypi.org/legacy/", "https://pypi.org/simple"),
    "testpypi": ("https://test.pypi.org/legacy/", "https://test.pypi.org/simple"),
}


def clean_dist_dir() -> None:
    """Remove dist/ so uv publish only sees artifacts for the current build."""
    if DIST_DIR.is_dir():
        shutil.rmtree(DIST_DIR)


def command_publish(args: argparse.Namespace) -> None:
    publish_url, check_url = _PUBLISH_INDEX[args.index]
    clean_dist_dir()
    subprocess.run(["uv", "build"], cwd=ROOT_DIR, check=True)
    cmd = [
        "uv",
        "publish",
        "--publish-url",
        publish_url,
        "--check-url",
        check_url,
    ]
    if args.dry_run:
        cmd.append("--dry-run")
    subprocess.run(cmd, cwd=ROOT_DIR, check=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Publish the uthana package to PyPI or TestPyPI.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    publish_parser = subparsers.add_parser(
        "publish",
        help="Clear dist/, uv build, uv publish (PyPI or TestPyPI)",
    )
    publish_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate publish without uploading (uv publish --dry-run)",
    )
    publish_parser.add_argument(
        "--index",
        choices=sorted(_PUBLISH_INDEX.keys()),
        default="pypi",
        help="Package index (default: production PyPI)",
    )
    publish_parser.set_defaults(func=command_publish)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except Exception as error:  # noqa: BLE001
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    import sys

    main()
