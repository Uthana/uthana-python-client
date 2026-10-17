"""Typed sampled-pose inputs for the enhanced stitch preview API.

Sampling and spatial placement belong to the caller's motion loader. These
validators check structure and numerical consistency, not animation quality.
"""

import math
from copy import deepcopy
from typing import Any, Mapping, TypedDict, cast


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


class StitchPlacement(TypedDict, total=False):
    forward_m: float
    right_m: float
    facing_degrees: float


class _AutoStitchRequired(TypedDict):
    character_id: str
    prefix_motion_id: str
    suffix_motion_id: str


class AutoStitchInput(_AutoStitchRequired, total=False):
    stitch_duration: float
    prefix_start_seconds: float
    prefix_end_seconds: float
    suffix_start_seconds: float
    suffix_end_seconds: float
    placement: StitchPlacement


def validate_auto_stitch_input(value: Mapping[str, Any]) -> AutoStitchInput:
    """Validate simple inputs without loading assets or submitting a mutation."""
    required = {"character_id", "prefix_motion_id", "suffix_motion_id"}
    allowed = required | {
        "stitch_duration",
        "prefix_start_seconds",
        "prefix_end_seconds",
        "suffix_start_seconds",
        "suffix_end_seconds",
        "placement",
    }
    if not isinstance(value, dict) or not required <= value.keys() or value.keys() - allowed:
        raise ValueError("Automatic stitch input has missing or unsupported fields")
    for key in required:
        if not isinstance(value[key], str) or not value[key].strip() or len(value[key]) > 128:
            raise ValueError(f"{key} must be a nonempty ID of at most 128 characters")
    if not 0.1 <= _finite(value.get("stitch_duration", 1.0)) <= 3:
        raise ValueError("stitch_duration must be between 0.1 and 3 seconds")
    for label in ("prefix", "suffix"):
        start = _finite(value.get(f"{label}_start_seconds", 0.0))
        if start < 0:
            raise ValueError("Trim start must be nonnegative")
        if f"{label}_end_seconds" in value and _finite(value[f"{label}_end_seconds"]) <= start:
            raise ValueError("Trim end must exceed start")
    if "placement" in value:
        placement = value["placement"]
        if not isinstance(placement, dict) or placement.keys() - {
            "forward_m",
            "right_m",
            "facing_degrees",
        }:
            raise ValueError("Unsupported placement fields")
        for key, number in placement.items():
            limit = 180 if key == "facing_degrees" else 100
            if not -limit <= _finite(number) <= limit:
                raise ValueError(f"{key} must be between {-limit} and {limit}")
    return cast(AutoStitchInput, deepcopy(value))
