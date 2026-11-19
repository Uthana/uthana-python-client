"""Offline cross-language contract and transport regression tests."""

import copy
import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from tests.test_modules import _make_client
from uthana.controlled_locomotion import (
    controlled_locomotion_options,
    normalize_controlled_locomotion_plan,
)
from uthana.graphql import q
from uthana.types import UthanaError

CASES = json.loads((Path(__file__).parent / "fixtures/controlled_locomotion.json").read_text())
PLAN = CASES[0]["input"]
CHARACTER = "cH32hVsowEyB"


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_shared_contract(case):
    original = copy.deepcopy(case["input"])
    if case["valid"]:
        actual = normalize_controlled_locomotion_plan(case["input"])
        assert actual == case["normalized"]
        actual["points"][0]["right"] = 1
    else:
        with pytest.raises(ValueError):
            normalize_controlled_locomotion_plan(case["input"])
    assert case["input"] == original


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf"), 10**500])
def test_nonfinite(value):
    plan = copy.deepcopy(PLAN)
    plan["pace_changes"][0]["speed_mps"] = value
    with pytest.raises(ValueError):
        normalize_controlled_locomotion_plan(plan)


def test_discovery_is_fresh():
    options = controlled_locomotion_options()
    options["styles"].clear()
    assert controlled_locomotion_options()["styles"]


async def test_submit_and_no_retry():
    client = _make_client()
    job = {"id": "j1", "status": "PENDING"}
    client._graphql = AsyncMock(return_value=job)
    assert await client.motions.create_controlled_locomotion(CHARACTER, plan=PLAN) == job
    args, kwargs = client._graphql.call_args
    assert args[0] == q.CREATE_CONTROLLED_LOCOMOTION
    assert args[1] == {"character_id": CHARACTER, "plan": CASES[0]["normalized"]}
    assert kwargs["path"] == "create_controlled_locomotion_job.job"
    client._graphql = AsyncMock(side_effect=TimeoutError())
    with pytest.raises(TimeoutError):
        await client.motions.create_controlled_locomotion(CHARACTER, plan=PLAN)
    client._graphql.assert_awaited_once()


@pytest.mark.parametrize("job", [None, {}, {"id": ""}, {"id": 7}, {"id": "  "}])
async def test_unknown_submission_outcome(job):
    client = _make_client()
    client._graphql = AsyncMock(return_value=job)
    with pytest.raises(UthanaError) as exc:
        await client.motions.create_controlled_locomotion(CHARACTER, plan=PLAN)
    assert exc.value.kind == "uncertain"
    client._graphql.assert_awaited_once()


async def test_invalid_input_never_sends():
    client = _make_client()
    client._graphql = AsyncMock()
    with pytest.raises(ValueError):
        await client.motions.create_controlled_locomotion("unsupported", plan=PLAN)
    with pytest.raises(ValueError):
        await client.motions.create_controlled_locomotion(CHARACTER, plan={})
    client._graphql.assert_not_called()


def test_sync():
    client = _make_client()
    client._graphql = AsyncMock(return_value={"id": "j1"})
    assert client.motions.create_controlled_locomotion_sync(CHARACTER, plan=PLAN)["id"] == "j1"


@pytest.mark.parametrize("enabled", [True, False])
async def test_live_options(enabled):
    client = _make_client()
    client._graphql = AsyncMock(return_value={"enabled": enabled, "styles": ["march"]})
    assert await client.motions.get_controlled_locomotion_options() == {
        "enabled": enabled,
        "styles": ["march"],
    }
    client._graphql.assert_awaited_once_with(
        q.CONTROLLED_LOCOMOTION_OPTIONS, path="controlled_locomotion_options"
    )


@pytest.mark.parametrize("options", [None, {}, {"enabled": 1}, {"enabled": "true"}])
async def test_malformed_options(options):
    client = _make_client()
    client._graphql = AsyncMock(return_value=options)
    with pytest.raises(UthanaError):
        await client.motions.get_controlled_locomotion_options()


def test_sync_live_options():
    client = _make_client()
    client._graphql = AsyncMock(return_value={"enabled": False})
    assert client.motions.get_controlled_locomotion_options_sync() == {"enabled": False}
