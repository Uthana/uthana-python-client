"""Motion lookup requests personal feedback without internal identity fields."""

import json

import httpx
import pytest

from uthana import Uthana


@pytest.mark.parametrize("has_feedback", [True, False])
@pytest.mark.parametrize("tags", [{"Method": "TextToMotion"}, ["Walk"], None])
def test_motion_lookup_keeps_dates_tags_favorites_and_ratings(
    tags: object, has_feedback: bool
) -> None:
    calls = []
    motion = {
        "id": "m1",
        "name": "Walk",
        "org_id": "org",
        "created": None,
        "updated": "2026-01-01",
        "tags": tags,
        "favorite": {"created": None, "updated": None} if has_feedback else None,
        "rating": {
            "score": 0,
            "created": "2026-01-01T00:00:00Z",
            "updated": "2026-01-02T00:00:00Z",
        }
        if has_feedback
        else None,
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
    assert "user_id" not in query
    assert "label_id" not in query
