from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from uthana import Uthana
from uthana.modules import vtm


@pytest.mark.asyncio
@pytest.mark.parametrize("max_bytes", [None, 1000])
async def test_video_hard_cap_cannot_be_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, max_bytes: int | None
) -> None:
    monkeypatch.setattr(vtm, "VIDEO_UPLOAD_MAX_BYTES", 4)
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"12345")
    client = Uthana("synthetic-key", telemetry=False)
    with patch.object(client, "_graphql", new_callable=AsyncMock) as submit:
        with pytest.raises(ValueError, match="200 MiB"):
            await client.vtm.create(str(source), max_bytes=max_bytes)
        with pytest.raises(ValueError, match="200 MiB"):
            await client.vtm.create_from_bytes("clip.mp4", b"12345", max_bytes=max_bytes)
        submit.assert_not_called()
    client.close()


@pytest.mark.asyncio
async def test_video_boundary_and_lower_custom_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(vtm, "VIDEO_UPLOAD_MAX_BYTES", 4)
    client = Uthana("synthetic-key", telemetry=False)
    with patch.object(
        client, "_graphql", new_callable=AsyncMock, return_value={"id": "job1"}
    ) as submit:
        await client.vtm.create_from_bytes("clip.mp4", b"1234", max_bytes=None)
        with pytest.raises(ValueError, match="max_bytes"):
            await client.vtm.create_from_bytes("clip.mp4", b"1234", max_bytes=3)
        assert submit.call_count == 1
    client.close()


@pytest.mark.asyncio
async def test_video_reads_are_bounded_even_when_file_size_is_underreported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Source(BytesIO):
        def fileno(self) -> int:
            return 0

        def read(self, size: int = -1) -> bytes:
            assert size == 5
            return super().read(size)

    monkeypatch.setattr(vtm, "VIDEO_UPLOAD_MAX_BYTES", 4)
    monkeypatch.setattr(vtm.os, "fstat", lambda _: SimpleNamespace(st_size=0))
    with patch("builtins.open", return_value=Source(b"123456789")):
        client = Uthana("synthetic-key", telemetry=False)
        try:
            with patch.object(client, "_graphql", new_callable=AsyncMock) as submit:
                with pytest.raises(ValueError, match="200 MiB"):
                    await client.vtm.create("clip.mp4")
                submit.assert_not_called()
        finally:
            client.close()
