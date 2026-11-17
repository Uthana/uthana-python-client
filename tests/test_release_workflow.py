"""Release detection must fail closed when PyPI cannot establish version availability."""

import os
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    ("status", "exit_code", "should_release"),
    [("200", 0, "false"), ("404", 0, "true"), ("403", 0, None), ("500", 0, None), ("000", 6, None)],
)
def test_release_detection(
    tmp_path: Path, status: str, exit_code: int, should_release: str | None
) -> None:
    workflow = (Path(__file__).parents[1] / ".github/workflows/release.yml").read_text()
    detection = workflow.split("          STATUS=$(curl", 1)[1].split("\n\n      - name:", 1)[0]
    script = "STATUS=$(curl" + detection
    script = "\n".join(line.removeprefix("          ") for line in script.splitlines())
    curl = tmp_path / "curl"
    curl.write_text(f"#!/bin/sh\nprintf '%s' '{status}'\nexit {exit_code}\n")
    curl.chmod(0o755)
    output = tmp_path / "output"
    output.touch()
    result = subprocess.run(
        ["bash", "-e", "-c", script],
        env={
            **os.environ,
            "PATH": f"{tmp_path}:{os.environ['PATH']}",
            "VERSION": "0.0.0",
            "GITHUB_OUTPUT": str(output),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert (result.returncode == 0) == (should_release is not None)
    expected = "" if should_release is None else f"should_release={should_release}\n"
    assert output.read_text() == expected
