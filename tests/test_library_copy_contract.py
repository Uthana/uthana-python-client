"""Shared Python/JS acceptance and recovery cases for paid library copies."""

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from uthana import Uthana, UthanaError

CONTRACT = json.loads((Path(__file__).parent / "fixtures/library_copy_contract.json").read_text())


@pytest.mark.parametrize("payload", CONTRACT["invalid_results"])
@pytest.mark.asyncio
async def test_malformed_paid_results_remain_uncertain(payload: object) -> None:
    client = Uthana("test", telemetry=False)
    client._graphql = AsyncMock(return_value=payload)
    try:
        with pytest.raises(UthanaError) as error:
            await client.ttm.copy_from_library("walk")
        assert error.value.kind == "uncertain"
        client._graphql.assert_awaited_once()
    finally:
        client.close()


@pytest.mark.parametrize("case", CONTRACT["valid_results"])
@pytest.mark.asyncio
async def test_valid_copy_metadata(case: dict) -> None:
    client = Uthana("test", telemetry=False)
    client._graphql = AsyncMock(return_value=case["response"])
    try:
        result = await client.ttm.copy_from_library("walk")
        assert result.motion_id == case["motion_id"]
        assert result.name == case["name"]
        assert result.match_score == case["match_score"]
    finally:
        client.close()


@pytest.mark.parametrize(
    "tags",
    CONTRACT["unknown_score_tags"]
    + [{"Distance": float("inf")}, {"Distance": float("nan")}, {"Distance": 10**1000}],
)
@pytest.mark.asyncio
async def test_unusable_scores_are_unknown(tags: object) -> None:
    client = Uthana("test", telemetry=False)
    client._graphql = AsyncMock(return_value={"motion": {"id": "m1", "tags": tags}})
    try:
        assert (await client.ttm.copy_from_library("walk")).match_score is None
        client._graphql.assert_awaited_once()
    finally:
        client.close()
