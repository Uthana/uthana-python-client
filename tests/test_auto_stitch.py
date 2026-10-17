import json

import httpx
import pytest

from uthana import Uthana
from uthana.stitch import validate_auto_stitch_input
from uthana.types import UthanaError

OPTIONS = dict(character_id="c1", prefix_motion_id="m1", suffix_motion_id="m2")


@pytest.mark.parametrize(
    "options",
    [OPTIONS, {**OPTIONS, "placement": {"forward_m": 0.0, "right_m": 1.0, "facing_degrees": 90.0}}],
)
async def test_wire_contract_and_timeout(options):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "data": {
                    "create_enhanced_stitched_motion": {
                        "motion": {"id": "m3"},
                        "preparation": {"pose_samples_source": "server_sampled"},
                    }
                }
            },
        )

    client = Uthana("test", telemetry=False, transport=httpx.MockTransport(handler))
    result = await client.motions.stitch_motions(options)
    assert result["motion"]["id"] == "m3"
    assert json.loads(seen[0].content)["variables"] == {"auto_input": options}
    assert seen[0].extensions["timeout"]["read"] == 360
    client.close()


@pytest.mark.parametrize(
    "bad",
    [
        {"stitch_duration": True},
        {"stitch_duration": float("inf")},
        {"placement": {"forward_m": "2"}},
        {"placement": {"forward_m": 101}},
        {"placement": {"facing_degrees": 181}},
        {"prefix_start_seconds": 2.0, "prefix_end_seconds": 1.0},
        {"prefix_end_seconds": None},
        {"extra": 1},
    ],
)
def test_invalid_options(bad):
    with pytest.raises(ValueError):
        validate_auto_stitch_input({**OPTIONS, **bad})


async def test_missing_result_is_uncertain_without_retry():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            200, json={"data": {"create_enhanced_stitched_motion": {"motion": None}}}
        )

    client = Uthana("test", telemetry=False, transport=httpx.MockTransport(handler))
    with pytest.raises(UthanaError) as exc:
        await client.motions.stitch_motions(OPTIONS)
    assert exc.value.kind == "uncertain"
    assert len(calls) == 1
    client.close()
