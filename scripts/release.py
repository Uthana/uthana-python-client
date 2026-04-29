#!/usr/bin/env python3
"""Release helper: keep git tags and pyproject.toml version aligned for PyPI releases.

Run by maintainers before publishing (see README "Releasing and PyPI").

Commands:

  prepare --version SEMVER
      Bump project.version in pyproject.toml (if needed), optionally commit,
      and create an annotated v* tag. Requires a clean git worktree. Afterward:
      git push origin <branch> --follow-tags.

  check-tag --tag vX.Y.Z [--github-output PATH]
      Validate tag shape and that pyproject.toml matches the tag's base version.
      Used by CI on tag pushes; you rarely run this locally.

  verify [--skip-remote-check]
      Confirm project.version matches a local v* tag at HEAD and (unless
      --skip-remote-check) that the tag exists on origin (GitHub). Skipped if
      SKIP_RELEASE_TAG_CHECK=1 (same env as the JS client's npm publish guard).

  push [--dry-run]
      git push origin <current-branch> [--follow-tags]; --dry-run passes git push --dry-run.

  publish [--dry-run] [--index pypi|testpypi]
      Removes dist/, uv build, then uv publish (--dry-run validates without uploading).
      Local uploads need a PyPI or TestPyPI API token (see README).

Examples:

    uv run python scripts/release.py prepare --version 1.2.3
    uv run python scripts/release.py push
    uv run python scripts/release.py verify
    uv run python scripts/release.py publish --dry-run
    uv run python scripts/release.py publish --dry-run --index testpypi

Use uv run python scripts/release.py --help or <command> --help.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[no-redef]

ROOT_DIR = Path(__file__).resolve().parents[1]
PYPROJECT_FILE = ROOT_DIR / "pyproject.toml"
DIST_DIR = ROOT_DIR / "dist"

# uv publish endpoints (see https://docs.astral.sh/uv/reference/cli/#uv-publish)
_PUBLISH_INDEX = {
    "pypi": ("https://upload.pypi.org/legacy/", "https://pypi.org/simple"),
    "testpypi": ("https://test.pypi.org/legacy/", "https://test.pypi.org/simple"),
}
SEMVER_PATTERN = r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-rc\.(0|[1-9]\d*))?$"
TAG_PATTERN = rf"^v{SEMVER_PATTERN[1:]}"


@dataclass(frozen=True)
class ParsedVersion:
    full: str
    base: str
    is_prerelease: bool


def run_git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT_DIR,
        check=check,
        text=True,
        capture_output=True,
    )


def run_git_inherit_stdio(*args: str) -> None:
    subprocess.run(["git", *args], cwd=ROOT_DIR, check=True)


def parse_version(version: str) -> ParsedVersion:
    normalized = version.strip()
    if normalized.startswith("v"):
        normalized = normalized[1:]
    if not re.fullmatch(SEMVER_PATTERN, normalized):
        raise ValueError(
            "Invalid version format. Expected MAJOR.MINOR.PATCH or MAJOR.MINOR.PATCH-rc.N"
        )
    base = normalized.split("-", maxsplit=1)[0]
    return ParsedVersion(full=normalized, base=base, is_prerelease="-" in normalized)


def parse_tag(tag: str) -> ParsedVersion:
    normalized = tag.strip()
    if not re.fullmatch(TAG_PATTERN, normalized):
        raise ValueError(
            "Invalid tag format. Expected vMAJOR.MINOR.PATCH or vMAJOR.MINOR.PATCH-rc.N"
        )
    return parse_version(normalized)


def read_pyproject_version() -> str:
    data = tomllib.loads(PYPROJECT_FILE.read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def write_pyproject_version(base_version: str) -> None:
    content = PYPROJECT_FILE.read_text(encoding="utf-8")
    updated = re.sub(
        r'(?m)^version = "[^"]+"',
        f'version = "{base_version}"',
        content,
        count=1,
    )
    PYPROJECT_FILE.write_text(updated, encoding="utf-8")


def require_clean_worktree() -> None:
    status = run_git("status", "--porcelain").stdout.strip()
    if status:
        raise RuntimeError(
            "Worktree is not clean. Commit/stash changes before creating a release tag."
        )


def assert_release_tag_at_head_and_on_origin(tag_name: str, *, skip_remote_check: bool) -> None:
    """Match JS publish-packages: local tag exists, HEAD is exact tag, tag on origin.

    Used by the verify command after pushing so CI/PyPI sees the same commit as GitHub.
    """
    local_ok = (
        run_git("rev-parse", "-q", "--verify", f"refs/tags/{tag_name}", check=False).returncode == 0
    )
    if not local_ok:
        raise RuntimeError(
            f"Missing local git tag {tag_name} for pyproject.toml version. "
            f"Create it: python scripts/release.py prepare --version … "
            f'or git tag -a {tag_name} -m "Release {tag_name}"'
        )

    describe = run_git("describe", "--tags", "--exact-match", "HEAD", check=False)
    head_tag = describe.stdout.strip() if describe.returncode == 0 else ""
    if describe.returncode != 0 or head_tag != tag_name:
        raise RuntimeError(
            f"HEAD must exactly match release tag {tag_name} "
            f"(current: {head_tag or 'not exactly tagged'}). "
            f"Check out the tagged commit or recreate the tag on this commit."
        )

    if skip_remote_check:
        return

    remote_result = run_git(
        "ls-remote",
        "--exit-code",
        "--tags",
        "origin",
        f"refs/tags/{tag_name}",
        check=False,
    )
    if remote_result.returncode not in (0, 2):
        raise RuntimeError(
            "Could not verify remote tags on origin. "
            "Check network/auth or rerun with --skip-remote-check."
        )
    if remote_result.returncode != 0:
        raise RuntimeError(
            f"Tag {tag_name} is not on origin (GitHub). "
            f"Push branch and tags: git push origin $(git branch --show-current) --follow-tags"
        )


def ensure_tag_is_new(tag_name: str, skip_remote_check: bool) -> None:
    local_exists = (
        run_git("rev-parse", "-q", "--verify", f"refs/tags/{tag_name}", check=False).returncode == 0
    )
    if local_exists:
        raise RuntimeError(f"Tag already exists locally: {tag_name}")

    if skip_remote_check:
        return
    remote_result = run_git(
        "ls-remote",
        "--exit-code",
        "--tags",
        "origin",
        f"refs/tags/{tag_name}",
        check=False,
    )
    if remote_result.returncode not in (0, 2):
        raise RuntimeError(
            "Could not verify remote tags on origin. "
            "Check network/auth or rerun with --skip-remote-check."
        )
    remote_exists = remote_result.returncode == 0
    if remote_exists:
        raise RuntimeError(f"Tag already exists on origin: {tag_name}")


def maybe_commit_version_bump(tag_name: str) -> None:
    run_git("add", str(PYPROJECT_FILE))
    staged = run_git("diff", "--cached", "--name-only").stdout.strip()
    if staged:
        run_git("commit", "-m", f"release: {tag_name}")


def create_annotated_tag(tag_name: str) -> None:
    run_git("tag", "-a", tag_name, "-m", f"Release {tag_name}")


def command_push(args: argparse.Namespace) -> None:
    branch = run_git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if branch in ("HEAD", ""):
        raise RuntimeError("Detached HEAD; checkout a branch before pushing.")
    if args.dry_run:
        run_git_inherit_stdio("push", "--dry-run", "origin", branch, "--follow-tags")
    else:
        run_git_inherit_stdio("push", "origin", branch, "--follow-tags")


def command_prepare(args: argparse.Namespace) -> None:
    version = parse_version(args.version)
    tag_name = f"v{version.full}"

    require_clean_worktree()
    ensure_tag_is_new(tag_name, skip_remote_check=args.skip_remote_check)

    write_pyproject_version(version.base)
    maybe_commit_version_bump(tag_name)
    create_annotated_tag(tag_name)

    branch_name = run_git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    print(f"Created {tag_name} from branch {branch_name}.")
    print("Next: uv run python scripts/release.py push")


def command_check_tag(args: argparse.Namespace) -> None:
    version = parse_tag(args.tag)
    pyproject_version = read_pyproject_version()

    if pyproject_version != version.base:
        raise RuntimeError(
            f"pyproject version mismatch: expected {version.base}, found {pyproject_version}"
        )

    if args.github_output:
        output_path = Path(args.github_output)
        with output_path.open("a", encoding="utf-8") as output_file:
            output_file.write(f"version_label={version.full}\n")
            output_file.write(f"is_prerelease={'true' if version.is_prerelease else 'false'}\n")
    print(f"Validated tag {args.tag}: base={version.base}, prerelease={version.is_prerelease}")


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


def command_verify(args: argparse.Namespace) -> None:
    if os.environ.get("SKIP_RELEASE_TAG_CHECK", "").strip() == "1":
        print("Skipping verify (SKIP_RELEASE_TAG_CHECK=1)")
        return

    py_ver = read_pyproject_version()
    parsed = parse_version(py_ver)
    tag_name = f"v{parsed.full}"
    assert_release_tag_at_head_and_on_origin(tag_name, skip_remote_check=args.skip_remote_check)
    if args.skip_remote_check:
        print(f"OK: {tag_name} matches pyproject.toml and HEAD (remote check skipped).")
    else:
        print(f"OK: {tag_name} matches pyproject.toml, HEAD, and origin.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=("Keep pyproject.toml version with v* release tags in sync"),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser(
        "prepare", help="Update versions, commit (if needed), and create tag"
    )
    prepare_parser.add_argument(
        "--version", required=True, help="SemVer version (e.g. 1.2.3 or 1.2.3-rc.0)"
    )
    prepare_parser.add_argument(
        "--skip-remote-check",
        action="store_true",
        help="Skip checking whether tag already exists on origin",
    )
    prepare_parser.set_defaults(func=command_prepare)

    check_parser = subparsers.add_parser("check-tag", help="Validate tag format and version sync")
    check_parser.add_argument("--tag", required=True, help="Git tag (e.g. v1.2.3 or v1.2.3-rc.0)")
    check_parser.add_argument(
        "--github-output",
        help="Optional path to write GitHub Actions outputs",
    )
    check_parser.set_defaults(func=command_check_tag)

    verify_parser = subparsers.add_parser(
        "verify",
        help="Confirm release tag at HEAD exists on GitHub (see JS publish-packages parity)",
    )
    verify_parser.add_argument(
        "--skip-remote-check",
        action="store_true",
        help="Only check local tag and HEAD (skip git ls-remote origin)",
    )
    verify_parser.set_defaults(func=command_verify)

    push_parser = subparsers.add_parser(
        "push",
        help="git push origin <branch> --follow-tags",
    )
    push_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run git push --dry-run (no refs sent to origin)",
    )
    push_parser.set_defaults(func=command_push)

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
    main()
