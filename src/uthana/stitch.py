"""Typed sampled-pose inputs for the enhanced stitch preview API.

Sampling and spatial placement belong to the caller's motion loader. These
validators check structure and numerical consistency, not animation quality.
"""

import math
import re
from copy import deepcopy
from typing import Any, Literal, Mapping, TypedDict, cast

from .types import Motion

MAX_FRAME_INDEX = 2**53 - 1


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


def _finite(value):
    try:
        valid = (
            not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)
        )
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


def _allowed_fields(value: object, *, required: set[str], allowed: set[str]) -> dict:
    if not isinstance(value, dict):
        raise ValueError("Stitch objects must be dictionaries")
    missing_fields = not required <= value.keys()
    unsupported_fields = bool(value.keys() - allowed)
    if missing_fields or unsupported_fields:
        raise ValueError("Stitch input has missing or unsupported fields")
    return value


def _stitch_id(value: object) -> None:
    if not isinstance(value, str) or re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value) is None:
        raise ValueError("Stitch IDs need 1-128 letters, digits, underscores, or hyphens")


def _validate_range(value: object) -> None:
    fields = {"start_frame", "end_frame", "start_seconds", "end_seconds"}
    selected = _allowed_fields(value, required=set(), allowed=fields)
    frames = bool(selected.keys() & {"start_frame", "end_frame"})
    seconds = bool(selected.keys() & {"start_seconds", "end_seconds"})
    if frames and seconds:
        raise ValueError("Use frames or seconds within a range, not both")
    for key, number in selected.items():
        if key.endswith("_frame"):
            if type(number) is not int or not 0 <= number <= MAX_FRAME_INDEX:
                raise ValueError("Frame indices must be nonnegative safe integers")
        elif _finite(number) < 0:
            raise ValueError("Range seconds must be nonnegative")
    unit = "frame" if frames else "seconds"
    start = selected.get(f"start_{unit}", 0)
    end = selected.get(f"end_{unit}")
    if end is not None and end <= start:
        raise ValueError("Range end must exceed start")


def validate_stitch_input(value: Mapping[str, Any]) -> StitchInput:
    """Validate the shared typed-step contract without API calls or pose sampling."""
    request = _allowed_fields(
        value, required={"character_id", "steps"}, allowed={"character_id", "steps"}
    )
    _stitch_id(request["character_id"])
    steps = request["steps"]
    if not isinstance(steps, list) or len(steps) != 3:
        raise ValueError("Supported sequence is motion, transition, motion")
    result = deepcopy(request)
    for index, step in enumerate(result["steps"]):
        expected = "transition" if index == 1 else "motion"
        allowed = (
            {"type", "duration_seconds"}
            if index == 1
            else {"type", "motion_id", "range", "placement"}
        )
        required = {"type"} if index == 1 else {"type", "motion_id"}
        _allowed_fields(step, required=required, allowed=allowed)
        if step["type"] != expected:
            raise ValueError("Supported sequence is motion, transition, motion")
        if index == 1:
            duration = _finite(step.get("duration_seconds", 1.0))
            if not 0.1 <= duration <= 3:
                raise ValueError("Transition duration must be 0.1-3 seconds")
            step["duration_seconds"] = duration
            continue
        _stitch_id(step["motion_id"])
        _validate_range(step.setdefault("range", {}))
        if "placement" not in step:
            continue
        if index == 0:
            raise ValueError("Placement is supported only on the arriving motion")
        placement = _allowed_fields(
            step["placement"],
            required=set(),
            allowed={"forward_m", "right_m", "turn_degrees", "absolute"},
        )
        if placement.get("absolute", False) is not False:
            raise ValueError("Only relative placement (absolute: false) is supported")
        placement["absolute"] = False
        for key in ("forward_m", "right_m", "turn_degrees"):
            number = _finite(placement.setdefault(key, 0.0))
            limit = 180 if key == "turn_degrees" else 100
            if not -limit <= number <= limit:
                raise ValueError(f"{key} must be between {-limit} and {limit}")
    return cast(StitchInput, result)
