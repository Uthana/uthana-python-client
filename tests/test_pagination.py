"""Exercise paged reads through the real transport without changing old list calls."""

import json

import httpx
import pytest

from uthana import Uthana, UthanaError


@pytest.mark.parametrize("kind", ["characters", "motions"])
@pytest.mark.asyncio
async def test_paged_reads_continue_with_opaque_cursor(kind: str) -> None:
    requests = []
    pages = [
        {"items": [{"id": "older", "name": "Walk", "created": None}], "next_cursor": "opaque+/="},
        {"items": [{"id": "oldest", "name": "Walk", "created": "2020-01-01"}], "next_cursor": None},
    ]

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={"data": {f"{kind}_paged": pages[len(requests) - 1]}})

    client = Uthana("test", telemetry=False, transport=httpx.MockTransport(handle))
    module = getattr(client, kind)
    options = {"query": "walk", "source": "mine", "order": "created_asc", "limit": 1}
    if kind == "motions":
        options["method"] = "VideoToMotion"
    try:
        first = await module.list_paged(**options)
        second = await module.list_paged(**options, cursor=first["next_cursor"])
    finally:
        client.close()
    assert first == pages[0]
    assert second == pages[1]
    assert requests[0]["variables"] == options
    assert requests[1]["variables"] == {**options, "cursor": "opaque+/="}
    assert f"{kind}_paged(" in requests[0]["query"]
    assert "org_id" in requests[0]["query"]
    assert "updated" in requests[0]["query"]


@pytest.mark.parametrize("kind", ["characters", "motions"])
def test_sync_defaults_and_legacy_list_are_separate(kind: str) -> None:
    requests = []

    def handle(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        requests.append(payload)
        data = {f"{kind}_paged": {"items": [], "next_cursor": None}, kind: []}
        return httpx.Response(200, json={"data": data})

    client = Uthana("test", telemetry=False, transport=httpx.MockTransport(handle))
    module = getattr(client, kind)
    try:
        assert module.list_paged_sync() == {"items": [], "next_cursor": None}
        assert module.list_sync() == []
    finally:
        client.close()
    assert requests[0]["variables"] == {}
    assert f"{kind}_paged(" in requests[0]["query"]
    assert f"{kind}_paged" not in requests[1]["query"]


@pytest.mark.parametrize("kind", ["characters", "motions"])
@pytest.mark.asyncio
async def test_cursor_errors_propagate_without_retry(kind: str) -> None:
    calls = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"errors": [{"message": "Invalid page cursor"}]})

    client = Uthana("test", telemetry=False, transport=httpx.MockTransport(handle))
    try:
        with pytest.raises(UthanaError, match="Invalid page cursor"):
            await getattr(client, kind).list_paged(cursor="expired", limit=100)
    finally:
        client.close()
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_explicit_empty_and_zero_options_reach_validation() -> None:
    requests = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={"errors": [{"message": "limit must be at least 1"}]})

    client = Uthana("test", telemetry=False, transport=httpx.MockTransport(handle))
    try:
        with pytest.raises(UthanaError, match="limit"):
            await client.motions.list_paged(query="", cursor="", method="", limit=0)
    finally:
        client.close()
    assert requests[0]["variables"] == {"query": "", "cursor": "", "method": "", "limit": 0}
