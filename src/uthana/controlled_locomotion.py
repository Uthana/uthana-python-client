"""Path-controlled locomotion plan types, validation, and offline contract discovery."""

import math
from typing import Literal, TypedDict

MIN_SPEED_MPS = 0.25
MAX_SPEED_MPS = 1.2
MAX_POINTS = 16
MAX_COORDINATE = 10.0
MIN_SEGMENT_LENGTH = 0.05
SUPPORTED_CHARACTERS = ("cQAGzmu5SRR5", "cH32hVsowEyB", "c87BhovBvmQA", "cXi2eAP19XwQ")
SUPPORTED_STYLES = ("neutral_male_a", "crouching", "zombie", "march", "rushed")


class PathPoint(TypedDict):
    right: float
    forward: float


class PaceChange(TypedDict):
    path_fraction: float
    speed_mps: float


class _RequiredPlan(TypedDict):
    points: list[PathPoint]
    pace_changes: list[PaceChange]
    allow_slowing: Literal[True]


class ControlledLocomotionPlan(_RequiredPlan, total=False):
    units: Literal["metres", "character_heights"]
    style: Literal["neutral_male_a", "crouching", "zombie", "march", "rushed"]


class ControlledLocomotionMeasurements(TypedDict):
    duration_seconds: float
    path_length_m: float
    actual_distance_m: float
    max_path_error_m: float
    endpoint_error_m: float
    final_second_drift_m: float
    has_stopped: bool


class ControlledLocomotionResult(TypedDict):
    status: Literal["succeeded", "constraints_not_met"]
    character_id: str
    motion_id: str | None
    measurements: ControlledLocomotionMeasurements


def _record(value: object, *, required: set[str], optional: set[str] | None = None) -> dict:
    if not isinstance(value, dict):
        raise ValueError("Expected a controlled locomotion object")
    keys = set(value)
    if not required <= keys or keys - required - (optional or set()):
        raise ValueError("Controlled locomotion object has missing or unknown fields")
    return value


def _number(value: object, *, field: str, minimum: float, maximum: float) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{field} must be a finite number between {minimum} and {maximum}")
    try:
        number = float(value)
    except OverflowError:
        raise ValueError(f"{field} must be finite") from None
    if not math.isfinite(number) or not minimum <= number <= maximum:
        raise ValueError(f"{field} must be a finite number between {minimum} and {maximum}")
    return number


def normalize_controlled_locomotion_plan(value: object) -> ControlledLocomotionPlan:
    """Validate and copy a plan, making omitted defaults explicit without mutating input.

    Smoothed path length and character-height conversion are checked by the worker.
    This does not check account access or whether the feature is enabled.
    """
    plan = _record(
        value, required={"points", "pace_changes", "allow_slowing"}, optional={"units", "style"}
    )
    units = plan.get("units", "metres")
    style = plan.get("style", "neutral_male_a")
    if units not in ("metres", "character_heights"):
        raise ValueError("units must be metres or character_heights")
    if style not in SUPPORTED_STYLES:
        raise ValueError("style must be one of the supported controlled locomotion styles")
    if plan["allow_slowing"] is not True:
        raise ValueError("allow_slowing must be true; exact timing is not supported")
    raw_points = plan["points"]
    if not isinstance(raw_points, list) or not 2 <= len(raw_points) <= MAX_POINTS:
        raise ValueError(f"points must contain 2-{MAX_POINTS} waypoints")
    points: list[PathPoint] = []
    for raw_point in raw_points:
        point = _record(raw_point, required={"right", "forward"})
        points.append(
            {
                "right": _number(
                    point["right"], field="right", minimum=-MAX_COORDINATE, maximum=MAX_COORDINATE
                ),
                "forward": _number(
                    point["forward"],
                    field="forward",
                    minimum=-MAX_COORDINATE,
                    maximum=MAX_COORDINATE,
                ),
            }
        )
    if points[0] != {"right": 0, "forward": 0}:
        raise ValueError("points must start at right=0, forward=0")
    if points[1]["right"] != 0 or points[1]["forward"] <= 0:
        raise ValueError("The first segment must head forward")
    for previous, current in zip(points, points[1:]):
        if (
            math.hypot(
                current["right"] - previous["right"], current["forward"] - previous["forward"]
            )
            < MIN_SEGMENT_LENGTH
        ):
            raise ValueError(
                f"Adjacent path points must be at least {MIN_SEGMENT_LENGTH} units apart"
            )
    raw_paces = plan["pace_changes"]
    if not isinstance(raw_paces, list) or not 1 <= len(raw_paces) <= MAX_POINTS:
        raise ValueError(f"pace_changes must contain 1-{MAX_POINTS} entries")
    paces: list[PaceChange] = []
    for raw_pace in raw_paces:
        pace = _record(raw_pace, required={"path_fraction", "speed_mps"})
        fraction = _number(pace["path_fraction"], field="path_fraction", minimum=0, maximum=1)
        if (
            fraction >= 1
            or (not paces and fraction != 0)
            or (paces and fraction <= paces[-1]["path_fraction"])
        ):
            raise ValueError("pace_changes must start at 0 and increase strictly below 1")
        paces.append(
            {
                "path_fraction": fraction,
                "speed_mps": _number(
                    pace["speed_mps"],
                    field="speed_mps",
                    minimum=MIN_SPEED_MPS,
                    maximum=MAX_SPEED_MPS,
                ),
            }
        )
    return {
        "units": units,
        "style": style,
        "points": points,
        "pace_changes": paces,
        "allow_slowing": True,
    }


def controlled_locomotion_options() -> dict[str, object]:
    """Return a fresh offline contract catalog, not deployment or account eligibility."""
    return {
        "supported_character_ids": list(SUPPORTED_CHARACTERS),
        "styles": list(SUPPORTED_STYLES),
        "units": ["metres", "character_heights"],
        "min_points": 2,
        "max_points": MAX_POINTS,
        "min_speed_mps": MIN_SPEED_MPS,
        "max_speed_mps": MAX_SPEED_MPS,
        "max_coordinate": MAX_COORDINATE,
        "min_segment_length": MIN_SEGMENT_LENGTH,
        "max_pace_changes": MAX_POINTS,
        "max_path_length_m": 12.0,
        "max_duration_seconds": 20.0,
        "allow_slowing_required": True,
        "availability": "Requires an enabled backend and authorized character access",
        "axes": "Fixed initial right/forward; start at origin and head forward",
        "pace": "By smoothed-path progress, not elapsed time; ends with a stop",
    }
