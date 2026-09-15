"""Offline contracts for image preparation/finalization and the preview loop API."""

import json

import httpx
import pytest

from tests.test_workflow_capabilities import multipart
from uthana import Uthana
from uthana.graphql import q
from uthana.types import UthanaError


def client_for(handler):
    return Uthana(
        "synthetic", telemetry=False, trust_env=False, transport=httpx.MockTransport(handler)
    )


@pytest.mark.asyncio
async def test_loop_defaults_and_explicit_target():
    calls = []

    def handler(request):
        calls.append((json.loads(request.content), request.extensions["timeout"]))
        return httpx.Response(
            200,
            json={"data": {"create_looped_motion": {"motion": {"id": "loop1", "name": "Loop"}}}},
        )

    client = client_for(handler)
    assert (await client.motions.create_looped_motion("char1", "motion1"))["id"] == "loop1"
    assert calls[0][0]["query"] == q.CREATE_LOOPED_MOTION
    assert calls[0][0]["variables"] == {
        "character_id": "char1",
        "motion_id": "motion1",
        "trim_start_pct": 0.0,
        "trim_end_pct": 1.0,
        "zone_duration": 2.0,
        "loop_mode": "closed",
        "zone_mode": "modify",
        "zone_end_position": None,
    }
    target = {"x": 2.0, "y": -1.0, "facing_angle": 0.25}
    await client.motions.create_looped_motion(
        "char1",
        "motion1",
        loop_mode="open",
        zone_mode="extend",
        trim_start_pct=0.1,
        trim_end_pct=0.9,
        zone_duration=1.0,
        zone_end_position=target,
        timeout=httpx.Timeout(360, connect=15),
    )
    assert calls[1][0]["variables"]["zone_end_position"] == target
    assert calls[1][1]["read"] == 360 and calls[1][1]["connect"] == 15
    client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kwargs",
    [
        {"trim_start_pct": True},
        {"trim_end_pct": float("nan")},
        {"trim_start_pct": 1},
        {"trim_end_pct": 1.1},
        {"zone_duration": 0},
        {"zone_duration": float("inf")},
        {"zone_duration": "2"},
        {"loop_mode": "cyclical"},
        {"zone_mode": "invalid"},
        {"zone_end_position": {"x": 0, "y": 0}},
        {"loop_mode": "open", "zone_end_position": {"x": 0}},
        {"loop_mode": "open", "zone_end_position": {"x": 0, "y": False}},
        {"loop_mode": "open", "zone_end_position": {"x": 0, "y": 0, "extra": 1}},
    ],
)
async def test_loop_invalid_inputs_do_not_submit(kwargs):
    def handler(request):
        pytest.fail("Invalid input reached the API")

    client = client_for(handler)
    with pytest.raises(ValueError):
        await client.motions.create_looped_motion("char1", "motion1", **kwargs)
    client.close()


@pytest.mark.asyncio
async def test_image_preparation_is_separate_from_finalization():
    calls = []

    def handler(request):
        calls.append(request)
        if "multipart/" in request.headers.get("content-type", ""):
            operation, mapping, content, filename = multipart(request)
            assert operation["query"] == q.CREATE_IMAGE_FROM_IMAGE
            assert mapping == {"0": ["variables.file"]}
            assert content == b"image-snapshot" and filename == "reference.png"
            assert request.extensions["timeout"]["read"] == 360
            return httpx.Response(
                200,
                json={
                    "data": {
                        "create_image_from_image": {
                            "character_id": "char1",
                            "image": {
                                "key": "char1-front.png",
                                "url": "https://example.invalid/image",
                            },
                        }
                    }
                },
            )
        document = json.loads(request.content)
        assert document["query"] == q.CREATE_CHARACTER_FROM_IMAGE
        assert document["variables"] == {
            "character_id": "char1",
            "image_key": "char1-front.png",
            "prompt": "",
            "name": "Hero",
            "include_fingers": True,
        }
        assert request.extensions["timeout"]["read"] == 660
        return httpx.Response(
            200,
            json={
                "data": {
                    "create_character_from_image": {
                        "character": {"id": "char1", "name": "Hero"},
                        "auto_rig_confidence": 0.95,
                    }
                }
            },
        )

    client = client_for(handler)
    prepared = await client.characters.prepare_from_image_bytes(
        "reference.png",
        b"image-snapshot",
        timeout=httpx.Timeout(360, connect=15),
    )
    assert len(calls) == 1 and prepared.character_id == "char1"
    result = await client.characters.generate_from_image(
        prepared,
        prepared.previews[0]["key"],
        name="Hero",
        include_fingers=True,
        timeout=httpx.Timeout(660, connect=15),
    )
    assert len(calls) == 2 and result.character["id"] == "char1"
    client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "filename, content, limit",
    [
        ("ref.gif", b"abc", 10),
        ("ref.png", b"", 10),
        ("ref.jpg", b"abc", 2),
        ("ref.jpeg", "abc", 10),
        ("ref.png", b"a", False),
    ],
)
async def test_invalid_image_snapshots_do_not_submit(filename, content, limit):
    client = client_for(lambda _: pytest.fail("Invalid snapshot reached the API"))
    with pytest.raises(ValueError):
        await client.characters.prepare_from_image_bytes(filename, content, max_bytes=limit)
    client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "data", [None, {}, {"character_id": "char1", "image": {}}, {"image": {"key": "a"}}]
)
async def test_malformed_preparation_does_not_finalize(data):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"data": {"create_image_from_image": data}})

    client = client_for(handler)
    with pytest.raises(UthanaError):
        await client.characters.prepare_from_image_bytes("ref.png", b"abc")
    assert len(calls) == 1
    client.close()


def test_sync_wrappers():
    def handler(request):
        if "multipart/" in request.headers.get("content-type", ""):
            return httpx.Response(
                200,
                json={
                    "data": {
                        "create_image_from_image": {
                            "character_id": "char1",
                            "image": {"key": "char1-front.png"},
                        }
                    }
                },
            )
        if json.loads(request.content)["query"] == q.CREATE_LOOPED_MOTION:
            return httpx.Response(
                200, json={"data": {"create_looped_motion": {"motion": {"id": "loop1"}}}}
            )
        return httpx.Response(
            200, json={"data": {"create_character_from_image": {"character": {"id": "char1"}}}}
        )

    client = client_for(handler)
    prepared = client.characters.prepare_from_image_bytes_sync("ref.png", b"abc")
    assert (
        client.characters.generate_from_image_sync(
            prepared, prepared.previews[0]["key"], name="Hero"
        ).character["id"]
        == "char1"
    )
    assert client.motions.create_looped_motion_sync("char1", "motion1")["id"] == "loop1"
    client.close()
