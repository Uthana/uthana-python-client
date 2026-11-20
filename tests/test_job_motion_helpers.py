"""Public parity helpers poll/read existing work and send only intentional ratings."""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from uthana import Uthana, UthanaError


def make_client() -> Uthana:
    return Uthana("test", telemetry=False)


@pytest.mark.asyncio
async def test_wait_polls_same_job_and_preserves_finished_result() -> None:
    client = make_client()
    final = {"id": "j1", "status": "FINISHED", "result": {"result": {"id": "m1"}}}
    client.jobs.get = AsyncMock(side_effect=[{"status": "READY"}, final])
    try:
        with patch("uthana.modules.jobs.asyncio.sleep", new_callable=AsyncMock) as sleep:
            assert await client.jobs.wait("j1", interval_seconds=1, timeout_seconds=10) == final
        sleep.assert_awaited_once_with(1)
        assert client.jobs.get.await_args_list[0].args == ("j1",)
        assert client.jobs.get.await_args_list[1].args == ("j1",)
    finally:
        client.close()


@pytest.mark.asyncio
async def test_wait_reports_failure_without_resubmitting() -> None:
    client = make_client()
    client.jobs.get = AsyncMock(
        return_value={"status": "FAILED", "result": {"message": "Failed inference"}}
    )
    try:
        with pytest.raises(UthanaError, match="Failed inference") as error:
            await client.jobs.wait("j1")
        assert error.value.status_code == 500
        client.jobs.get.assert_awaited_once_with("j1")
    finally:
        client.close()


@pytest.mark.parametrize(
    "job,status_code",
    [
        (None, 404),
        ({}, 404),
        ({"id": "j1"}, 502),
        ({"status": None}, 502),
        ({"status": 42}, 502),
        ({"status": True}, 502),
        ({"status": ""}, 502),
        ({"status": " "}, 502),
    ],
)
@pytest.mark.asyncio
async def test_wait_stops_on_missing_job_or_invalid_status(job: object, status_code: int) -> None:
    calls: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"data": {"job": job}})

    client = Uthana("test", telemetry=False, transport=httpx.MockTransport(handle))
    try:
        with pytest.raises(UthanaError, match="Job j1") as error:
            await client.jobs.wait("j1", timeout_seconds=1)
        assert error.value.status_code == status_code
        if status_code == 502:
            assert error.value.kind == "invalid_response"
        assert len(calls) == 1
    finally:
        client.close()


@pytest.mark.asyncio
async def test_wait_deadline_cancels_a_slow_read_and_keeps_job_identity() -> None:
    client = make_client()
    cancelled = []

    async def slow_get(job_id: str):
        try:
            await asyncio.Future()
        finally:
            cancelled.append(job_id)

    client.jobs.get = slow_get
    try:
        with pytest.raises(UthanaError, match="Job j1 did not finish") as error:
            await client.jobs.wait("j1", timeout_seconds=0.01)
        assert error.value.status_code == 408
        assert cancelled == ["j1"]
    finally:
        client.close()


@pytest.mark.parametrize("option", ["interval_seconds", "timeout_seconds"])
@pytest.mark.parametrize("value", [0, -1, True, float("inf"), float("nan"), "1"])
@pytest.mark.asyncio
async def test_wait_rejects_invalid_timing_before_read(option: str, value: object) -> None:
    client = make_client()
    client.jobs.get = AsyncMock()
    try:
        with pytest.raises(ValueError, match=option):
            await client.jobs.wait("j1", **{option: value})
        client.jobs.get.assert_not_awaited()
    finally:
        client.close()


def test_wait_sync_handles_httpx_timeout_configuration() -> None:
    client = Uthana("test", telemetry=False, timeout=httpx.Timeout(None))
    client.jobs.get = AsyncMock(return_value={"id": "j1", "status": "FINISHED"})
    try:
        assert client.jobs.wait_sync("j1")["id"] == "j1"
    finally:
        client.close()


@pytest.mark.parametrize("score", [0, 1])
@pytest.mark.asyncio
async def test_rate_sends_selected_score_and_label(score: int) -> None:
    calls = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content))
        return httpx.Response(
            200, json={"data": {"rate_motion": {"motion_rating": {"score": score}}}}
        )

    client = Uthana("test", telemetry=False, transport=httpx.MockTransport(handle))
    try:
        assert await client.motions.rate("m1", score, label_id="l1") is None
    finally:
        client.close()
    assert calls[0]["variables"] == {"motion_id": "m1", "score": score, "label_id": "l1"}
    assert "rate_motion(" in calls[0]["query"]


@pytest.mark.parametrize("score", [-1, 2, True, 0.0, "1", None])
@pytest.mark.asyncio
async def test_rating_validation_prevents_submission(score: object) -> None:
    client = make_client()
    client._graphql = AsyncMock()
    try:
        with pytest.raises(ValueError, match="score must be 0 or 1"):
            await client.motions.rate("m1", score)
        client._graphql.assert_not_called()
    finally:
        client.close()


def test_download_history_and_rating_sync_wrappers() -> None:
    payload = [
        {"motion_id": "m1", "character_id": "c1", "secs": 0, "created": None, "motion": None}
    ]
    queries = []

    def handle(request: httpx.Request) -> httpx.Response:
        query = json.loads(request.content)["query"]
        queries.append(query)
        return httpx.Response(200, json={"data": {"motion_downloads": payload, "rate_motion": {}}})

    client = Uthana("test", telemetry=False, transport=httpx.MockTransport(handle))
    try:
        assert client.motions.list_downloads_sync() == payload
        assert client.motions.rate_sync("m1", 1) is None
    finally:
        client.close()
    assert "motion_downloads" in queries[0]
    assert "rate_motion" in queries[1]


@pytest.mark.parametrize("is_favorite", [True, False])
@pytest.mark.asyncio
async def test_favorite_sends_explicit_state(is_favorite: bool) -> None:
    calls: list[dict] = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content))
        return httpx.Response(
            200, json={"data": {"favorite_motion": {"__typename": "FavoriteMotion"}}}
        )

    client = Uthana("test", telemetry=False, transport=httpx.MockTransport(handle))
    try:
        assert await client.motions.favorite("m1", is_favorite) is None
    finally:
        client.close()
    assert len(calls) == 1
    assert calls[0]["variables"] == {"motion_id": "m1", "favorite": is_favorite}
    assert "favorite_motion(" in calls[0]["query"]
    assert "motion_favorite {" not in calls[0]["query"]


def test_favorite_sync_repeats_the_state_without_toggling() -> None:
    calls: list[dict] = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content))
        return httpx.Response(
            200, json={"data": {"favorite_motion": {"__typename": "FavoriteMotion"}}}
        )

    client = Uthana("test", telemetry=False, transport=httpx.MockTransport(handle))
    try:
        client.motions.favorite_sync("m1", True)
        client.motions.favorite_sync("m1", True)
        client.motions.favorite_sync("m1", False)
    finally:
        client.close()
    assert [call["variables"]["favorite"] for call in calls] == [True, True, False]
