# (c) Copyright 2026 Uthana, Inc. All Rights Reserved

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypedDict

# -----------------------------------------------------------------------------
# Exceptions
# -----------------------------------------------------------------------------


class Error(Exception):
    """Base exception for Uthana API errors."""

    pass


class UthanaError(Error):
    """Raised when the API returns an error response."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Uthana API error {status_code}: {message}")


# -----------------------------------------------------------------------------
# Entity types (from queries: get, list)
# -----------------------------------------------------------------------------


class User(TypedDict, total=False):
    """User object from org.get_user."""

    id: str
    name: str | None
    email: str | None
    email_verified: bool | None


class Org(TypedDict, total=False):
    """Org object from org.get_org."""

    id: str
    name: str | None
    motion_download_secs_per_month: float | None
    motion_download_secs_per_month_remaining: float | None


class Character(TypedDict, total=False):
    """Character object from characters.list."""

    id: str
    name: str | None
    created: str | None
    updated: str | None


class Motion(TypedDict, total=False):
    """Motion object from motions.list or update_motion (delete/rename)."""

    id: str
    name: str | None
    created: str | None
    deleted: str | None


class Job(TypedDict, total=False):
    """Job object from jobs.get, jobs.list, or vtm.create. Poll until status is FINISHED or FAILED.

    For video-to-motion, motion id is at result['result']['id'] when status is FINISHED.
    """

    id: str
    status: str
    method: str | None
    created: str | None
    started: str | None
    ended: str | None
    result: dict | None


# -----------------------------------------------------------------------------
# Mutation result types
# -----------------------------------------------------------------------------


@dataclass
class TextToMotionResult:
    """Result of ttm.create or motions.bake_with_changes mutation."""

    character_id: str
    motion_id: str


@dataclass
class CreateCharacterResult:
    """Result of characters.create_from_file."""

    url: str
    character_id: str
    auto_rig_confidence: float | None = None


@dataclass
class CharacterPreviewResult:
    """Intermediate result of characters.create_from_prompt when no on_previews_ready
    callback is provided. Pass to characters.generate_from_image to finalize the character."""

    character_id: str
    previews: list
    prompt: str


@dataclass
class CreateFromGeneratedImageResult:
    """Result of characters.create_from_prompt / characters.create_from_image (with callback where
    applicable), or characters.generate_from_image."""

    character: dict
    auto_rig_confidence: float | None = None


# Alias for vtm.create return type
VideoToMotionResult = Job


# -----------------------------------------------------------------------------
# Constants and literals
# -----------------------------------------------------------------------------


TtmModelType = Literal["vqvae-v1", "diffusion-v2"]
VtmModelType = Literal["video-to-motion-v1", "video-to-motion-v2"]
ModelType = Literal["auto"] | TtmModelType | VtmModelType
OutputFormat = Literal["glb", "fbx"]

DEFAULT_OUTPUT_FORMAT: OutputFormat = "glb"
DEFAULT_TIMEOUT = 120.0
SUPPORTED_VIDEO_FORMATS = frozenset({".mp4", ".mov", ".avi"})


@dataclass(frozen=True)
class UthanaCharacters:
    """Pre-built character IDs. Use these without uploading your own character."""

    tar: str = "cXi2eAP19XwQ"
    ava: str = "cmEE2fT4aSaC"
    manny: str = "c43tbGks3crJ"
    quinn: str = "czCjWEMtWxt8"
    y_bot: str = "cJM4ngRqXg83"


# -----------------------------------------------------------------------------
# Utilities
# -----------------------------------------------------------------------------


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
