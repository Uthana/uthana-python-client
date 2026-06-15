# (c) Copyright 2026 Uthana, Inc. All Rights Reserved

"""Helper functions for preparing API requests."""

import os

from .types import SUPPORTED_VIDEO_FORMATS, Error, detect_mesh_format

# Maps legacy/non-X.Y model strings to their canonical X.Y equivalents.
# Update this table when the API renames models; no other code changes required.
LEGACY_MODEL_SHIM: dict[str, str] = {
    "video-to-motion-v2": "video-to-motion-2.0",
    "vqvae-v1": "text-to-motion-1.0",
    "text-to-motion": "text-to-motion-1.0",
    "diffusion-v2": "text-to-motion-2.0",
    "text-to-motion-bucmd": "text-to-motion-2.0",
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
