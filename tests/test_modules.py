# (c) Copyright 2026 Uthana, Inc. All Rights Reserved

"""Unit tests for module methods using mocked _graphql and httpx."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from uthana import Uthana, UthanaCharacters
from uthana.types import (
    CharacterPreviewResult,
    CreateFromGeneratedImageResult,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client() -> Uthana:
    """Create an Uthana client with all network calls patched out."""
    with (
        patch.object(Uthana, "_log_init", return_value={}),
        patch("uthana.client.httpx.AsyncClient", return_value=MagicMock()),
        patch("uthana.client.httpx.Client", return_value=MagicMock()),
    ):
        return Uthana("fake-key")


def _make_httpx_mock(response_data: dict):
    """Build a mock httpx.AsyncClient context manager returning JSON response_data."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.is_success = True
    mock_response.json.return_value = {"data": response_data}

    mock_http = AsyncMock()
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=False)
    mock_http.post = AsyncMock(return_value=mock_response)

    return mock_http


# ---------------------------------------------------------------------------
# characters.create_from_prompt — two-step, no callback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_prompt_no_callback_returns_preview_result() -> None:
    client = _make_client()
    client._graphql = AsyncMock(
        return_value={
            "character_id": "c1",
            "images": [
                {"key": "k1", "url": "http://img.com/1"},
                {"key": "k2", "url": "http://img.com/2"},
            ],
        }
    )

    result = await client.characters.create_from_prompt(prompt="a knight in armor")

    assert isinstance(result, CharacterPreviewResult)
    assert result.character_id == "c1"
    assert len(result.previews) == 2
    assert result.previews[0]["key"] == "k1"
    assert result.prompt == "a knight in armor"


# ---------------------------------------------------------------------------
# characters.create_from_prompt — sync callback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_prompt_with_sync_callback_returns_finalized() -> None:
    client = _make_client()
    client._graphql = AsyncMock(
        side_effect=[
            # CREATE_IMAGE_FROM_TEXT
            {
                "character_id": "c1",
                "images": [{"key": "k1", "url": "u1"}, {"key": "k2", "url": "u2"}],
            },
            # CREATE_CHARACTER_FROM_IMAGE
            {"character": {"id": "c1", "name": "Knight"}, "auto_rig_confidence": 0.9},
        ]
    )

    result = await client.characters.create_from_prompt(
        prompt="a knight",
        on_previews_ready=lambda previews: previews[1]["key"],  # pick second
    )

    assert isinstance(result, CreateFromGeneratedImageResult)
    assert result.character["id"] == "c1"
    assert result.auto_rig_confidence == 0.9
    finalize_vars = client._graphql.call_args_list[1][0][1]
    assert finalize_vars["image_key"] == "k2"
    assert finalize_vars["prompt"] == "a knight"


# ---------------------------------------------------------------------------
# characters.create_from_prompt — async callback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_prompt_with_async_callback() -> None:
    client = _make_client()
    client._graphql = AsyncMock(
        side_effect=[
            {"character_id": "c1", "images": [{"key": "k1", "url": "u1"}]},
            {"character": {"id": "c1", "name": "Knight"}, "auto_rig_confidence": None},
        ]
    )

    async def async_picker(previews):
        return previews[0]["key"]

    result = await client.characters.create_from_prompt(
        prompt="a knight", on_previews_ready=async_picker
    )

    assert isinstance(result, CreateFromGeneratedImageResult)
    finalize_vars = client._graphql.call_args_list[1][0][1]
    assert finalize_vars["image_key"] == "k1"


# ---------------------------------------------------------------------------
# characters.create_from_prompt — name forwarded to finalize call
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_prompt_passes_name() -> None:
    client = _make_client()
    client._graphql = AsyncMock(
        side_effect=[
            {"character_id": "c1", "images": [{"key": "k1", "url": "u1"}]},
            {"character": {"id": "c1", "name": "Warrior"}, "auto_rig_confidence": None},
        ]
    )

    await client.characters.create_from_prompt(
        prompt="a warrior",
        name="Warrior",
        on_previews_ready=lambda p: p[0]["key"],
    )

    finalize_vars = client._graphql.call_args_list[1][0][1]
    assert finalize_vars["name"] == "Warrior"


# ---------------------------------------------------------------------------
# characters.generate_from_image — step 2 of two-step flow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_from_image_finalizes_with_prompt() -> None:
    client = _make_client()
    client._graphql = AsyncMock(
        return_value={"character": {"id": "c1", "name": "Knight"}, "auto_rig_confidence": 0.8}
    )

    pending = CharacterPreviewResult(
        character_id="c1",
        previews=[{"key": "k1", "url": "u1"}],
        prompt="a knight",
    )
    result = await client.characters.generate_from_image(pending, "k1")

    assert result.character["id"] == "c1"
    finalize_vars = client._graphql.call_args[0][1]
    assert finalize_vars["character_id"] == "c1"
    assert finalize_vars["image_key"] == "k1"
    assert finalize_vars["prompt"] == "a knight"


# ---------------------------------------------------------------------------
# characters.create_from_image — upload image file, single-step
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_image_uploads_and_finalizes(tmp_path) -> None:
    img_file = tmp_path / "ref.png"
    img_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

    mock_http = _make_httpx_mock(
        {"create_image_from_image": {"character_id": "c2", "image": {"key": "k2", "url": "u2"}}}
    )

    client = _make_client()
    client._graphql = AsyncMock(
        return_value={"character": {"id": "c2", "name": "Archer"}, "auto_rig_confidence": 0.7}
    )

    with patch("uthana.modules.characters.httpx.AsyncClient", return_value=mock_http):
        result = await client.characters.create_from_image(str(img_file))

    assert isinstance(result, CreateFromGeneratedImageResult)
    assert result.character["id"] == "c2"
    # prompt is an internal detail — must be passed as "" to the GQL layer
    finalize_vars = client._graphql.call_args[0][1]
    assert finalize_vars["image_key"] == "k2"
    assert finalize_vars["prompt"] == ""


# ---------------------------------------------------------------------------
# characters.create_from_image — raises when file is missing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_image_raises_without_file() -> None:
    from uthana.types import UthanaError

    client = _make_client()
    with pytest.raises(UthanaError):
        await client.characters.create_from_image("")


# ---------------------------------------------------------------------------
# characters.rename
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rename_calls_mutation() -> None:
    client = _make_client()
    client._graphql = AsyncMock(return_value={"id": "c1", "name": "New Name"})

    await client.characters.rename("c1", "New Name")

    call_vars = client._graphql.call_args[0][1]
    assert call_vars["character_id"] == "c1"
    assert call_vars["name"] == "New Name"


# ---------------------------------------------------------------------------
# characters.delete
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_calls_mutation() -> None:
    client = _make_client()
    client._graphql = AsyncMock(return_value={"id": "c1", "name": "Knight"})

    await client.characters.delete("c1")

    call_vars = client._graphql.call_args[0][1]
    assert call_vars["character_id"] == "c1"


# ---------------------------------------------------------------------------
# motions.preview
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_preview_calls_correct_url() -> None:
    client = _make_client()

    mock_response = MagicMock()
    mock_response.is_success = True
    mock_response.content = b"webm-bytes"

    mock_http = AsyncMock()
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=False)
    mock_http.get = AsyncMock(return_value=mock_response)

    with patch("uthana.modules.motions.httpx.AsyncClient", return_value=mock_http):
        result = await client.motions.preview("char1", "motion1")

    assert result == b"webm-bytes"
    call_url = mock_http.get.call_args[0][0]
    assert "char1" in call_url
    assert "motion1" in call_url
    assert "preview.webm" in call_url


# ---------------------------------------------------------------------------
# motions.bake_with_changes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bake_with_changes_returns_result() -> None:
    client = _make_client()
    client._graphql = AsyncMock(return_value={"motion": {"id": "m99"}})

    result = await client.motions.bake_with_changes("<gltf/>", "My motion")

    assert result.motion_id == "m99"
    assert result.character_id == UthanaCharacters.tar
    call_vars = client._graphql.call_args[0][1]
    assert call_vars["motionName"] == "My motion"


@pytest.mark.asyncio
async def test_bake_with_changes_uses_provided_character_id() -> None:
    client = _make_client()
    client._graphql = AsyncMock(return_value={"motion": {"id": "m1"}})

    result = await client.motions.bake_with_changes(
        "<gltf/>", "My motion", character_id="custom-char"
    )

    assert result.character_id == "custom-char"
    call_vars = client._graphql.call_args[0][1]
    assert call_vars["characterId"] == "custom-char"


# ---------------------------------------------------------------------------
# motions.create_locomotion / list_locomotion_styles
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_locomotion_returns_result_and_variables() -> None:
    client = _make_client()
    client._graphql = AsyncMock(return_value={"motion": {"id": "m-loco", "name": "Loco Walk"}})

    result = await client.motions.create_locomotion(
        UthanaCharacters.tar,
        strides=2,
        move_speed=1.3,
        style_id="neutral_male_a",
        travel_angle=0.0,
    )

    assert result.character_id == UthanaCharacters.tar
    assert result.motion_id == "m-loco"
    call_query, call_vars = client._graphql.call_args[0][0], client._graphql.call_args[0][1]
    assert "create_locomotion" in call_query
    assert call_vars["character_id"] == UthanaCharacters.tar
    assert call_vars["strides"] == 2
    assert call_vars["move_speed"] == 1.3
    assert call_vars["style_id"] == "neutral_male_a"
    assert call_vars["travel_angle"] == 0.0


@pytest.mark.asyncio
async def test_create_locomotion_omits_optional_when_none() -> None:
    client = _make_client()
    client._graphql = AsyncMock(return_value={"motion": {"id": "m1"}})

    await client.motions.create_locomotion(UthanaCharacters.tar)

    call_vars = client._graphql.call_args[0][1]
    assert call_vars == {"character_id": UthanaCharacters.tar}
    assert "strides" not in call_vars


@pytest.mark.asyncio
async def test_create_locomotion_raises_without_motion_id() -> None:
    from uthana.types import UthanaError

    client = _make_client()
    client._graphql = AsyncMock(return_value={"motion": {}})

    with pytest.raises(UthanaError, match="create_locomotion did not return motion id"):
        await client.motions.create_locomotion(UthanaCharacters.tar)


@pytest.mark.asyncio
async def test_list_locomotion_styles_returns_list() -> None:
    client = _make_client()
    client._graphql = AsyncMock(return_value=["neutral_male_a", "neutral_female_a"])

    styles = await client.motions.list_locomotion_styles()

    assert styles == ["neutral_male_a", "neutral_female_a"]
    call_query = client._graphql.call_args[0][0]
    assert "locomotion_styles" in call_query


@pytest.mark.asyncio
async def test_list_locomotion_styles_empty_default() -> None:
    client = _make_client()
    client._graphql = AsyncMock(return_value=[])

    styles = await client.motions.list_locomotion_styles()

    assert styles == []


# ---------------------------------------------------------------------------
# jobs.list — timestamp normalization (created_at/started_at/ended_at → public names)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_jobs_list_normalizes_timestamps() -> None:
    client = _make_client()
    client._graphql = AsyncMock(
        return_value=[
            {
                "id": "j1",
                "status": "FINISHED",
                "method": "VideoToMotion",
                "created_at": "2026-01-01T00:00:00Z",
                "started_at": "2026-01-01T00:01:00Z",
                "ended_at": "2026-01-01T00:02:00Z",
            },
            {
                "id": "j2",
                "status": "PENDING",
                "method": "VideoToMotion",
                "created_at": "2026-01-03T00:00:00Z",
                "started_at": None,
                "ended_at": None,
            },
        ]
    )

    jobs = await client.jobs.list()

    assert len(jobs) == 2
    for job in jobs:
        assert "created_at" not in job
        assert "started_at" not in job
        assert "ended_at" not in job
    assert jobs[0]["created"] == "2026-01-01T00:00:00Z"
    assert jobs[0]["started"] == "2026-01-01T00:01:00Z"
    assert jobs[0]["ended"] == "2026-01-01T00:02:00Z"
    assert jobs[1]["created"] == "2026-01-03T00:00:00Z"
    assert jobs[1]["started"] is None
    assert jobs[1]["ended"] is None


@pytest.mark.asyncio
async def test_jobs_list_handles_missing_timestamps() -> None:
    """Jobs missing timestamp fields are left without created/started/ended keys."""
    client = _make_client()
    client._graphql = AsyncMock(
        return_value=[{"id": "j1", "status": "FINISHED", "method": "VideoToMotion"}]
    )

    jobs = await client.jobs.list()

    assert jobs[0].get("created") is None
    assert jobs[0].get("started") is None
    assert jobs[0].get("ended") is None
    assert "created_at" not in jobs[0]
    assert "started_at" not in jobs[0]
    assert "ended_at" not in jobs[0]


# ---------------------------------------------------------------------------
# jobs.get — timestamp normalization
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_jobs_get_normalizes_timestamps() -> None:
    client = _make_client()
    client._graphql = AsyncMock(
        return_value={
            "id": "j1",
            "status": "FINISHED",
            "result": {"id": "m1"},
            "created_at": "2026-01-01T00:00:00Z",
            "started_at": "2026-01-01T00:01:00Z",
            "ended_at": "2026-01-01T00:02:00Z",
        }
    )

    job = await client.jobs.get("j1")

    assert job["created"] == "2026-01-01T00:00:00Z"
    assert job["started"] == "2026-01-01T00:01:00Z"
    assert job["ended"] == "2026-01-01T00:02:00Z"
    assert "created_at" not in job
    assert "started_at" not in job
    assert "ended_at" not in job
