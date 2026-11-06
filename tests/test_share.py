# (c) Copyright 2026 Uthana, Inc. All Rights Reserved

"""motions.share: public viewer links for people outside the organization."""

import json
from unittest.mock import AsyncMock

import httpx
import pytest

from uthana import Uthana, UthanaError
from uthana.modules.motions import (
    SHARE_IMAGE_FPS,
    SHARE_IMAGE_HEIGHT_PX,
    SHARE_IMAGE_WIDTH_PX,
)

from .test_modules import _make_client

PNG_URL = "https://uthana.com/app/share/char1/motion1/share.png"


@pytest.mark.asyncio
async def test_share_returns_public_viewer_link_without_window() -> None:
    client = _make_client()
    client._graphql = AsyncMock(return_value={"png_url": PNG_URL})

    link = await client.motions.share("char1", "motion1")

    assert link == {
        "character_id": "char1",
        "motion_id": "motion1",
        "start": 0.0,
        "end": 1.0,
        "preview_url": "https://uthana.com/app/preview/char1/motion1",
        "png_url": PNG_URL,
    }
    query, variables = client._graphql.call_args[0]
    assert "create_share_link(" in query and "png_url" in query
    assert variables == {
        "character_id": "char1",
        "motion_id": "motion1",
        "start": 0.0,
        "end": 1.0,
        "fps": SHARE_IMAGE_FPS,
        "wd": SHARE_IMAGE_WIDTH_PX,
        "ht": SHARE_IMAGE_HEIGHT_PX,
    }
    assert client._graphql.call_args.kwargs["path"] == "create_share_link"


@pytest.mark.asyncio
async def test_share_window_is_appended_with_two_decimals_and_ids_are_quoted() -> None:
    client = _make_client()
    client._graphql = AsyncMock(return_value={"png_url": PNG_URL})

    link = await client.motions.share("c/1", "m 1", start=0.125, end=0.5)

    assert link["preview_url"] == "https://uthana.com/app/preview/c%2F1/m%201?start=0.12&end=0.50"
    assert link["start"] == 0.125 and link["end"] == 0.5


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "start,end",
    [(0.5, 0.5), (0.7, 0.2), (-0.1, 1.0), (0.0, 1.5), (float("nan"), 1.0), (0.0, float("inf"))],
)
async def test_share_rejects_invalid_window(start: float, end: float) -> None:
    client = _make_client()
    client._graphql = AsyncMock()
    with pytest.raises(ValueError, match="Share window fractions"):
        await client.motions.share("char1", "motion1", start=start, end=end)
    client._graphql.assert_not_called()


@pytest.mark.asyncio
async def test_share_rejects_boolean_window_values() -> None:
    client = _make_client()
    client._graphql = AsyncMock()
    with pytest.raises(ValueError, match="Share window fractions"):
        await client.motions.share("char1", "motion1", start=False, end=True)
    client._graphql.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("data", [{}, {"png_url": None}, {"png_url": "  "}, "unexpected"])
async def test_share_without_image_url_is_uncertain(data: object) -> None:
    client = _make_client()
    client._graphql = AsyncMock(return_value=data)
    with pytest.raises(UthanaError) as error:
        await client.motions.share("char1", "motion1")
    assert error.value.kind == "uncertain"
    assert "use Share" in error.value.message


@pytest.mark.asyncio
async def test_share_sends_mutation_over_transport() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        body = json.loads(request.content)
        assert body["query"].lstrip().startswith("mutation CreateShareLink")
        assert body["variables"]["fps"] == SHARE_IMAGE_FPS
        return httpx.Response(200, json={"data": {"create_share_link": {"png_url": PNG_URL}}})

    client = Uthana(
        "synthetic-key",
        domain="staging.uthana.com",
        telemetry=False,
        trust_env=False,
        transport=httpx.MockTransport(handler),
    )
    try:
        link = await client.motions.share("char1", "motion1", timeout=5.0)
    finally:
        client.close()
    assert link["preview_url"] == "https://staging.uthana.com/app/preview/char1/motion1"
    assert requests[0].url.path == "/graphql"
    assert requests[0].extensions["timeout"]["read"] == 5.0


def test_share_sync_wraps_async() -> None:
    client = _make_client()
    client._graphql = AsyncMock(return_value={"png_url": PNG_URL})
    link = client.motions.share_sync("char1", "motion1", start=0.0, end=0.5)
    assert link["preview_url"].endswith("?start=0.00&end=0.50")
