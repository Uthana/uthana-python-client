import httpx
import pytest

from uthana import Uthana


@pytest.mark.parametrize("token", ["", "with space", "line\nbreak"])
def test_invalid_bearer_token(token):
    with pytest.raises(ValueError, match="access_token"):
        Uthana(access_token=token, telemetry=False)


def test_conflicting_credentials():
    with pytest.raises(ValueError, match="not both"):
        Uthana("key", access_token="token", telemetry=False)


async def test_bearer_reaches_async_transport_without_basic_auth():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"data": {"user": {"id": "u1"}}})

    client = Uthana(
        access_token="delegated-token", telemetry=False, transport=httpx.MockTransport(handler)
    )
    await client._graphql("{ user { id } }")
    assert len(calls) == 1
    assert calls[0].headers["Authorization"] == "Bearer delegated-token"
    assert client.session.build_request("GET", client.base_url).headers.get("Authorization") is None
    assert "delegated-token" not in repr(client)
    client.close()


async def test_refreshable_auth_runs_for_each_request():
    class Refreshable(httpx.Auth):
        async def async_auth_flow(self, request):
            request.headers["Authorization"] = "Bearer refreshed"
            yield request

    seen = []

    def handler(request):
        seen.append(request.headers["Authorization"])
        return httpx.Response(200, json={"data": {}})

    client = Uthana(
        access_token=Refreshable(), telemetry=False, transport=httpx.MockTransport(handler)
    )
    await client._graphql("{ user { id } }")
    await client._graphql("{ user { id } }")
    assert seen == ["Bearer refreshed", "Bearer refreshed"]
    client.close()
