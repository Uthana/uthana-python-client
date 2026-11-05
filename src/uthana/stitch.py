"""Flat motion-step stitching, with legacy sampled-pose compatibility.

Ordinary stitching is prepared by the service. Only legacy sampled-pose callers
supply transforms; validation never establishes animation quality.
"""

import math
import re
from copy import deepcopy
from typing import Any, Mapping, TypedDict, cast

from .types import Motion

MAX_FRAME_INDEX = 2**31 - 1
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


class _MotionStepRequired(TypedDict):
    motion_id: str


class MotionStep(_MotionStepRequired, total=False):
    trim_start_frame: int
    trim_end_frame: int
    trim_start_seconds: float
    trim_end_seconds: float
    transition_duration_seconds: float
    transition_forward_meters: float
    transition_right_meters: float
    transition_facing_degrees: float


class StitchInput(TypedDict):
    character_id: str
    steps: list[MotionStep]


class _ResolvedMotionRequired(TypedDict):
    motion_id: str
    trim_start_frame: int
    trim_end_frame: int
    trim_start_seconds: float
    trim_end_seconds: float


class ResolvedMotionStep(_ResolvedMotionRequired, total=False):
    transition_duration_seconds: float
    transition_forward_meters: float
    transition_right_meters: float
    transition_facing_degrees: float


def _allowed_fields(value: object, *, required: set[str], allowed: set[str]) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError("Stitch objects must be dictionaries")
    if not required <= value.keys() or value.keys() - allowed:
        raise ValueError("Stitch input has missing or unsupported fields")
    return cast(dict[str, object], value)


def _stitch_id(value: object) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value) is None:
        raise ValueError("Stitch IDs need 1-128 letters, digits, underscores, or hyphens")
    return value


def _validate_motion_step(value: object, *, outgoing: bool) -> MotionStep:
    frame_fields = {"trim_start_frame", "trim_end_frame"}
    second_fields = {"trim_start_seconds", "trim_end_seconds"}
    placement_limits = {
        "transition_forward_meters": MAX_OFFSET_METERS,
        "transition_right_meters": MAX_OFFSET_METERS,
        "transition_facing_degrees": MAX_TURN_DEGREES,
    }
    transition_fields = {"transition_duration_seconds", *placement_limits}
    selected = _allowed_fields(
        value,
        required={"motion_id"},
        allowed={"motion_id", *frame_fields, *second_fields, *transition_fields},
    )
    result: dict[str, object] = {"motion_id": _stitch_id(selected["motion_id"])}
    has_frame_range = bool(selected.keys() & frame_fields)
    has_second_range = bool(selected.keys() & second_fields)
    if has_frame_range and has_second_range:
        raise ValueError("Use frames or seconds within a trim, not both")
    for key, item in selected.items():
        if key == "motion_id":
            continue
        number = _finite(item)
        if key in frame_fields:
            if type(item) is not int or not 0 <= number <= MAX_FRAME_INDEX:
                raise ValueError(f"{key} must be a nonnegative GraphQL integer")
            result[key] = item
        elif key in second_fields:
            if number < 0:
                raise ValueError(f"{key} must be nonnegative")
            result[key] = float(number)
        elif outgoing:
            limit = placement_limits.get(key)
            if limit is not None and not -limit <= number <= limit:
                raise ValueError(f"{key} must be between {-limit} and {limit}")
            if (
                key == "transition_duration_seconds"
                and not MIN_TRANSITION_SECONDS <= number <= MAX_TRANSITION_SECONDS
            ):
                raise ValueError("Transition duration must be 0.1-3 seconds")
            result[key] = float(number)
        # Final-step transition settings have scalar checks only and are discarded.
    unit = "frame" if has_frame_range else "seconds"
    start_key, end_key = f"trim_start_{unit}", f"trim_end_{unit}"
    start = cast(int | float, result.get(start_key, 0))
    if (end := result.get(end_key)) is not None and cast(int | float, end) <= start:
        raise ValueError("Trim end must exceed start")
    result[start_key] = start
    if outgoing:
        result.setdefault("transition_duration_seconds", DEFAULT_TRANSITION_SECONDS)
        if selected.keys() & placement_limits.keys():
            for key in placement_limits:
                result.setdefault(key, 0.0)
    return cast(MotionStep, result)


def validate_stitch_input(value: object) -> StitchInput:
    """Validate and copy flat motion steps before preparation or paid work."""
    request = _allowed_fields(
        value, required={"character_id", "steps"}, allowed={"character_id", "steps"}
    )
    character_id = _stitch_id(request["character_id"])
    if not isinstance(steps := request["steps"], list) or len(steps) != 2:
        raise ValueError("Must include exactly two motion objects")
    return {
        "character_id": character_id,
        "steps": [
            _validate_motion_step(steps[0], outgoing=True),
            _validate_motion_step(steps[1], outgoing=False),
        ],
    }


class StitchResult(TypedDict):
    motion: Motion
    resolved_steps: list[ResolvedMotionStep]
