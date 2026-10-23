"""Shared byte detection remains a hint rather than upload validation."""

import pytest

from uthana import detect_file_format


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (b"glTF", "glb"),
        (b"Kaydara FBX Binary  \x00", "fbx"),
        (b" \n; FBX 7.4.0", "fbx"),
        (b"; FBX ftyp", "fbx"),
        (b"\x89PNG\r\n\x1a\n", "png"),
        (b"\xff\xd8\xff", "jpg"),
        (b"\x1aE\xdf\xa3", "webm"),
        (b"RIFF\x00\x00\x00\x00WEBP", "webp"),
        (b"\x00\x00\x00\x18ftypisom", "mp4"),
        (b"\x00\x00\x00\x18moov", "mp4"),
        (b"\x00\x00\x00\x18mdat", "mp4"),
        (b' \n{"asset": {"version": "2.0"}}', "gltf"),
        (b"{}", "gltf"),
        (b"", None),
        (b"RIFF\x00\x00\x00\x00WAVE", None),
        (b"\x89PNG", None),
        (b"not a supported file", None),
    ],
)
def test_detect_file_format(data: bytes, expected: str | None) -> None:
    assert detect_file_format(data) == expected
