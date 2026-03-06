# (c) Copyright 2026 Uthana, Inc. All Rights Reserved

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypedDict


class UpdateMotionResult(TypedDict, total=False):
    """Result of update_motion (delete/rename)."""

    id: str
    name: str | None
    deleted: str | None


class VideoToMotionResultPayload(TypedDict, total=False):
    """Inner payload of video-to-motion job result. Motion id at result['result']['id']."""

    id: str


class VideoToMotionJobResult(TypedDict, total=False):
    """Job result for video-to-motion. Motion id at result['result']['id']."""

    result: VideoToMotionResultPayload


class Error(Exception):
    """Base exception for Uthana API errors."""

    pass


class UthanaError(Error):
    """Raised when the API returns an error response."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Uthana API error {status_code}: {message}")


@dataclass
class MotionOutput:
    """Result of a text-to-motion or create-from-gltf request."""

    character_id: str
    motion_id: str


@dataclass
class JobOutput:
    """Result of an async job (e.g. video-to-motion). Poll until status is FINISHED or FAILED.

    For video-to-motion, motion id is at result['result']['id'] when status is FINISHED.
    """

    job_id: str
    status: str
    result: dict | None = None  # Polymorphic by job type; see VideoToMotionJobResult for VTM


@dataclass
class CharacterOutput:
    """Result of a character upload. Includes download URL and auto-rig confidence (0–1)."""

    url: str
    character_id: str
    auto_rig_confidence: float | None = None


@dataclass
class UserInfo:
    """Current authenticated user."""

    id: str
    name: str | None
    email: str | None
    email_verified: bool | None


@dataclass
class OrgInfo:
    """Organization info including motion download quota."""

    id: str
    name: str | None
    motion_download_secs_per_month: float | None
    motion_download_secs_per_month_remaining: float | None


@dataclass
class MotionInfo:
    """Motion metadata from list_motions."""

    id: str
    name: str | None
    created: str | None


@dataclass
class CharacterInfo:
    """Character metadata from list_characters."""

    id: str
    name: str | None
    created: str | None
    updated: str | None


def detect_mesh_format(filepath: str) -> str | None:
    """Detect mesh format from file header. Returns 'glb', 'fbx', or None if unknown."""
    with open(filepath, "rb") as f:
        header = f.read(20)

    if header[:4] == b"glTF":
        return "glb"
    if header.startswith(b"Kaydara FBX Binary"):
        return "fbx"
    if header.startswith(b"; FBX"):
        return "fbx"
    return None


ModelType = Literal["auto", "vqvae-v1", "diffusion-v2"]
OutputFormat = Literal["glb", "fbx"]


@dataclass(frozen=True)
class UthanaCharacters:
    """Pre-built character IDs. Use these without uploading your own character."""

    tar: str = "cXi2eAP19XwQ"
    ava: str = "cmEE2fT4aSaC"
    manny: str = "c43tbGks3crJ"
    quinn: str = "czCjWEMtWxt8"
    y_bot: str = "cJM4ngRqXg83"


DEFAULT_OUTPUT_FORMAT: OutputFormat = "glb"
DEFAULT_TIMEOUT = 120.0
SUPPORTED_VIDEO_FORMATS = frozenset({".mp4", ".mov", ".avi"})
