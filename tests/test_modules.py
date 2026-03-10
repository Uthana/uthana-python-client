# (c) Copyright 2026 Uthana, Inc. All Rights Reserved

"""Unit tests for module methods using mocked _graphql and httpx."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from uthana import Uthana, UthanaCharacters
from uthana.types import (
    CreateFromGeneratedImageResult,
    GenerateFromImageResult,
    GenerateFromTextResult,
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


# ---------------------------------------------------------------------------
# characters.generate_from_text
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_from_text_returns_result() -> None:
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

    result = await client.characters.generate_from_text("a knight in armor")

    assert result.character_id == "c1"
    assert len(result.images) == 2
    assert result.images[0]["key"] == "k1"


# ---------------------------------------------------------------------------
# characters.create_from_generated_image
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_from_generated_image_returns_result() -> None:
    client = _make_client()
    client._graphql = AsyncMock(
        return_value={
            "character": {"id": "c1", "name": "Knight"},
            "auto_rig_confidence": 0.9,
        }
    )

    result = await client.characters.create_from_generated_image(
        "c1", "k1", "a knight in armor", name="Knight"
    )

    assert result.character["id"] == "c1"
    assert result.auto_rig_confidence == 0.9
    client._graphql.assert_called_once()
    call_vars = client._graphql.call_args[0][1]
    assert call_vars["character_id"] == "c1"
    assert call_vars["image_key"] == "k1"
    assert call_vars["name"] == "Knight"


# ---------------------------------------------------------------------------
# characters.create_from_text
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_from_text_defaults_to_first_preview() -> None:
    client = _make_client()
    client.characters.generate_from_text = AsyncMock(
        return_value=GenerateFromTextResult(
            character_id="c1",
            images=[{"key": "k1", "url": "u1"}, {"key": "k2", "url": "u2"}],
        )
    )
    client.characters.create_from_generated_image = AsyncMock(
        return_value=CreateFromGeneratedImageResult(
            character={"id": "c1"},
            auto_rig_confidence=0.85,
        )
    )

    result = await client.characters.create_from_text("a knight")

    client.characters.create_from_generated_image.assert_called_once_with(
        "c1", "k1", "a knight", name=None
    )
    assert result.character["id"] == "c1"


@pytest.mark.asyncio
async def test_create_from_text_lambda_on_previews_ready() -> None:
    client = _make_client()
    client.characters.generate_from_text = AsyncMock(
        return_value=GenerateFromTextResult(
            character_id="c1",
            images=[{"key": "k1", "url": "u1"}, {"key": "k2", "url": "u2"}],
        )
    )
    client.characters.create_from_generated_image = AsyncMock(
        return_value=CreateFromGeneratedImageResult(
            character={"id": "c1"},
            auto_rig_confidence=0.85,
        )
    )

    await client.characters.create_from_text(
        "a knight",
        on_previews_ready=lambda previews: previews[1]["key"],  # pick second
    )

    client.characters.create_from_generated_image.assert_called_once_with(
        "c1", "k2", "a knight", name=None
    )


@pytest.mark.asyncio
async def test_create_from_text_async_on_previews_ready() -> None:
    client = _make_client()
    client.characters.generate_from_text = AsyncMock(
        return_value=GenerateFromTextResult(
            character_id="c1",
            images=[{"key": "k1", "url": "u1"}],
        )
    )
    client.characters.create_from_generated_image = AsyncMock(
        return_value=CreateFromGeneratedImageResult(
            character={"id": "c1"},
            auto_rig_confidence=None,
        )
    )

    async def async_picker(previews):
        return previews[0]["key"]

    await client.characters.create_from_text("a knight", on_previews_ready=async_picker)

    client.characters.create_from_generated_image.assert_called_once_with(
        "c1", "k1", "a knight", name=None
    )


@pytest.mark.asyncio
async def test_create_from_text_passes_name() -> None:
    client = _make_client()
    client.characters.generate_from_text = AsyncMock(
        return_value=GenerateFromTextResult(
            character_id="c1",
            images=[{"key": "k1", "url": "u1"}],
        )
    )
    client.characters.create_from_generated_image = AsyncMock(
        return_value=CreateFromGeneratedImageResult(
            character={"id": "c1"},
            auto_rig_confidence=None,
        )
    )

    await client.characters.create_from_text("a knight", name="Knight")

    client.characters.create_from_generated_image.assert_called_once_with(
        "c1", "k1", "a knight", name="Knight"
    )


# ---------------------------------------------------------------------------
# characters.create_from_image
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_from_image_auto_confirms_single_preview() -> None:
    client = _make_client()
    client.characters.generate_from_image = AsyncMock(
        return_value=GenerateFromImageResult(
            character_id="c1",
            image={"key": "k1", "url": "u1"},
        )
    )
    client.characters.create_from_generated_image = AsyncMock(
        return_value=CreateFromGeneratedImageResult(
            character={"id": "c1"},
            auto_rig_confidence=0.7,
        )
    )

    result = await client.characters.create_from_image(
        "path/to/ref.png", prompt="a knight in armor"
    )

    client.characters.create_from_generated_image.assert_called_once_with(
        "c1", "k1", "a knight in armor", name=None
    )
    assert result.character["id"] == "c1"


@pytest.mark.asyncio
async def test_create_from_image_lambda_on_previews_ready() -> None:
    client = _make_client()
    client.characters.generate_from_image = AsyncMock(
        return_value=GenerateFromImageResult(
            character_id="c1",
            image={"key": "k1", "url": "u1"},
        )
    )
    client.characters.create_from_generated_image = AsyncMock(
        return_value=CreateFromGeneratedImageResult(
            character={"id": "c1"},
            auto_rig_confidence=None,
        )
    )

    await client.characters.create_from_image(
        "path/to/ref.png",
        prompt="a knight",
        on_previews_ready=lambda previews: previews[0]["key"],
    )

    client.characters.create_from_generated_image.assert_called_once_with(
        "c1", "k1", "a knight", name=None
    )


# ---------------------------------------------------------------------------
# motions.preview (renamed from download_preview)
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
