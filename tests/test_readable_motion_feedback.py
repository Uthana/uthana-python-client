"""Shared cross-language feedback inputs and safe clear outcomes."""

import json
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest

from uthana import Uthana, UthanaError

CONTRACT = json.loads(
    (Path(__file__).parent / "fixtures/motion_feedback_contract.json").read_text()
)


@pytest.mark.parametrize("case", CONTRACT["ratings"])
@pytest.mark.asyncio
async def test_readable_and_existing_scores_send_the_same_vote(case: dict) -> None:
    client = Uthana("test", telemetry=False)
    client._graphql = AsyncMock(return_value={})
    try:
        await client.motions.rate("m1", case["input"], label_id="annotation")
        assert client._graphql.await_args.args[1] == {
            "motion_id": "m1",
            "score": case["score"],
            "label_id": "annotation",
        }
    finally:
        client.close()


@pytest.mark.parametrize("value", CONTRACT["invalid_ratings"])
@pytest.mark.asyncio
async def test_invalid_scores_never_submit(value: object) -> None:
    client = Uthana("test", telemetry=False)
    client._graphql = AsyncMock()
    try:
        with pytest.raises(ValueError, match="Motion rating score"):
            await client.motions.rate("m1", value)
        client._graphql.assert_not_awaited()
    finally:
        client.close()


def test_clear_and_favorite_sync_calls_preserve_explicit_intent() -> None:
    calls: list[dict] = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "data": {
                    "clear_motion_rating": {"ok": True},
                    "favorite_motion": {"__typename": "FavoriteMotion"},
                }
            },
        )

    client = Uthana("test", telemetry=False, transport=httpx.MockTransport(handle))
    try:
        client.motions.rate_sync("m1", None)
        client.motions.rate_sync("m1", None)
        client.motions.favorite_sync("m1")
        client.motions.favorite_sync("m1")
        client.motions.unfavorite_sync("m1")
        client.motions.unfavorite_sync("m1")
    finally:
        client.close()
    assert [call["variables"] for call in calls] == [
        {"motion_id": "m1"},
        {"motion_id": "m1"},
        {"motion_id": "m1", "favorite": True},
        {"motion_id": "m1", "favorite": True},
        {"motion_id": "m1", "favorite": False},
        {"motion_id": "m1", "favorite": False},
    ]
    assert all("clear_motion_rating(" in call["query"] for call in calls[:2])


@pytest.mark.parametrize("result", CONTRACT["invalid_clear_results"])
@pytest.mark.asyncio
async def test_ambiguous_clear_is_not_retried(result: object) -> None:
    client = Uthana("test", telemetry=False)
    client._graphql = AsyncMock(return_value=result)
    try:
        with pytest.raises(UthanaError) as error:
            await client.motions.rate("m1", None)
        assert error.value.kind == "uncertain"
        client._graphql.assert_awaited_once()
    finally:
        client.close()


@pytest.mark.asyncio
async def test_clear_rejects_annotation_selector_and_preserves_unsupported_server_error() -> None:
    client = Uthana("test", telemetry=False)
    failure = UthanaError(400, "Unknown clear_motion_rating field", kind="graphql")
    client._graphql = AsyncMock(side_effect=failure)
    try:
        with pytest.raises(ValueError, match="whole motion"):
            await client.motions.rate("m1", None, label_id="annotation")
        client._graphql.assert_not_awaited()
        with pytest.raises(UthanaError) as error:
            await client.motions.rate("m1", None)
        assert error.value is failure
        client._graphql.assert_awaited_once()
    finally:
        client.close()


@pytest.mark.parametrize("value", CONTRACT["invalid_favorites"])
@pytest.mark.asyncio
async def test_invalid_favorite_state_never_writes(value: object) -> None:
    client = Uthana("test", telemetry=False)
    client._graphql = AsyncMock()
    try:
        with pytest.raises(ValueError, match="Favorite state"):
            await client.motions.favorite("m1", value)
        client._graphql.assert_not_awaited()
    finally:
        client.close()
