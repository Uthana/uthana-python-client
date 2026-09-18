# (c) Copyright 2026 Uthana, Inc. All Rights Reserved

"""Offline coverage for configurable transport, response bounds, and API error envelopes."""

import gzip
import io
import json
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from uthana import Uthana, UthanaError


class ChunkedStream(httpx.AsyncByteStream):
    def __init__(self, chunks):
        self.chunks = chunks
        self.consumed = 0
        self.closed = False

    async def __aiter__(self):
        for chunk in self.chunks:
            self.consumed += 1
            yield chunk

    async def aclose(self):
        self.closed = True


def make_client(handler, **kwargs):
    return Uthana(
        "offline-test-key",
        telemetry=False,
        trust_env=False,
        transport=httpx.MockTransport(handler),
        **kwargs,
    )


def test_telemetry_opt_out_avoids_constructor_network_and_close_releases_session():
    with patch.object(Uthana, "_log_init") as log_init:
        client = Uthana("offline-test-key", telemetry=False, trust_env=False)
        log_init.assert_not_called()
    assert client.base_url == "https://uthana.com"
    assert not client.session.is_closed
    client.close()
    assert client.session.is_closed
    client.close()


def test_default_telemetry_and_custom_domain_are_preserved():
    with patch.object(Uthana, "_log_init") as log_init:
        client = Uthana("offline-test-key", domain="staging.uthana.com", trust_env=False)
        log_init.assert_called_once_with()
    assert client.graphql_url == "https://staging.uthana.com/graphql"
    client.close()


@pytest.mark.parametrize("field", ["max_response_bytes", "max_mutation_response_bytes"])
@pytest.mark.parametrize("limit", [0, -1, True, 1.5, "100"])
def test_constructor_rejects_invalid_response_limit(field, limit):
    with pytest.raises(ValueError, match="positive integers"):
        Uthana("offline-test-key", telemetry=False, **{field: limit})


async def test_graphql_posts_auth_query_and_variables_without_environment_proxy(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://unreachable.invalid:9")
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(200, json={"data": {"motion": {"id": "m1"}}})

    client = make_client(handle)
    try:
        assert await client._graphql(
            "query Motion($id:String!){motion(id:$id){id}}", {"id": "m1"}
        ) == {"motion": {"id": "m1"}}
    finally:
        client.close()
    assert len(requests) == 1
    request = requests[0]
    assert str(request.url) == "https://uthana.com/graphql"
    assert request.headers["authorization"].startswith("Basic ")
    assert request.headers["accept"] == "application/json"
    assert json.loads(request.content)["variables"] == {"id": "m1"}


async def test_graphql_path_defaults_and_return_type_survive_reuse():
    replies = iter(
        [
            {"data": {"create": {"motion": {"id": "m1"}}}},
            {"data": {"characters": None}},
            {"data": {}},
            {"data": {"org": None}},
        ]
    )
    client = make_client(lambda request: httpx.Response(200, json=next(replies)))
    try:
        assert await client._graphql("mutation{}", path="create.motion") == {"id": "m1"}
        assert (
            await client._graphql("query{}", path="characters", path_default=[], return_type=list)
            == []
        )
        assert await client._graphql("query{}", path="characters", path_default=[]) == []
        assert await client._graphql("query{}", path="org.characters", path_default=[]) == []
    finally:
        client.close()


async def test_upload_encodes_graphql_multipart_map_and_timeout_override():
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(200, json={"data": {"create_character": {"character": {"id": "c1"}}}})

    client = make_client(handle, timeout=httpx.Timeout(180, connect=15))
    try:
        await client._graphql(
            "mutation Upload($file:Upload!){create_character(file:$file){character{id}}}",
            {"file": None, "name": "Demo"},
            upload=("demo.fbx", b"private offline fixture"),
            timeout=httpx.Timeout(360, connect=15),
        )
        await client._graphql("query{user{id}}")
    finally:
        client.close()
    upload, query = requests
    assert upload.headers["content-type"].startswith("multipart/form-data;")
    assert upload.headers["accept"] == "application/json"
    assert b'"0": ["variables.file"]' in upload.content
    assert b'"file": null' in upload.content
    assert b'filename="demo.fbx"' in upload.content
    assert b"private offline fixture" in upload.content
    assert upload.extensions["timeout"] == {"connect": 15, "read": 360, "write": 360, "pool": 360}
    assert query.extensions["timeout"] == {"connect": 15, "read": 180, "write": 180, "pool": 180}


async def test_async_client_honors_injected_transport_and_environment_setting():
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"data": {}}))
    client = Uthana("offline-test-key", telemetry=False, trust_env=False, transport=transport)
    try:
        with patch("uthana.client.httpx.AsyncClient", wraps=httpx.AsyncClient) as factory:
            await client._graphql("query{}")
        assert factory.call_args.kwargs["transport"] is transport
        assert factory.call_args.kwargs["trust_env"] is False
        assert factory.call_args.kwargs["follow_redirects"] is False
    finally:
        client.close()


@pytest.mark.parametrize("status", [301, 302, 307, 308, 400, 401, 403, 429, 500])
async def test_http_failures_are_structured_and_never_redirected_or_retried(status):
    requests = []
    envelope = {"errors": [{"message": "Example upstream error"}]}

    def handle(request):
        requests.append(request)
        return httpx.Response(status, json=envelope, headers={"Location": "https://other.invalid"})

    client = make_client(handle)
    try:
        with pytest.raises(UthanaError) as error:
            await client._graphql("mutation{}")
    finally:
        client.close()
    assert len(requests) == 1
    assert error.value.kind == "http"
    assert error.value.status_code == status
    assert error.value.response_data == envelope


async def test_huge_http_error_keeps_status_and_bounds_error_body():
    stream = ChunkedStream([b"x" * 65536] * 20)
    client = make_client(
        lambda request: httpx.Response(401, stream=stream), max_mutation_response_bytes=32
    )
    try:
        with pytest.raises(UthanaError) as error:
            await client._graphql("mutation{}")
    finally:
        client.close()
    assert error.value.status_code == 401
    assert error.value.kind == "http"
    assert len(error.value.message) == 32
    assert stream.consumed == 1
    assert stream.closed


@pytest.mark.parametrize("failure", [httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout])
async def test_httpx_failures_preserve_identity_without_retry(failure):
    calls = []
    expected = failure("offline simulated failure")

    def handle(request):
        calls.append(request)
        raise expected

    client = make_client(handle)
    try:
        with pytest.raises(failure) as error:
            await client._graphql("mutation{}")
    finally:
        client.close()
    assert error.value is expected
    assert len(calls) == 1


async def test_graphql_errors_preserve_full_envelope_for_submission_classification():
    envelope = {
        "errors": [{"message": "Example", "path": ["create_motion", "motion"]}],
        "data": {"create_motion": {"motion": None}},
    }
    client = make_client(lambda request: httpx.Response(200, json=envelope))
    try:
        with pytest.raises(UthanaError) as error:
            await client._graphql("mutation{}")
    finally:
        client.close()
    assert error.value.kind == "graphql"
    assert error.value.response_data == envelope
    assert error.value.status_code == 400


@pytest.mark.parametrize("body", [b"not-json", b"\xff", b"[]", b"null", b"{}", b'{"data":null}'])
async def test_invalid_graphql_response_is_structured(body):
    client = make_client(lambda request: httpx.Response(200, content=body))
    try:
        with pytest.raises(UthanaError) as error:
            await client._graphql("query{}")
    finally:
        client.close()
    assert error.value.kind == "invalid_response"
    assert error.value.response_data is None


async def test_graphql_response_limit_uses_decoded_bytes_and_stops_streaming():
    stream = ChunkedStream([b"x" * 65536] * 20)
    client = make_client(
        lambda request: httpx.Response(200, stream=stream), max_response_bytes=65536
    )
    try:
        with pytest.raises(UthanaError) as error:
            await client._graphql("query{}")
    finally:
        client.close()
    assert error.value.kind == "response_too_large"
    assert stream.consumed == 2
    assert stream.closed


async def test_compressed_response_is_bounded_after_decompression():
    compressed = gzip.compress(json.dumps({"data": {"large": "x" * 10000}}).encode())
    client = make_client(
        lambda request: httpx.Response(
            200, content=compressed, headers={"content-encoding": "gzip"}
        ),
        max_response_bytes=256,
    )
    try:
        with pytest.raises(UthanaError, match="byte limit") as error:
            await client._graphql("query{}")
    finally:
        client.close()
    assert error.value.kind == "response_too_large"


async def test_binary_response_limit_is_independent_of_graphql_limit():
    client = make_client(
        lambda request: httpx.Response(200, content=b"0123456789"), max_response_bytes=2
    )
    try:
        assert (
            await client._request_bytes("GET", client.base_url + "/asset", max_bytes=10)
            == b"0123456789"
        )
        with pytest.raises(UthanaError) as error:
            await client._request_bytes("GET", client.base_url + "/asset", max_bytes=9)
        assert error.value.kind == "response_too_large"
    finally:
        client.close()


def test_motion_export_options_and_character_warning_are_preserved():
    client = Uthana("offline-test-key", telemetry=False, trust_env=False)
    try:
        url = client._motion_url(
            character_id="c1",
            motion_id="m1",
            output_format="bvh",
            fps=30,
            no_mesh=False,
            in_place=True,
            roblox_compatible=True,
            speed_multiplier=0.5,
            torso_only=False,
        )
        result = client._build_character_output(
            result={
                "data": {
                    "create_character": {
                        "character": {"id": "c1"},
                        "auto_rig_confidence": 0.8,
                        "message": "FBX rotation compatibility warning",
                    }
                }
            },
            ext="fbx",
        )
    finally:
        client.close()
    assert urlparse(url).path.endswith("/c1-m1.bvh")
    assert parse_qs(urlparse(url).query) == {
        "fps": ["30"],
        "no_mesh": ["false"],
        "in_place": ["true"],
        "roblox_compatible": ["true"],
        "torso_only": ["false"],
        "speed_multiplier": ["0.5"],
    }
    assert result.message == "FBX rotation compatibility warning"
    assert result.character_id == "c1"
    assert result.auto_rig_confidence == 0.8


def test_error_two_argument_constructor_is_backwards_compatible():
    error = UthanaError(404, "Not found")
    assert error.kind is None
    assert error.response_data is None
    assert str(error) == "Uthana API error 404: Not found"


async def test_graphql_upload_streams_file_without_unbounded_reads_or_taking_ownership():
    class GuardedFile(io.BytesIO):
        def __init__(self, value):
            super().__init__(value)
            self.read_sizes = []

        def read(self, size=-1):
            assert 0 < size <= 65536, "Upload requested an unbounded file read"
            self.read_sizes.append(size)
            return super().read(size)

    upload = GuardedFile(b"x" * 200000)
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"data": {"create": {"id": "new"}}})

    client = make_client(handler)
    try:
        result = await client._graphql(
            "mutation Upload($file:Upload!){create(file:$file){id}}",
            {"file": None},
            upload=("large.fbx", upload),
        )
    finally:
        client.close()
    assert result == {"create": {"id": "new"}}
    assert len(upload.read_sizes) > 1
    assert not upload.closed
    assert len(requests) == 1
    assert b'filename="large.fbx"' in requests[0].content
    assert b"x" * 200000 in requests[0].content
    upload.close()


@pytest.mark.parametrize(
    "query",
    [
        "mutation { create { id } }",
        "\ufeff ,# query { not_an_operation }\r\n mutation M { create { id } }",
        "fragment F on Motion { id } mutation { create { ...F } }",
    ],
)
@pytest.mark.parametrize("multipart_upload", [False, True])
async def test_mutation_receipt_is_not_limited_by_query_bound(query, multipart_upload):
    requests = []
    receipt = {"create": {"id": "c1", "message": "x" * 2000}}

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"data": receipt})

    client = make_client(handler, max_response_bytes=16)
    try:
        assert (
            await client._graphql(
                query, upload=("character.glb", b"glTF") if multipart_upload else None
            )
            == receipt
        )
    finally:
        client.close()
    assert len(requests) == 1


async def test_explicit_mutation_limit_reports_uncertain_without_retry_and_closes_stream():
    stream = ChunkedStream([b"x" * 65536] * 20)
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, stream=stream)

    client = make_client(handler, max_response_bytes=16, max_mutation_response_bytes=65536)
    try:
        with pytest.raises(UthanaError, match="may have succeeded") as error:
            await client._graphql("mutation { create { id } }")
    finally:
        client.close()
    assert error.value.kind == "uncertain"
    assert error.value.status_code == 200
    assert "before resubmitting" in error.value.message
    assert len(calls) == 1
    assert stream.consumed == 2
    assert stream.closed


@pytest.mark.parametrize(
    "query",
    [
        "query Q { motion { id } }",
        "{ motion { id } }",
        "\ufeff ,# mutation { ignored }\r\nquery Q { motion { id } }",
    ],
)
async def test_query_bound_still_applies_with_separate_mutation_limit(query):
    client = make_client(
        lambda _: httpx.Response(200, json={"data": {"motion": {"id": "m1"}}}),
        max_response_bytes=16,
        max_mutation_response_bytes=1000,
    )
    try:
        with pytest.raises(UthanaError) as error:
            await client._graphql(query)
        assert error.value.kind == "response_too_large"
    finally:
        client.close()
