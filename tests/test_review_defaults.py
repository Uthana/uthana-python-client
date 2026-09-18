"""Review regressions for synchronous ML deadlines and missing result receipts."""

import json

import httpx
import pytest

from tests.test_stitch import clip
from uthana import CharacterPreviewResult, StitchParams, Uthana, UthanaError
from uthana.stitch import StitchParams as SubmoduleStitchParams


def invocation(client, operation, sync, kwargs):
    if operation == "prepare":
        method = (
            client.characters.prepare_from_image_bytes_sync
            if sync
            else client.characters.prepare_from_image_bytes
        )
        return method("reference.png", b"image-snapshot", **kwargs)
    if operation == "generate":
        method = (
            client.characters.generate_from_image_sync
            if sync
            else client.characters.generate_from_image
        )
        pending = CharacterPreviewResult(
            character_id="char1", previews=[{"key": "image1"}], prompt=""
        )
        return method(pending, "image1", **kwargs)
    if operation == "loop":
        method = (
            client.motions.create_looped_motion_sync
            if sync
            else client.motions.create_looped_motion
        )
        return method("char1", "motion1", **kwargs)
    method = (
        client.motions.create_stitched_motion_sync
        if sync
        else client.motions.create_stitched_motion
    )
    return method("char1", clip(), clip("motion2"), **kwargs)


def configured_client(operation, mode):
    requests = []
    fields = {
        "prepare": (
            "create_image_from_image",
            {"character_id": "char1", "image": {"key": "image1"}},
        ),
        "generate": ("create_character_from_image", {"character": {"id": "char1"}}),
        "loop": ("create_looped_motion", {"motion": {"id": "motion1"}}),
        "stitch": ("create_enhanced_stitched_motion", {"motion": {"id": "motion1"}}),
    }
    field, receipt = fields[operation]

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"data": {field: receipt}})

    custom = httpx.Timeout(connect=4, read=55, write=66, pool=7)
    kwargs = (
        {}
        if mode == "omitted"
        else {"timeout": {"none": None, "seconds": 77.0, "custom": custom}[mode]}
    )
    phase = 660 if operation == "generate" else 360
    expected: dict[str, float] = {"read": phase, "write": phase, "pool": phase, "connect": 15}
    if mode == "seconds":
        expected = {name: 77.0 for name in expected}
    elif mode == "custom":
        expected = {"read": 55, "write": 66, "pool": 7, "connect": 4}
    client = Uthana(
        "synthetic",
        telemetry=False,
        trust_env=False,
        timeout=9,
        transport=httpx.MockTransport(handler),
    )
    return client, requests, kwargs, expected


@pytest.mark.parametrize("operation", ["prepare", "generate", "loop", "stitch"])
@pytest.mark.parametrize("mode", ["omitted", "none", "seconds", "custom"])
async def test_async_operation_deadlines(operation, mode):
    client, requests, kwargs, expected = configured_client(operation, mode)
    try:
        await invocation(client, operation, False, kwargs)
        assert len(requests) == 1
        assert requests[0].extensions["timeout"] == expected
    finally:
        client.close()


@pytest.mark.parametrize("operation", ["prepare", "generate", "loop", "stitch"])
@pytest.mark.parametrize("mode", ["omitted", "none", "seconds", "custom"])
def test_sync_operation_deadlines(operation, mode):
    client, requests, kwargs, expected = configured_client(operation, mode)
    try:
        invocation(client, operation, True, kwargs)
        assert len(requests) == 1
        assert requests[0].extensions["timeout"] == expected
    finally:
        client.close()


@pytest.mark.parametrize("operation", ["loop", "stitch"])
@pytest.mark.parametrize(
    "receipt",
    [
        None,
        {},
        {"motion": None},
        {"motion": {}},
        {"motion": []},
        {"motion": {"id": ""}},
        {"motion": {"id": "  "}},
        {"motion": {"id": 42}},
        {"motion": {"id": False}},
    ],
)
async def test_missing_motion_receipt_is_uncertain_without_retry(operation, receipt):
    calls = []
    field = "create_looped_motion" if operation == "loop" else "create_enhanced_stitched_motion"

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"data": {field: receipt}})

    client = Uthana(
        "synthetic", telemetry=False, trust_env=False, transport=httpx.MockTransport(handler)
    )
    try:
        with pytest.raises(UthanaError, match="may have succeeded") as error:
            await invocation(client, operation, False, {})
        assert error.value.kind == "uncertain"
        assert "before resubmitting" in str(error.value)
        assert len(calls) == 1
    finally:
        client.close()


@pytest.mark.parametrize("operation", ["loop", "stitch"])
async def test_graphql_errors_are_not_hidden_by_motion_receipt_guard(operation):
    envelope = {"errors": [{"message": "Example provider error"}], "data": None}
    calls = []

    def handler(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200, json=envelope)

    client = Uthana(
        "synthetic", telemetry=False, trust_env=False, transport=httpx.MockTransport(handler)
    )
    try:
        with pytest.raises(UthanaError) as error:
            await invocation(client, operation, False, {})
        assert error.value.kind == "graphql"
        assert error.value.response_data == envelope
        assert len(calls) == 1
    finally:
        client.close()


@pytest.mark.parametrize("limit", [None, 0, -1, True, 2.5, "100"])
async def test_image_preparation_requires_positive_integer_bound(limit):
    client = Uthana(
        "synthetic",
        telemetry=False,
        trust_env=False,
        transport=httpx.MockTransport(lambda _: pytest.fail("Invalid limit reached network")),
    )
    try:
        with pytest.raises(ValueError, match="positive max_bytes"):
            await client.characters.prepare_from_image_bytes("ref.png", b"image", max_bytes=limit)
    finally:
        client.close()


def test_stitch_params_public_export_is_the_documented_type():
    assert StitchParams is SubmoduleStitchParams
