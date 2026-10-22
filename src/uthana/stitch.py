"""Shared typed-step stitching, with legacy sampled-pose compatibility.

Ordinary stitching is prepared by the service. Only legacy sampled-pose callers
supply transforms; validation never establishes animation quality.
"""

import math
import re
from copy import deepcopy
from typing import Any, Literal, Mapping, TypedDict, cast

from .types import Motion

MAX_FRAME_INDEX = 2**53 - 1
MAX_OFFSET_METERS = 100
MAX_TURN_DEGREES = 180
MIN_TRANSITION_SECONDS = 0.1
MAX_TRANSITION_SECONDS = 3
DEFAULT_TRANSITION_SECONDS = 1.0


class Vector3(TypedDict):
    x: float
    y: float
    z: float


class Quaternion(TypedDict):
    x: float
    y: float
    z: float
    w: float


class PelvisState(TypedDict):
    pelvis_world_pos: Vector3
    pelvis_world_rot: Quaternion
    hips_forward_facing_world_yaw: float


class StitchParams(TypedDict):
    prompt: str
    motion_id: str
    stitch_loop: bool
    stitch_duration: float
    motion_duration: float
    motion_lower_trim_time: float
    motion_upper_trim_time: float
    motion_lower_trim_fraction: float
    motion_upper_trim_fraction: float
    root_node_world_pos: Vector3
    root_node_world_rot: Quaternion
    at_zero_time: PelvisState
    at_lower_trim_time: PelvisState
    at_upper_trim_time: PelvisState


def _finite(value: object) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Stitch values must be finite numbers, not booleans or strings")
    try:
        valid = math.isfinite(value)
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError("Stitch values must be finite numbers, not booleans or strings")
    return value


def _fields(value, required):
    if not isinstance(value, dict) or set(value) != set(required):
        raise ValueError("Stitch input has missing or unsupported fields")


def _vector(value, *, quaternion=False):
    _fields(value, "xyzw" if quaternion else "xyz")
    for number in value.values():
        _finite(number)
    if quaternion and not math.isclose(math.hypot(*value.values()), 1.0, abs_tol=1e-3):
        raise ValueError("Stitch rotations must be unit quaternions in x/y/z/w order")


def validate_stitch_params(params: Mapping[str, Any]) -> StitchParams:
    """Validate and copy a full API clip input before a potentially paid mutation."""
    _fields(params, StitchParams.__required_keys__)
    if not isinstance(params["motion_id"], str) or not params["motion_id"].strip():
        raise ValueError("Each stitch clip needs a motion_id")
    if not isinstance(params["prompt"], str) or not isinstance(params["stitch_loop"], bool):
        raise ValueError("Stitch prompt must be text and stitch_loop must be boolean")
    duration = _finite(params["motion_duration"])
    start = _finite(params["motion_lower_trim_time"])
    end = _finite(params["motion_upper_trim_time"])
    lower = _finite(params["motion_lower_trim_fraction"])
    upper = _finite(params["motion_upper_trim_fraction"])
    if duration <= 0 or not 0 <= start < end <= duration or _finite(params["stitch_duration"]) <= 0:
        raise ValueError(
            "Stitch trims need 0 <= start < end <= duration and positive transition duration"
        )
    if not 0 <= lower < upper <= 1 or not all(
        math.isclose(a, b, rel_tol=1e-7, abs_tol=1e-8)
        for a, b in ((lower, start / duration), (upper, end / duration))
    ):
        raise ValueError("Stitch trim fractions must agree with times divided by motion duration")
    _vector(params["root_node_world_pos"])
    _vector(params["root_node_world_rot"], quaternion=True)
    for key in ("at_zero_time", "at_lower_trim_time", "at_upper_trim_time"):
        pose = params[key]
        _fields(pose, PelvisState.__required_keys__)
        _vector(pose["pelvis_world_pos"])
        _vector(pose["pelvis_world_rot"], quaternion=True)
        _finite(pose["hips_forward_facing_world_yaw"])
    return cast(StitchParams, deepcopy(params))


class StitchRange(TypedDict, total=False):
    start_frame: int
    end_frame: int
    start_seconds: float
    end_seconds: float


class StitchPlacement(TypedDict, total=False):
    forward_m: float
    right_m: float
    turn_degrees: float
    absolute: Literal[False]


class _MotionStepRequired(TypedDict):
    type: Literal["motion"]
    motion_id: str


class MotionStep(_MotionStepRequired, total=False):
    range: StitchRange
    placement: StitchPlacement


class _TransitionStepRequired(TypedDict):
    type: Literal["transition"]


class TransitionStep(_TransitionStepRequired, total=False):
    duration_seconds: float


class StitchInput(TypedDict):
    character_id: str
    steps: list[MotionStep | TransitionStep]


class ResolvedRange(TypedDict):
    start_frame: int
    end_frame: int
    start_seconds: float
    end_seconds: float


class AutomaticPlacement(TypedDict):
    mode: Literal["automatic"]


class _ResolvedMotionRequired(TypedDict):
    type: Literal["motion"]
    motion_id: str
    range: ResolvedRange


class ResolvedMotionStep(_ResolvedMotionRequired, total=False):
    placement: StitchPlacement | AutomaticPlacement


class ResolvedTransitionStep(TypedDict):
    type: Literal["transition"]
    duration_seconds: float


class StitchResult(TypedDict):
    motion: Motion
    resolved_steps: list[ResolvedMotionStep | ResolvedTransitionStep]


def _allowed_fields(value: object, *, required: set[str], allowed: set[str]) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError("Stitch objects must be dictionaries")
    missing_fields = not required <= value.keys()
    has_unsupported_fields = bool(value.keys() - allowed)
    if missing_fields or has_unsupported_fields:
        raise ValueError("Stitch input has missing or unsupported fields")
    # Membership above establishes every key is one of the allowed strings.
    return cast(dict[str, object], value)


def _stitch_id(value: object) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value) is None:
        raise ValueError("Stitch IDs need 1-128 letters, digits, underscores, or hyphens")
    return value


def _frame(value: object) -> int:
    if type(value) is not int or not 0 <= value <= MAX_FRAME_INDEX:
        raise ValueError("Frame indices must be nonnegative safe integers")
    return value


def _seconds(value: object) -> float:
    number = _finite(value)
    if number < 0:
        raise ValueError("Range seconds must be nonnegative")
    return float(number)


def _validate_range(value: object) -> StitchRange:
    fields = {"start_frame", "end_frame", "start_seconds", "end_seconds"}
    selected = _allowed_fields(value, required=set(), allowed=fields)
    has_frame_range = bool(selected.keys() & {"start_frame", "end_frame"})
    has_second_range = bool(selected.keys() & {"start_seconds", "end_seconds"})
    if has_frame_range and has_second_range:
        raise ValueError("Use frames or seconds within a range, not both")
    result: StitchRange = {}
    if "start_frame" in selected:
        result["start_frame"] = _frame(selected["start_frame"])
    if "end_frame" in selected:
        result["end_frame"] = _frame(selected["end_frame"])
    if "start_seconds" in selected:
        result["start_seconds"] = _seconds(selected["start_seconds"])
    if "end_seconds" in selected:
        result["end_seconds"] = _seconds(selected["end_seconds"])
    start = result.get("start_frame", 0) if has_frame_range else result.get("start_seconds", 0.0)
    end = result.get("end_frame") if has_frame_range else result.get("end_seconds")
    if end is not None and end <= start:
        raise ValueError("Range end must exceed start")
    return result


def _validate_placement(value: object) -> StitchPlacement:
    selected = _allowed_fields(
        value, required=set(), allowed={"forward_m", "right_m", "turn_degrees", "absolute"}
    )
    if selected.get("absolute", False) is not False:
        raise ValueError("Only relative placement (absolute: false) is supported")
    forward = float(_finite(selected.get("forward_m", 0.0)))
    right = float(_finite(selected.get("right_m", 0.0)))
    turn = float(_finite(selected.get("turn_degrees", 0.0)))
    for name, number, limit in (
        ("forward_m", forward, MAX_OFFSET_METERS),
        ("right_m", right, MAX_OFFSET_METERS),
        ("turn_degrees", turn, MAX_TURN_DEGREES),
    ):
        if not -limit <= number <= limit:
            raise ValueError(f"{name} must be between {-limit} and {limit}")
    return {"forward_m": forward, "right_m": right, "turn_degrees": turn, "absolute": False}


def _validate_motion_step(value: object, *, arriving: bool) -> MotionStep:
    selected = _allowed_fields(
        value, required={"type", "motion_id"}, allowed={"type", "motion_id", "range", "placement"}
    )
    if selected["type"] != "motion":
        raise ValueError(
            "Must include exactly three steps: a first motion, "
            "a middle transition, and a second motion"
        )
    result: MotionStep = {
        "type": "motion",
        "motion_id": _stitch_id(selected["motion_id"]),
        "range": _validate_range(selected.get("range", {})),
    }
    if "placement" in selected:
        if not arriving:
            raise ValueError("Placement is supported only on the arriving motion")
        result["placement"] = _validate_placement(selected["placement"])
    return result


def _validate_transition_step(value: object) -> TransitionStep:
    selected = _allowed_fields(value, required={"type"}, allowed={"type", "duration_seconds"})
    if selected["type"] != "transition":
        raise ValueError(
            "Must include exactly three steps: a first motion, "
            "a middle transition, and a second motion"
        )
    duration = float(_finite(selected.get("duration_seconds", DEFAULT_TRANSITION_SECONDS)))
    if not MIN_TRANSITION_SECONDS <= duration <= MAX_TRANSITION_SECONDS:
        raise ValueError("Transition duration must be 0.1-3 seconds")
    return {"type": "transition", "duration_seconds": duration}


def validate_stitch_input(value: object) -> StitchInput:
    """Validate and copy typed steps without API calls or caller-owned mutations."""
    request = _allowed_fields(
        value, required={"character_id", "steps"}, allowed={"character_id", "steps"}
    )
    character_id = _stitch_id(request["character_id"])
    if not isinstance(steps := request["steps"], list) or len(steps) != 3:
        raise ValueError(
            "Must include exactly three steps: a first motion, "
            "a middle transition, and a second motion"
        )
    return {
        "character_id": character_id,
        "steps": [
            _validate_motion_step(steps[0], arriving=False),
            _validate_transition_step(steps[1]),
            _validate_motion_step(steps[2], arriving=True),
        ],
    }
