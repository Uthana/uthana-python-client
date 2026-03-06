#!/usr/bin/env python3
"""Release helper for SemVer tags and version synchronization."""

from __future__ import annotations

import argparse
import re
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
    print(f"Next: git push origin {branch_name} --follow-tags")


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Release and tag helper")
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
