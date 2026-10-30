"""Shared contract fixtures and real SDK wire behavior, without paid API calls."""

import json
from copy import deepcopy
from pathlib import Path

import httpx
import pytest

from uthana import Uthana
from uthana.stitch import validate_stitch_input
from uthana.types import UthanaError

FIXTURES = json.loads((Path(__file__).parent / "fixtures/stitch_contract.json").read_text())
OPTIONS = FIXTURES["valid"][0]["input"]


@pytest.mark.parametrize("case", FIXTURES["valid"], ids=lambda c: c["name"])
async def test_wire_contract_and_timeout(case):
    seen = []
    options = case["input"]
    expected = validate_stitch_input(options)
    assert expected == case["normalized"]

    def handler(request):
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "data": {"stitch": {"motion": {"id": "m3"}, "resolved_steps": expected["steps"]}}
            },
        )

    client = Uthana("test", telemetry=False, transport=httpx.MockTransport(handler))
    result = await client.motions.stitch(options)
    assert result["motion"]["id"] == "m3"
    assert result["resolved_steps"] == expected["steps"]
    assert json.loads(seen[0].content)["variables"] == {"input": expected}
    assert "stitch(input: $input)" in json.loads(seen[0].content)["query"]
    assert seen[0].extensions["timeout"]["read"] == 360
    client.close()


@pytest.mark.parametrize("case", FIXTURES["invalid"], ids=lambda c: c["name"])
def test_invalid_options(case):
    with pytest.raises(ValueError):
        validate_stitch_input(case["input"])


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_values(value):
    options = {
        **OPTIONS,
        "steps": [
            {**OPTIONS["steps"][0], "transition": {"duration_seconds": value}},
            OPTIONS["steps"][1],
        ],
    }
    with pytest.raises(ValueError):
        validate_stitch_input(options)


@pytest.mark.parametrize(
    ("result", "message"),
    [
        ({"motion": None}, "invalid motion"),
        ({"motion": {"id": " "}}, "invalid motion"),
        ({"motion": {"id": "m3"}}, "exactly two resolved steps"),
        ({"motion": {"id": "m3"}, "resolved_steps": []}, "exactly two resolved steps"),
    ],
)
async def test_invalid_result_is_specific_and_uncertain_without_retry(result, message):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"data": {"stitch": result}})

    client = Uthana("test", telemetry=False, transport=httpx.MockTransport(handler))
    with pytest.raises(UthanaError) as exc:
        await client.motions.stitch(OPTIONS)
    assert message in str(exc.value)
    assert exc.value.kind == "uncertain"
    assert len(calls) == 1
    client.close()


def test_normalization_preserves_caller_owned_nested_records():
    request = deepcopy(FIXTURES["valid"][1]["input"])
    request["steps"][1]["placement"] = {"forward_m": 0, "right_m": 0.5}
    original = deepcopy(request)
    normalized = validate_stitch_input(request)
    assert validate_stitch_input(normalized) == normalized
    first, last = normalized["steps"]
    assert "type" not in first and "type" not in last
    assert "range" in first and "placement" in last
    first["range"]["end_frame"] = 50
    last["placement"]["right_m"] = 10
    assert request == original
