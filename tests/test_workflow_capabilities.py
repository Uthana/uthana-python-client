# (c) Copyright 2026 Uthana, Inc. All Rights Reserved

"""Public SDK workflows exercise shared HTTP transport with synthetic responses."""

import json
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Awaitable, Callable, Literal, cast
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from uthana import Uthana
from uthana.graphql import q
from uthana.types import UthanaError


def client_for(handler) -> Uthana:
    return Uthana(
        "synthetic-key",
        domain="staging.uthana.com",
        telemetry=False,
        transport=httpx.MockTransport(handler),
        trust_env=False,
    )


def multipart(request: httpx.Request) -> tuple[dict, dict, bytes, str]:
    body = request.read()
    message = BytesParser(policy=policy.default).parsebytes(
        b"Content-Type: " + request.headers["content-type"].encode() + b"\r\n\r\n" + body
    )
    parts = {p.get_param("name", header="content-disposition"): p for p in message.iter_parts()}
    operation_bytes = parts["operations"].get_payload(decode=True)
    mapping_bytes = parts["map"].get_payload(decode=True)
    content = parts["0"].get_payload(decode=True)
    filename = parts["0"].get_filename()
    assert isinstance(operation_bytes, bytes)
    assert isinstance(mapping_bytes, bytes)
    assert isinstance(content, bytes)
    assert isinstance(filename, str)
    return json.loads(operation_bytes), json.loads(mapping_bytes), content, filename


@pytest.mark.asyncio
async def test_motion_metadata_catalog_and_trim_contracts() -> None:
    requests = []
    motion = {"id": "motion1", "name": "Walk", "assets": [{"uid": "bundle", "metadata": {}}]}
    catalog = {"org": {"id": "org1"}, "motions": [{"id": "motion1", "tags": ["walk"]}]}

    def handler(request):
        document = json.loads(request.content)
        requests.append(document)
        if document["query"] == q.GET_MOTION:
            return httpx.Response(200, json={"data": {"motion": motion}})
        if document["query"] == q.MOTION_CATALOG:
            return httpx.Response(200, json={"data": catalog})
        return httpx.Response(
            200, json={"data": {"trim_and_loop_motion": {"motion": {"id": "trim1"}}}}
        )

    client = client_for(handler)
    assert await client.motions.get("motion1") == motion
    assert await client.motions.catalog() == catalog
    assert await client.motions.trim("motion1", 0.25, 0.75, "Edited walk") == {"id": "trim1"}
    assert requests[0]["variables"] == {"motion_id": "motion1"}
    assert requests[2]["variables"] == {
        "motion_id": "motion1",
        "start": 0.25,
        "end": 0.75,
        "name": "Edited walk",
    }
    assert "loop: false" in requests[2]["query"]
    assert 'app_ids: ["motion_viewer"]' in requests[1]["query"]
    client.close()


@pytest.mark.asyncio
async def test_catalog_does_not_change_existing_simple_list() -> None:
    client = client_for(lambda _: httpx.Response(200, json={"data": {"motions": []}}))
    assert await client.motions.list() == []
    client.close()


@pytest.mark.asyncio
async def test_export_options_and_preview_endpoint() -> None:
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, content=b"asset")

    client = client_for(handler)
    assert (
        await client.motions.download(
            "char1",
            "motion1",
            output_format="bvh",
            fps=30,
            no_mesh=False,
            in_place=True,
            roblox_compatible=True,
            speed_multiplier=1.25,
            torso_only=True,
            max_bytes=10,
        )
        == b"asset"
    )
    params = dict(requests[0].url.params)
    assert params == {
        "fps": "30",
        "no_mesh": "false",
        "in_place": "true",
        "roblox_compatible": "true",
        "speed_multiplier": "1.25",
        "torso_only": "true",
    }
    assert requests[0].url.path.endswith("/bvh/char1-motion1.bvh")
    assert await client.motions.preview("char1", "motion1", format="apng", max_bytes=10) == b"asset"
    assert requests[1].url.path == "/app/preview/char1/motion1/preview.png"
    assert not requests[1].url.query
    assert await client.motions.preview("char1", "motion1") == b"asset"
    assert requests[2].url.path.endswith("preview.webm")
    assert requests[2].extensions["timeout"]["read"] == 60.0
    client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["preview", "download"])
async def test_asset_methods_enforce_size_bound(method: str) -> None:
    client = client_for(lambda _: httpx.Response(200, content=b"oversized"))
    with pytest.raises(UthanaError) as error:
        await getattr(client.motions, method)("char1", "motion1", max_bytes=3)
    assert error.value.kind == "response_too_large"
    client.close()


@pytest.mark.asyncio
async def test_preview_invalid_format_never_requests_network() -> None:
    client = client_for(lambda _: pytest.fail("Unexpected HTTP request"))
    with pytest.raises(ValueError, match="Preview format"):
        await client.motions.preview(
            "char1", "motion1", format=cast(Literal["webm", "apng"], "gif")
        )
    client.close()


@pytest.mark.asyncio
async def test_bake_includes_source_only_when_provided() -> None:
    variables = []

    def handler(request):
        payload = json.loads(request.content)
        variables.append(payload["variables"])
        assert "motion_id: $sourceMotionId" in payload["query"]
        return httpx.Response(
            200, json={"data": {"create_motion_from_gltf": {"motion": {"id": "saved"}}}}
        )

    client = client_for(handler)
    result = await client.motions.bake_with_changes(
        '{"asset":{"version":"2.0"}}', "Save", character_id="char1", source_motion_id="motion1"
    )
    assert result.motion_id == "saved"
    assert result.character_id == "char1"
    assert variables[0]["sourceMotionId"] == "motion1"
    await client.motions.bake_with_changes("{}", "Old caller")
    assert "sourceMotionId" not in variables[1]
    client.close()


@pytest.mark.asyncio
async def test_character_snapshot_warning_name_and_timeout() -> None:
    captured = []

    def handler(request):
        captured.append((request, multipart(request)))
        return httpx.Response(
            200,
            json={
                "data": {
                    "create_character": {
                        "character": {"id": "char1", "name": "Uploaded"},
                        "auto_rig_confidence": 0.75,
                        "message": "FBX compatibility warning",
                    }
                }
            },
        )

    client = client_for(handler)
    content = b"Kaydara FBX Binary  snapshot"
    result = await client.characters.create_from_bytes(
        "character.fbx",
        content,
        name="  Armure é  ",
        auto_rig=False,
        front_facing=True,
        rerig_target="humanoid",
        include_fingers=True,
    )
    request, (operation, mapping, actual_content, filename) = captured[0]
    assert actual_content == content
    assert filename == "character.fbx"
    assert mapping == {"0": ["variables.file"]}
    assert operation["variables"] == {
        "name": "  Armure é  ",
        "file": None,
        "auto_rig": False,
        "auto_rig_front_facing": True,
        "rerig_target": "humanoid",
        "include_fingers": True,
    }
    assert "message" in operation["query"]
    assert request.extensions["timeout"]["read"] == 360
    assert request.extensions["timeout"]["connect"] == 15
    assert result.character_id == "char1"
    assert result.message == "FBX compatibility warning"
    assert result.auto_rig_confidence == 0.75
    assert result.url.endswith("/char1/character.fbx")
    client.close()


@pytest.mark.asyncio
async def test_character_file_reuses_snapshot_and_detected_format(tmp_path: Path) -> None:
    source = tmp_path / "mesh.data"
    snapshot = b"glTF" + b"0" * 30
    source.write_bytes(snapshot)
    client = client_for(lambda _: pytest.fail("Unexpected HTTP request"))
    upload = AsyncMock(return_value="result")
    with patch.object(client.characters, "create_from_bytes", upload):
        assert await client.characters.create_from_file(str(source), max_bytes=100) == "result"
    assert upload.await_args is not None
    assert upload.await_args.args == ("mesh.glb", snapshot)
    assert upload.await_args.kwargs["name"] == "mesh"
    client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("max_bytes", [0, -1, True, 1.5])
async def test_upload_invalid_bound_before_read_or_network(max_bytes) -> None:
    client = client_for(lambda _: pytest.fail("Unexpected HTTP request"))
    calls: list[tuple[Callable[..., Awaitable[object]], tuple]] = [
        (client.characters.create_from_bytes, ("char.glb", b"123")),
        (client.characters.create_from_file, ("missing.glb",)),
        (client.vtm.create_from_bytes, ("clip.mp4", b"123")),
        (client.vtm.create, ("missing.mp4",)),
    ]
    for method, args in calls:
        with pytest.raises(ValueError, match="positive integer"):
            await method(*args, max_bytes=max_bytes)
    client.close()


@pytest.mark.asyncio
async def test_upload_bytes_limits_before_network() -> None:
    client = client_for(lambda _: pytest.fail("Unexpected HTTP request"))
    calls: list[tuple[Callable[..., Awaitable[object]], str]] = [
        (client.characters.create_from_bytes, "char.glb"),
        (client.vtm.create_from_bytes, "clip.mp4"),
    ]
    for method, filename in calls:
        with pytest.raises(ValueError, match="exceeds"):
            await method(filename, b"1234", max_bytes=3)
        with pytest.raises(ValueError, match="nonempty bytes"):
            await method(filename, b"")
    client.close()


@pytest.mark.asyncio
async def test_video_snapshot_alias_webm_and_explicit_name() -> None:
    captured = []

    def handler(request):
        captured.append(multipart(request))
        return httpx.Response(
            200,
            json={
                "data": {
                    "create_video_to_motion": {
                        "job": {"id": "job1", "status": "PENDING", "model": "video-to-motion-2.0"}
                    }
                }
            },
        )

    client = client_for(handler)
    result = await client.vtm.create_from_bytes(
        "clip.webm", b"snapshot", motion_name="  Name é  ", model="video-to-motion-v2"
    )
    operation, mapping, content, filename = captured[0]
    assert operation["variables"] == {
        "file": None,
        "motion_name": "  Name é  ",
        "model": "video-to-motion-2.0",
    }
    assert mapping == {"0": ["variables.file"]}
    assert filename == "clip.webm"
    assert content == b"snapshot"
    assert result == {"id": "job1", "status": "PENDING", "model": "video-to-motion-2.0"}
    client.close()


@pytest.mark.asyncio
async def test_video_file_reuses_snapshot(tmp_path: Path) -> None:
    source = tmp_path / "video.mov"
    source.write_bytes(b"snapshot")
    client = client_for(lambda _: pytest.fail("Unexpected HTTP request"))
    upload = AsyncMock(return_value={"id": "job1"})
    with patch.object(client.vtm, "create_from_bytes", upload):
        assert await client.vtm.create(str(source), max_bytes=100) == {"id": "job1"}
    assert upload.await_args is not None
    assert upload.await_args.args == ("video.mov", b"snapshot")
    assert upload.await_args.kwargs["motion_name"] == "video"
    client.close()


@pytest.mark.asyncio
async def test_usage_prices_and_download_allowed_are_read_queries() -> None:
    captured = []
    prices = [{"model_key": "model", "billing_unit": "second", "unit_price": 0.1}]
    usage = {"org": {"payg_total_usd": 5}, "subscription": None, "payg_prices": prices}

    def handler(request):
        payload = json.loads(request.content)
        captured.append(payload)
        data: dict
        if payload["query"] == q.GET_USAGE:
            data = usage
        elif payload["query"] == q.GET_PRICES:
            data = {"payg_prices": prices}
        else:
            data = {"motion_download_allowed": {"allowed": False, "reason": "quota"}}
        return httpx.Response(200, json={"data": data})

    client = client_for(handler)
    assert await client.org.get_usage() == usage
    assert await client.org.get_prices() == prices
    assert await client.motions.download_allowed("motion1", "char1") == {
        "allowed": False,
        "reason": "quota",
    }
    assert captured[2]["variables"] == {"motion_id": "motion1", "character_id": "char1"}
    assert all(payload["query"].lstrip().startswith("query") for payload in captured)
    client.close()


@pytest.mark.asyncio
async def test_character_metadata_route_and_response() -> None:
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"bones": ["root"]})

    client = client_for(handler)
    assert await client.characters.metadata("char1") == {"bones": ["root"]}
    assert requests[0].url.path == "/motion/metadata/char1"
    assert requests[0].method == "GET"
    client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [b"null", b"[]", b"bad json", b"\xff"])
async def test_character_metadata_rejects_invalid_json(body: bytes) -> None:
    client = client_for(lambda _: httpx.Response(200, content=body))
    with pytest.raises(UthanaError, match="Invalid character metadata"):
        await client.characters.metadata("char1")
    client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "start,end",
    [
        (-0.1, 1),
        (0, 1.1),
        (0.5, 0.5),
        (0.9, 0.1),
        (float("nan"), 1),
        (0, float("inf")),
        (True, 1),
        (0, False),
    ],
)
async def test_trim_rejects_invalid_fractions_before_network(start: float, end: float) -> None:
    client = client_for(lambda _: pytest.fail("Unexpected HTTP request"))
    with pytest.raises(ValueError, match="Trim fractions"):
        await client.motions.trim("motion1", start, end, "Trim")
    client.close()


@pytest.mark.asyncio
async def test_image_upload_and_finalization_use_configured_transport(tmp_path: Path) -> None:
    source = tmp_path / "reference.png"
    snapshot = b"\x89PNG\r\n\x1a\nreference"
    source.write_bytes(snapshot)
    requests = []

    def handler(request):
        requests.append(request)
        data: dict
        if len(requests) == 1:
            operation, _, content, filename = multipart(request)
            assert operation["query"] == q.CREATE_IMAGE_FROM_IMAGE
            assert content == snapshot
            assert filename == "reference.png"
            data = {
                "create_image_from_image": {"character_id": "char1", "image": {"key": "image1"}}
            }
        else:
            operation = json.loads(request.content)
            assert operation["variables"]["name"] == "Character"
            data = {
                "create_character_from_image": {
                    "character": {"id": "char1"},
                    "auto_rig_confidence": 0.9,
                }
            }
        return httpx.Response(200, json={"data": data})

    client = client_for(handler)
    result = await client.characters.create_from_image(str(source), name="Character")
    assert result.character == {"id": "char1"}
    assert len(requests) == 2
    client.close()


@pytest.mark.asyncio
async def test_character_download_uses_shared_bounded_transport() -> None:
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, content=b"character-data")

    client = client_for(handler)
    with pytest.raises(UthanaError) as error:
        await client.characters.download("char1", max_bytes=3)
    assert error.value.kind == "response_too_large"
    assert requests[0].url.path == "/motion/bundle/char1/character.glb"
    client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["character", "video", "image"])
async def test_legacy_file_upload_keeps_open_stream_without_default_cap(
    tmp_path: Path, kind: str
) -> None:
    """A sparse input over128MiB reaches multipart without being buffered or rejected."""
    suffix = {"character": ".glb", "video": ".mp4", "image": ".png"}[kind]
    source = tmp_path / ("source" + suffix)
    with source.open("wb") as output:
        output.write(b"glTF" if kind == "character" else b"test")
        output.truncate(128 * 1024 * 1024 + 1)
    observed = []

    async def graphql(query, variables=None, **kwargs):
        if "upload" in kwargs:
            filename, stream = kwargs["upload"]
            assert filename == "source" + suffix
            assert not isinstance(stream, bytes)
            assert stream.name == str(source)
            assert not stream.closed
            assert stream.tell() == 0
            if kind == "character":
                assert kwargs["timeout"] is None
            observed.append(stream)
        if kind == "character":
            return {"create_character": {"character": {"id": "char1"}}}
        if kind == "video":
            return {"id": "job1"}
        if query == q.CREATE_IMAGE_FROM_IMAGE:
            return {"character_id": "char1", "image": {"key": "image1"}}
        return {"character": {"id": "char1"}}

    client = client_for(lambda _: pytest.fail("Unexpected HTTP request"))
    with patch.object(client, "_graphql", side_effect=graphql):
        if kind == "character":
            await client.characters.create_from_file(str(source))
        elif kind == "video":
            await client.vtm.create(str(source))
        else:
            await client.characters.create_from_image(str(source))
    assert len(observed) == 1
    assert observed[0].closed
    client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("max_bytes", [None, 100])
@pytest.mark.parametrize("override", [None, 75.0])
async def test_legacy_character_file_preserves_client_timeout(
    tmp_path: Path, max_bytes: int | None, override: float | None
) -> None:
    source = tmp_path / "character.glb"
    source.write_bytes(b"glTF" + b"0" * 30)
    observed = []

    def handler(request):
        observed.append(request.extensions["timeout"])
        return httpx.Response(
            200, json={"data": {"create_character": {"character": {"id": "char1"}}}}
        )

    client = Uthana(
        "synthetic-key",
        timeout=93.0,
        telemetry=False,
        transport=httpx.MockTransport(handler),
        trust_env=False,
    )
    await client.characters.create_from_file(str(source), max_bytes=max_bytes, timeout=override)
    assert observed[0]["read"] == (93.0 if override is None else override)
    client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["character", "video", "image"])
async def test_legacy_file_upload_can_opt_into_bound(tmp_path: Path, kind: str) -> None:
    suffix = {"character": ".glb", "video": ".mp4", "image": ".png"}[kind]
    source = tmp_path / ("source" + suffix)
    source.write_bytes(b"glTF" + b"0" * 30)
    client = client_for(lambda _: pytest.fail("Unexpected HTTP request"))
    with pytest.raises(ValueError, match="max_bytes"):
        if kind == "character":
            await client.characters.create_from_file(str(source), max_bytes=3)
        elif kind == "video":
            await client.vtm.create(str(source), max_bytes=3)
        else:
            await client.characters.create_from_image(str(source), max_bytes=3)
    client.close()
