# (c) Copyright 2026 Uthana, Inc. All Rights Reserved

"""Helper functions for preparing API requests."""

import os

from .types import SUPPORTED_VIDEO_FORMATS, Error, detect_mesh_format

# Maps model strings to the API string the server currently accepts.
#
# VTM: old alias maps forward to the new canonical name (server already accepts these).
# TTM sync: both new canonical names AND legacy friendly names map down to current API strings.
#   Remove the TTM entries once the API starts accepting "text-to-motion-1.0" / "2.0".
LEGACY_MODEL_SHIM: dict[str, str] = {
    # VTM legacy alias → new canonical (API already accepts these)
    "video-to-motion-v2": "video-to-motion-2.0",
    # TTM sync: canonical X.Y → current API strings (remove when API accepts X.Y directly)
    "text-to-motion-1.0": "text-to-motion",
    "text-to-motion-2.0": "text-to-motion-bucmd",
    # TTM sync: legacy friendly names → current API strings (backward compat)
    "vqvae-v1": "text-to-motion",
    "diffusion-v2": "text-to-motion-bucmd",
}


def normalize_model_name(model: str) -> str:
    """Map legacy/non-X.Y model names to their canonical X.Y form."""
    return LEGACY_MODEL_SHIM.get(model, model)


def prepare_create_character(
    file_path: str,
    auto_rig: bool | None,
    front_facing: bool | None,
    rerig_target: str | None,
    include_fingers: bool | None,
) -> tuple[dict, str, str, str]:
    """Prepare variables and metadata for create_character mutation."""
    filename = os.path.basename(file_path)
    name = os.path.splitext(filename)[0]
    ext = detect_mesh_format(file_path)
    if ext is None:
        ext = os.path.splitext(filename)[1].lstrip(".")

    variables = {
        "name": name,
        "file": None,
        "auto_rig": auto_rig,
        "auto_rig_front_facing": front_facing,
        "rerig_target": rerig_target,
        "include_fingers": include_fingers,
    }
    return variables, name, ext, filename


def prepare_video_to_motion(file_path: str, motion_name: str | None) -> tuple[dict, str]:
    """Validate video format and build variables for create_video_to_motion."""
    filename = os.path.basename(file_path)
    ext = os.path.splitext(filename)[1].lower()
    if ext not in SUPPORTED_VIDEO_FORMATS:
        supported = ", ".join(sorted(SUPPORTED_VIDEO_FORMATS))
        raise Error(f"Unsupported video format '{ext}'. Supported: {supported}")
    if motion_name is None:
        motion_name = os.path.splitext(filename)[0]
    variables = {"motion_name": motion_name, "file": None}
    return variables, filename
