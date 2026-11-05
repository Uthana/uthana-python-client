"""org.get_ledger: query shape, validation and paging."""

import datetime
import json

import httpx
import pytest

from uthana import Uthana


def client_for(handler) -> Uthana:
    return Uthana(
        "synthetic-key",
        domain="staging.uthana.com",
        telemetry=False,
        transport=httpx.MockTransport(handler),
        trust_env=False,
    )


ROW = {
    "id": "pl1",
    "created": "2026-11-01T12:00:00Z",
    "type": "debit",
    "total_usd": "0.2500",
    "balance_before": "10.0000",
    "balance_after": "9.7500",
    "ref": "motion:m1",
    "status": "ok",
}


@pytest.mark.asyncio
async def test_default_call_sends_only_limit() -> None:
    captured = []

    def handler(request):
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"data": {"payg_ledger": [ROW]}})

    client = client_for(handler)
    assert await client.org.get_ledger() == [ROW]
    payload = captured[0]
    assert payload["query"].lstrip().startswith("query Ledger($limit: Int)")
    assert "before_id" not in payload["query"]
    assert payload["variables"] == {"limit": 50}
    client.close()


@pytest.mark.asyncio
async def test_filters_are_sent_and_naive_times_are_utc() -> None:
    captured = []

    def handler(request):
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"data": {"payg_ledger": []}})

    client = client_for(handler)
    rows = await client.org.get_ledger(
        limit=500,
        before_id="pl9",
        since=datetime.datetime(2026, 11, 1),
        until="2026-11-04T00:00:00Z",
        types=("debit", "topup"),
    )
    assert rows == []
    assert captured[0]["variables"] == {
        "limit": 500,
        "before_id": "pl9",
        "since": "2026-11-01T00:00:00+00:00",
        "until": "2026-11-04T00:00:00Z",
        "types": ["debit", "topup"],
    }
    query = captured[0]["query"]
    for fragment in ("$before_id: ID", "$since: DateTime", "$types: [String!]", "types: $types"):
        assert fragment in query
    client.close()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"limit": 0},
        {"limit": 501},
        {"limit": True},
        {"before_id": ""},
        {"since": "yesterday"},
        {"types": "debit"},
        {"types": ["debit", ""]},
    ],
)
def test_invalid_arguments_fail_before_any_request(kwargs) -> None:
    client = client_for(lambda _: pytest.fail("Unexpected HTTP request"))
    with pytest.raises(ValueError):
        client.org.get_ledger_sync(**kwargs)
    client.close()


@pytest.mark.asyncio
async def test_debit_asset_and_job_ids_pass_through_unchanged() -> None:
    # The backend stores the charged motion in job_id and the processing job in task_id.
    debit = {**ROW, "job_id": "mMotion123", "task_id": "J0000000001", "ref": "motion:mMotion123"}
    captured = []

    def handler(request):
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"data": {"payg_ledger": [debit]}})

    client = client_for(handler)
    [row] = await client.org.get_ledger(limit=1)
    assert row["job_id"] == "mMotion123" and row["task_id"] == "J0000000001"
    assert "job_id" in captured[0]["query"] and "task_id" in captured[0]["query"]
    client.close()
