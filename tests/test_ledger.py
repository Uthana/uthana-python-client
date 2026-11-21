"""org.get_ledger: query shape, validation and paging."""

import datetime
import json
from typing import Any

import httpx
import pytest

from uthana import Uthana


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    original = datetime.datetime

    class FixedDatetime(original):
        @classmethod
        def now(cls, tz: datetime.tzinfo | None = None) -> datetime.datetime:
            return cls(2026, 11, 20, tzinfo=datetime.timezone.utc).astimezone(tz)

    monkeypatch.setattr("uthana.modules.org.datetime.datetime", FixedDatetime)


def client_for(handler: Any) -> Uthana:
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
async def test_default_call_sends_seven_day_bounds() -> None:
    captured = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"data": {"payg_ledger": [ROW]}})

    client = client_for(handler)
    assert await client.org.get_ledger() == [ROW]
    payload = captured[0]
    assert "$since: DateTime" in payload["query"]
    assert "before_id" not in payload["query"]
    assert payload["variables"] == {
        "limit": 50,
        "since": "2026-11-13T00:00:00+00:00",
        "until": "2026-11-20T00:00:00+00:00",
    }
    client.close()


@pytest.mark.asyncio
async def test_filters_are_sent_and_naive_times_are_utc() -> None:
    captured = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"data": {"payg_ledger": []}})

    client = client_for(handler)
    rows = await client.org.get_ledger(
        limit=500,
        before_id="pl9",
        since=datetime.datetime(2026, 11, 18),
        until="2026-11-19T00:00:00+00:00",
        types=("debit", "topup"),
    )
    assert rows == []
    assert captured[0]["variables"] == {
        "limit": 500,
        "before_id": "pl9",
        "since": "2026-11-18T00:00:00+00:00",
        "until": "2026-11-19T00:00:00+00:00",
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
def test_invalid_arguments_fail_before_any_request(kwargs: Any) -> None:
    client = client_for(lambda _: pytest.fail("Unexpected HTTP request"))
    with pytest.raises(ValueError):
        client.org.get_ledger_sync(**kwargs)
    client.close()


@pytest.mark.asyncio
async def test_debit_asset_and_job_ids_pass_through_unchanged() -> None:
    # The backend stores the charged motion in job_id and the processing job in task_id.
    debit = {**ROW, "job_id": "mMotion123", "task_id": "J0000000001", "ref": "motion:mMotion123"}
    captured = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"data": {"payg_ledger": [debit]}})

    client = client_for(handler)
    [row] = await client.org.get_ledger(limit=1)
    assert row["job_id"] == "mMotion123" and row["task_id"] == "J0000000001"
    assert "job_id" in captured[0]["query"] and "task_id" in captured[0]["query"]
    client.close()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"since": "2026-11-12T23:59:59.999Z"},
        {"until": "2026-11-12T23:59:59.999Z"},
        {"until": "2026-11-20T00:00:00.001Z"},
        {"since": "2026-11-20T00:00:00.001Z"},
        {"since": "2026-11-19T00:00:00Z", "until": "2026-11-19T00:00:00Z"},
        {"since": "2026-11-19T00:00:00Z", "until": "2026-11-18T00:00:00Z"},
    ],
)
def test_rejects_dates_outside_window_and_reversed_bounds(kwargs: Any) -> None:
    client = client_for(lambda _: pytest.fail("Unexpected HTTP request"))
    with pytest.raises(ValueError):
        client.org.get_ledger_sync(**kwargs)
    client.close()


def test_paging_cannot_escape_recent_window() -> None:
    captured = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"data": {"payg_ledger": []}})

    client = client_for(handler)
    assert client.org.get_ledger_sync(before_id="old-entry", since=None, until=None) == []
    assert captured[0]["variables"] == {
        "limit": 50,
        "before_id": "old-entry",
        "since": "2026-11-13T00:00:00+00:00",
        "until": "2026-11-20T00:00:00+00:00",
    }
    client.close()


def test_exact_cutoff_and_timezone_offsets_are_accepted() -> None:
    captured = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"data": {"payg_ledger": []}})

    client = client_for(handler)
    client.org.get_ledger_sync(since="2026-11-12T16:00:00-08:00")
    assert captured[0]["variables"]["since"] == "2026-11-12T16:00:00-08:00"
    client.close()
