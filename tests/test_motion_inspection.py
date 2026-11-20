"""Motion lookup preserves the metadata shared with the JS client."""

import json

import httpx
import pytest

from uthana import Uthana


@pytest.mark.parametrize("tags", [{"Method": "TextToMotion"}, ["Walk"], None])
def test_motion_lookup_keeps_dates_tags_favorites_and_ratings(tags: object) -> None:
    calls = []
    motion = {
        "id": "m1",
        "name": "Walk",
        "org_id": "org",
        "created": None,
        "updated": "2026-01-01",
        "tags": tags,
        "favorite": {"user_id": "u1", "label_id": None, "created": None, "updated": None},
        "rating": {
            "user_id": "u1",
            "label_id": None,
            "score": 0,
            "created": "2026-01-01T00:00:00Z",
            "updated": "2026-01-02T00:00:00Z",
        },
        "assets": [{"id": "a1", "metadata": {"fps": 30}}],
    }

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content))
        return httpx.Response(200, json={"data": {"motion": motion}})

    client = Uthana("test", telemetry=False, transport=httpx.MockTransport(handle))
    try:
        assert client.motions.get_sync("m1") == motion
    finally:
        client.close()
    assert calls[0]["variables"] == {"motion_id": "m1"}
    query = calls[0]["query"]
    for field in ["created", "updated", "tags", "favorite {", "rating {", "assets {"]:
        assert field in query
    rating_fields = query.split("rating {", 1)[1].split("}", 1)[0].split()
    assert "updated" in rating_fields
