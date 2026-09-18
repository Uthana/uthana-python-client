"""Enhanced stitch request contracts using synthetic, non-production poses."""

import copy
import json

import httpx
import pytest

from uthana import Uthana
from uthana.graphql import q
from uthana.stitch import validate_stitch_params


def clip(motion_id="motion1"):
    pose = {
        "pelvis_world_pos": {"x": 1, "y": 0.9, "z": 2},
        "pelvis_world_rot": {"x": 0, "y": 0, "z": 0, "w": 1},
        "hips_forward_facing_world_yaw": 0.2,
    }
    return {
        "motion_id": motion_id,
        "motion_duration": 4,
        "motion_lower_trim_time": 0.5,
        "motion_upper_trim_time": 3.5,
        "motion_lower_trim_fraction": 0.125,
        "motion_upper_trim_fraction": 0.875,
        "stitch_duration": 1.5,
        "stitch_loop": False,
        "prompt": "Step into the next action",
        "root_node_world_pos": {"x": 1, "y": 0, "z": 2},
        "root_node_world_rot": {"x": 0, "y": 0, "z": 0, "w": 1},
        "at_zero_time": copy.deepcopy(pose),
        "at_lower_trim_time": copy.deepcopy(pose),
        "at_upper_trim_time": copy.deepcopy(pose),
    }


def client(handler):
    return Uthana(
        "synthetic", telemetry=False, trust_env=False, transport=httpx.MockTransport(handler)
    )


async def test_enhanced_stitch_payload_and_timeout():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            200,
            json={
                "data": {
                    "create_enhanced_stitched_motion": {
                        "motion": {"id": "stitched1", "name": "Joined"}
                    }
                }
            },
        )

    api = client(handler)
    prefix, suffix = clip(), clip("motion2")
    original = copy.deepcopy((prefix, suffix))
    result = await api.motions.create_stitched_motion(
        "char1", prefix, suffix, timeout=httpx.Timeout(360, connect=15)
    )
    assert result == {"id": "stitched1", "name": "Joined"}
    assert json.loads(calls[0].content) == {
        "query": q.CREATE_ENHANCED_STITCHED_MOTION,
        "variables": {
            "stitch_input": {"character_id": "char1", "prefix": prefix, "suffix": suffix}
        },
    }
    assert calls[0].extensions["timeout"]["read"] == 360
    assert calls[0].extensions["timeout"]["connect"] == 15
    assert (prefix, suffix) == original
    api.close()


@pytest.mark.parametrize(
    "path,value",
    [
        (("motion_duration",), 0),
        (("motion_lower_trim_time",), -1),
        (("motion_upper_trim_time",), 5),
        (("motion_upper_trim_time",), 0.5),
        (("motion_lower_trim_fraction",), 0.9),
        (("motion_upper_trim_fraction",), 1),
        (("stitch_duration",), 0),
        (("stitch_duration",), True),
        (("motion_id",), ""),
        (("prompt",), None),
        (("stitch_loop",), "false"),
        (("extra",), 1),
        (("root_node_world_pos", "x"), float("inf")),
        (("root_node_world_rot", "w"), 0),
        (("root_node_world_rot", "w"), 2),
        (("at_upper_trim_time", "hips_forward_facing_world_yaw"), float("nan")),
        (("at_lower_trim_time", "pelvis_world_pos", "y"), "0.9"),
        (("at_zero_time", "pelvis_world_rot", "x"), False),
    ],
)
async def test_invalid_stitch_payload_does_not_submit(path, value):
    calls = []
    api = client(lambda request: calls.append(request))
    bad = clip()
    target = bad
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValueError):
        await api.motions.create_stitched_motion("char1", clip(), bad)
    assert calls == []
    api.close()


async def test_missing_pose_and_invalid_character_do_not_submit():
    calls = []
    api = client(lambda request: calls.append(request))
    bad = clip()
    del bad["at_upper_trim_time"]
    with pytest.raises(ValueError):
        await api.motions.create_stitched_motion("char1", bad, clip())
    with pytest.raises(ValueError):
        await api.motions.create_stitched_motion(" ", clip(), clip())
    assert not calls
    api.close()


def test_stitch_sync_and_input_snapshot():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            200, json={"data": {"create_enhanced_stitched_motion": {"motion": {"id": "sync1"}}}}
        )

    api = client(handler)
    assert (
        api.motions.create_stitched_motion_sync("char1", clip(), clip("motion2"))["id"] == "sync1"
    )
    assert len(calls) == 1
    original = clip()
    snapshot = validate_stitch_params(original)
    original["at_zero_time"]["pelvis_world_pos"]["x"] = 999
    assert snapshot["at_zero_time"]["pelvis_world_pos"]["x"] == 1
    api.close()
