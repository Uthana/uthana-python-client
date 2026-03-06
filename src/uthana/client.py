# (c) Copyright 2026 Uthana, Inc. All Rights Reserved

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from importlib.metadata import version as _pkg_version
from typing import TYPE_CHECKING, Literal

import httpx

from .models import get_default_stitch_model, get_default_ttm_model, get_default_vtm_model

if TYPE_CHECKING:
    from typing import Any


class Error(Exception):
    """Base exception for Uthana API errors."""

    pass


class APIError(Error):
    """Raised when the API returns an error response."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Uthana API error {status_code}: {message}")


@dataclass
class MotionOutput:
    character_id: str
    motion_id: str


@dataclass
class JobOutput:
    job_id: str
    status: str
    result: dict | None = None


@dataclass
class CharacterOutput:
    url: str
    character_id: str
    auto_rig_confidence: float | None = None


@dataclass
class UserInfo:
    id: str
    name: str | None
    email: str | None
    email_verified: bool | None


@dataclass
class OrgInfo:
    id: str
    name: str | None
    motion_download_secs_per_month: float | None
    motion_download_secs_per_month_remaining: float | None


@dataclass
class MotionInfo:
    id: str
    name: str | None
    created: str | None


@dataclass
class CharacterInfo:
    id: str
    name: str | None
    created: str | None
    updated: str | None


def detect_mesh_format(filepath: str) -> str | None:
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
    tar: str = "cXi2eAP19XwQ"
    ava: str = "cmEE2fT4aSaC"
    manny: str = "c43tbGks3crJ"
    quinn: str = "czCjWEMtWxt8"
    y_bot: str = "cJM4ngRqXg83"


DEFAULT_OUTPUT_FORMAT: OutputFormat = "glb"

DEFAULT_TIMEOUT = 120.0
_SUPPORTED_VIDEO_FORMATS = {".mp4", ".mov", ".avi"}

_TEXT_TO_MOTION_VQVAE_V1_MUTATION = """
mutation TextToMotion($prompt: String!, $character_id: String, $model: String!, $foot_ik: Boolean) {
    create_text_to_motion(prompt: $prompt, character_id: $character_id, model: $model, foot_ik: $foot_ik) {
        motion {
            id
            name
        }
    }
}
"""

_TEXT_TO_MOTION_DIFFUSION_V2_MUTATION = """
mutation CreateTextToMotion($prompt: String!, $character_id: String, $model: String!, $foot_ik: Boolean, $cfg_scale: Float, $length: Float, $seed: Int, $retargeting_ik: Boolean) {
    create_text_to_motion(prompt: $prompt, character_id: $character_id, model: $model, foot_ik: $foot_ik, cfg_scale: $cfg_scale, length: $length, seed: $seed, retargeting_ik: $retargeting_ik) {
        motion {
            id
            name
        }
    }
}
"""

_CREATE_CHARACTER_MUTATION = """
mutation CreateCharacter($name: String!, $file: Upload!, $auto_rig: Boolean, $auto_rig_front_facing: Boolean) {
    create_character(name: $name, file: $file, auto_rig: $auto_rig, auto_rig_front_facing: $auto_rig_front_facing) {
        character {
            id
            name
        }
        auto_rig_confidence
    }
}
"""

_CREATE_VIDEO_TO_MOTION_MUTATION = """
mutation CreateVideoToMotion($file: Upload!, $motion_name: String!, $model: String) {
    create_video_to_motion(file: $file, motion_name: $motion_name, model: $model) {
        job {
            id
            status
        }
    }
}
"""

_GET_JOB_QUERY = """
query GetJob($job_id: String!) {
    job(job_id: $job_id) {
        id
        status
        result
    }
}
"""

_LIST_MOTIONS_QUERY = """
query {
    motions {
        id
        name
        created
    }
}
"""

_LIST_CHARACTERS_QUERY = """
query {
    characters {
        id
        name
        created
        updated
    }
}
"""

_GET_USER_QUERY = """
query {
    user {
        id
        name
        email
        email_verified
    }
}
"""

_GET_ORG_QUERY = """
query {
    org {
        id
        name
        motion_download_secs_per_month
        motion_download_secs_per_month_remaining
    }
}
"""

_CREATE_MOTION_FROM_GLTF_MUTATION = """
mutation create_motion_from_gltf($gltf: String!, $motionName: String!, $characterId: String) {
    create_motion_from_gltf(gltf: $gltf, motion_name: $motionName, character_id: $characterId) {
        motion { id }
    }
}
"""

_UPDATE_MOTION_MUTATION = """
mutation update_motion($id: String!, $name: String, $deleted: Boolean) {
    update_motion(id: $id, name: $name, deleted: $deleted) {
        id
        name
        deleted
    }
}
"""

_CREATE_MOTION_FAVORITE_MUTATION = """
mutation create_motion_favorite($motion_id: String!) {
    create_motion_favorite(motion_id: $motion_id) {
        id
        motion_id
    }
}
"""

_DELETE_MOTION_FAVORITE_MUTATION = """
mutation delete_motion_favorite($motion_id: String!) {
    delete_motion_favorite(motion_id: $motion_id) {
        id
    }
}
"""

_CREATE_STITCHED_MOTION_MUTATION = """
mutation create_stitched_motion($character_id: String!, $leading_motion_id: String!, $trailing_motion_id: String!, $duration: Float!, $model: String) {
    create_stitched_motion(character_id: $character_id, leading_motion_id: $leading_motion_id, trailing_motion_id: $trailing_motion_id, duration: $duration, model: $model) {
        ok
        motion_id
    }
}
"""


class _BaseSubClient:
    def __init__(self, parent: "Uthana") -> None:
        self._parent = parent


class TTMClient(_BaseSubClient):
    """Text to motion: generate animations from natural language prompts."""

    def create_sync(
        self,
        prompt: str,
        *,
        model: ModelType | None = None,
        character_id: str | None = None,
        foot_ik: bool | None = None,
        length: float | None = None,
        cfg_scale: float | None = None,
        seed: int | None = None,
        internal_ik: bool | None = None,
    ) -> MotionOutput:
        """Generate a 3D character animation from a natural language prompt.

        Model defaults to the value in models.ini when omitted or set to \"auto\".
        """
        if model is None or model == "auto":
            model = get_default_ttm_model()
        mutation, variables = self._parent._prepare_and_select_text_to_motion(
            model, prompt, character_id, foot_ik, length, cfg_scale, seed, internal_ik
        )
        data = self._parent._graphql(mutation, variables)
        motion_id = data["create_text_to_motion"]["motion"]["id"]
        if character_id is None:
            character_id = UthanaCharacters.tar
        return MotionOutput(character_id=character_id, motion_id=motion_id)

    async def create(
        self,
        prompt: str,
        *,
        model: ModelType | None = None,
        character_id: str | None = None,
        foot_ik: bool | None = None,
        length: float | None = None,
        cfg_scale: float | None = None,
        seed: int | None = None,
        internal_ik: bool | None = None,
    ) -> MotionOutput:
        """Generate a 3D character animation from a natural language prompt (async).

        Model defaults to the value in models.ini when omitted or set to \"auto\".
        """
        if model is None or model == "auto":
            model = get_default_ttm_model()
        mutation, variables = self._parent._prepare_and_select_text_to_motion(
            model, prompt, character_id, foot_ik, length, cfg_scale, seed, internal_ik
        )
        data = await self._parent._agraphql(mutation, variables)
        motion_id = data["create_text_to_motion"]["motion"]["id"]
        if character_id is None:
            character_id = UthanaCharacters.tar
        return MotionOutput(character_id=character_id, motion_id=motion_id)


class VTMClient(_BaseSubClient):
    """Video to motion: extract motion capture from video files."""

    def create_sync(
        self,
        file_path: str,
        *,
        motion_name: str | None = None,
        model: str | None = None,
    ) -> JobOutput:
        """Extract motion capture data from a video (sync). Returns a job to poll via jobs.get_sync().

        Model defaults to the value in models.ini when omitted or set to \"auto\".
        """
        variables, filename = Uthana._prepare_video_to_motion(file_path, motion_name)
        if model is None or model == "auto":
            model = get_default_vtm_model()
        variables["model"] = model
        operations = json.dumps({"query": _CREATE_VIDEO_TO_MOTION_MUTATION, "variables": variables})
        map_data = json.dumps({"0": ["variables.file"]})

        with open(file_path, "rb") as f:
            response = self._parent.session.post(
                self._parent.graphql_url,
                data={"operations": operations, "map": map_data},
                files={"0": (filename, f, "application/octet-stream")},
            )

        result = self._parent._check_response(response)
        job = result["data"]["create_video_to_motion"]["job"]
        return JobOutput(job_id=job["id"], status=job["status"])

    async def create(
        self,
        file_path: str,
        *,
        motion_name: str | None = None,
        model: str | None = None,
    ) -> JobOutput:
        """Extract motion capture data from a video. Returns a job to poll via jobs.get().

        Model defaults to the value in models.ini when omitted or set to \"auto\".
        """
        variables, filename = Uthana._prepare_video_to_motion(file_path, motion_name)
        if model is None or model == "auto":
            model = get_default_vtm_model()
        variables["model"] = model
        operations = json.dumps({"query": _CREATE_VIDEO_TO_MOTION_MUTATION, "variables": variables})
        map_data = json.dumps({"0": ["variables.file"]})

        with open(file_path, "rb") as f:
            response = await self._parent.async_client.post(
                self._parent.graphql_url,
                data={"operations": operations, "map": map_data},
                files={"0": (filename, f, "application/octet-stream")},
            )

        result = self._parent._check_response(response)
        job = result["data"]["create_video_to_motion"]["job"]
        return JobOutput(job_id=job["id"], status=job["status"])


class CharactersClient(_BaseSubClient):
    """Character management: upload, list, download, and create motions from GLTF."""

    def create_sync(
        self,
        file_path: str,
        *,
        auto_rig: bool | None = None,
        front_facing: bool | None = None,
    ) -> CharacterOutput:
        """Upload and optionally auto-rig a 3D character model (sync)."""
        variables, name, ext, _ = Uthana._prepare_create_character(
            file_path, auto_rig, front_facing
        )
        operations = json.dumps({"query": _CREATE_CHARACTER_MUTATION, "variables": variables})
        map_data = json.dumps({"0": ["variables.file"]})

        with open(file_path, "rb") as f:
            response = self._parent.session.post(
                self._parent.graphql_url,
                data={"operations": operations, "map": map_data},
                files={"0": (f"{name}.{ext}", f, "application/octet-stream")},
            )

        result = self._parent._check_response(response)
        return self._parent._build_character_output(result, ext)

    async def create(
        self,
        file_path: str,
        *,
        auto_rig: bool | None = None,
        front_facing: bool | None = None,
    ) -> CharacterOutput:
        """Upload and optionally auto-rig a 3D character model."""
        variables, name, ext, _ = Uthana._prepare_create_character(
            file_path, auto_rig, front_facing
        )
        operations = json.dumps({"query": _CREATE_CHARACTER_MUTATION, "variables": variables})
        map_data = json.dumps({"0": ["variables.file"]})

        with open(file_path, "rb") as f:
            response = await self._parent.async_client.post(
                self._parent.graphql_url,
                data={"operations": operations, "map": map_data},
                files={"0": (f"{name}.{ext}", f, "application/octet-stream")},
            )

        result = self._parent._check_response(response)
        return self._parent._build_character_output(result, ext)

    def list_sync(self) -> list[CharacterInfo]:  # noqa: A001
        """List all characters for the authenticated user (sync)."""
        data = self._parent._graphql(_LIST_CHARACTERS_QUERY)
        raw = data.get("characters", [])
        return [
            CharacterInfo(
                id=c["id"],
                name=c.get("name"),
                created=c.get("created"),
                updated=c.get("updated"),
            )
            for c in raw
        ]

    async def list(self) -> list[CharacterInfo]:  # noqa: A001
        """List all characters for the authenticated user."""
        data = await self._parent._agraphql(_LIST_CHARACTERS_QUERY)
        raw = data.get("characters", [])
        return [
            CharacterInfo(
                id=c["id"],
                name=c.get("name"),
                created=c.get("created"),
                updated=c.get("updated"),
            )
            for c in raw
        ]

    def download_sync(
        self,
        character_id: str,
        *,
        output_format: OutputFormat = DEFAULT_OUTPUT_FORMAT,
    ) -> bytes:
        """Download a character model in the requested format (sync)."""
        ext = output_format.lower()
        url = f"{self._parent.base_url}/motion/bundle/{character_id}/character.{ext}"
        response = self._parent.session.get(url)
        if not response.is_success:
            raise APIError(response.status_code, response.text)
        return response.content

    async def download(
        self,
        character_id: str,
        *,
        output_format: OutputFormat = DEFAULT_OUTPUT_FORMAT,
    ) -> bytes:
        """Download a character model in the requested format."""
        ext = output_format.lower()
        url = f"{self._parent.base_url}/motion/bundle/{character_id}/character.{ext}"
        response = await self._parent.async_client.get(url)
        if not response.is_success:
            raise APIError(response.status_code, response.text)
        return response.content

    def download_preview_sync(self, character_id: str, motion_id: str) -> bytes:
        """Download motion preview WebM (does not charge download seconds) (sync)."""
        url = f"{self._parent.base_url}/app/preview/{character_id}/{motion_id}/preview.webm"
        response = self._parent.session.get(url, timeout=60.0)
        if not response.is_success:
            raise APIError(response.status_code, response.text)
        return response.content

    async def download_preview(self, character_id: str, motion_id: str) -> bytes:
        """Download motion preview WebM (does not charge download seconds)."""
        url = f"{self._parent.base_url}/app/preview/{character_id}/{motion_id}/preview.webm"
        response = await self._parent.async_client.get(url, timeout=60.0)
        if not response.is_success:
            raise APIError(response.status_code, response.text)
        return response.content

    def create_from_gltf_sync(
        self,
        gltf_content: str,
        motion_name: str,
        *,
        character_id: str | None = None,
    ) -> MotionOutput:
        """Upload GLTF content as a new motion (sync). Returns motion_id and character_id."""
        char_id = character_id or UthanaCharacters.tar
        variables = {
            "gltf": gltf_content,
            "motionName": motion_name,
            "characterId": char_id,
        }
        data = self._parent._graphql(_CREATE_MOTION_FROM_GLTF_MUTATION, variables)
        gltf_data = data.get("create_motion_from_gltf", {})
        motion = gltf_data.get("motion") or {}
        motion_id = motion.get("id")
        if not motion_id:
            raise APIError(400, "create_motion_from_gltf did not return motion id")
        return MotionOutput(character_id=char_id, motion_id=motion_id)

    async def create_from_gltf(
        self,
        gltf_content: str,
        motion_name: str,
        *,
        character_id: str | None = None,
    ) -> MotionOutput:
        """Upload GLTF content as a new motion. Returns motion_id and character_id."""
        char_id = character_id or UthanaCharacters.tar
        variables = {
            "gltf": gltf_content,
            "motionName": motion_name,
            "characterId": char_id,
        }
        data = await self._parent._agraphql(_CREATE_MOTION_FROM_GLTF_MUTATION, variables)
        gltf_data = data.get("create_motion_from_gltf", {})
        motion = gltf_data.get("motion") or {}
        motion_id = motion.get("id")
        if not motion_id:
            raise APIError(400, "create_motion_from_gltf did not return motion id")
        return MotionOutput(character_id=char_id, motion_id=motion_id)


class MotionsClient(_BaseSubClient):
    """Motion management: list, download, delete, rename, favorite, stitch."""

    def list_sync(self) -> list[MotionInfo]:  # noqa: A001
        """List all motions for the authenticated user (sync)."""
        data = self._parent._graphql(_LIST_MOTIONS_QUERY)
        raw = data.get("motions", [])
        return [
            MotionInfo(
                id=m["id"],
                name=m.get("name"),
                created=m.get("created"),
            )
            for m in raw
        ]

    async def list(self) -> list[MotionInfo]:  # noqa: A001
        """List all motions for the authenticated user."""
        data = await self._parent._agraphql(_LIST_MOTIONS_QUERY)
        raw = data.get("motions", [])
        return [
            MotionInfo(
                id=m["id"],
                name=m.get("name"),
                created=m.get("created"),
            )
            for m in raw
        ]

    def download_sync(
        self,
        character_id: str,
        motion_id: str,
        *,
        output_format: OutputFormat = DEFAULT_OUTPUT_FORMAT,
        fps: int | None = None,
        no_mesh: bool | None = None,
    ) -> bytes:
        """Download a motion animation file, retargeted to the given character (sync)."""
        url = self._parent._motion_url(character_id, motion_id, output_format, fps, no_mesh)
        response = self._parent.session.get(url)
        if not response.is_success:
            raise APIError(response.status_code, response.text)
        return response.content

    async def download(
        self,
        character_id: str,
        motion_id: str,
        *,
        output_format: OutputFormat = DEFAULT_OUTPUT_FORMAT,
        fps: int | None = None,
        no_mesh: bool | None = None,
    ) -> bytes:
        """Download a motion animation file, retargeted to the given character."""
        url = self._parent._motion_url(character_id, motion_id, output_format, fps, no_mesh)
        response = await self._parent.async_client.get(url)
        if not response.is_success:
            raise APIError(response.status_code, response.text)
        return response.content

    def delete_sync(self, motion_id: str) -> dict[str, "Any"]:
        """Soft-delete a motion by ID (sync)."""
        data = self._parent._graphql(_UPDATE_MOTION_MUTATION, {"id": motion_id, "deleted": True})
        return data.get("update_motion", {})

    async def delete(self, motion_id: str) -> dict[str, "Any"]:
        """Soft-delete a motion by ID."""
        data = await self._parent._agraphql(
            _UPDATE_MOTION_MUTATION, {"id": motion_id, "deleted": True}
        )
        return data.get("update_motion", {})

    def rename_sync(self, motion_id: str, new_name: str) -> dict[str, "Any"]:
        """Rename a motion by ID (sync)."""
        data = self._parent._graphql(_UPDATE_MOTION_MUTATION, {"id": motion_id, "name": new_name})
        return data.get("update_motion", {})

    async def rename(self, motion_id: str, new_name: str) -> dict[str, "Any"]:
        """Rename a motion by ID."""
        data = await self._parent._agraphql(
            _UPDATE_MOTION_MUTATION, {"id": motion_id, "name": new_name}
        )
        return data.get("update_motion", {})

    def favorite_sync(self, motion_id: str, favorite: bool) -> None:
        """Set or unset a motion as favorite (sync)."""
        if favorite:
            self._parent._graphql(_CREATE_MOTION_FAVORITE_MUTATION, {"motion_id": motion_id})
        else:
            self._parent._graphql(_DELETE_MOTION_FAVORITE_MUTATION, {"motion_id": motion_id})

    async def favorite(self, motion_id: str, favorite: bool) -> None:
        """Set or unset a motion as favorite."""
        if favorite:
            await self._parent._agraphql(_CREATE_MOTION_FAVORITE_MUTATION, {"motion_id": motion_id})
        else:
            await self._parent._agraphql(_DELETE_MOTION_FAVORITE_MUTATION, {"motion_id": motion_id})

    def create_stitched_sync(
        self,
        character_id: str,
        leading_motion_id: str,
        trailing_motion_id: str,
        duration: float,
        *,
        model: str | None = None,
    ) -> MotionOutput:
        """Create a stitched motion from two motions with a blend duration (sync).

        Model defaults to the value in models.ini when omitted or set to \"auto\".
        """
        variables: dict[str, object] = {
            "character_id": character_id,
            "leading_motion_id": leading_motion_id,
            "trailing_motion_id": trailing_motion_id,
            "duration": duration,
        }
        if model is None or model == "auto":
            model = get_default_stitch_model()
        variables["model"] = model
        data = self._parent._graphql(_CREATE_STITCHED_MOTION_MUTATION, variables)
        stitch_data = data.get("create_stitched_motion", {})
        motion_id = stitch_data.get("motion_id")
        if not motion_id:
            raise APIError(400, "create_stitched_motion did not return motion_id")
        return MotionOutput(character_id=character_id, motion_id=motion_id)

    async def create_stitched(
        self,
        character_id: str,
        leading_motion_id: str,
        trailing_motion_id: str,
        duration: float,
        *,
        model: str | None = None,
    ) -> MotionOutput:
        """Create a stitched motion from two motions with a blend duration.

        Model defaults to the value in models.ini when omitted or set to \"auto\".
        """
        variables: dict[str, object] = {
            "character_id": character_id,
            "leading_motion_id": leading_motion_id,
            "trailing_motion_id": trailing_motion_id,
            "duration": duration,
        }
        if model is None or model == "auto":
            model = get_default_stitch_model()
        variables["model"] = model
        data = await self._parent._agraphql(_CREATE_STITCHED_MOTION_MUTATION, variables)
        stitch_data = data.get("create_stitched_motion", {})
        motion_id = stitch_data.get("motion_id")
        if not motion_id:
            raise APIError(400, "create_stitched_motion did not return motion_id")
        return MotionOutput(character_id=character_id, motion_id=motion_id)


class OrgClient(_BaseSubClient):
    """Organization and user info."""

    def get_user_sync(self) -> UserInfo:
        """Get current user information (sync)."""
        data = self._parent._graphql(_GET_USER_QUERY)
        u = data.get("user") or {}
        return UserInfo(
            id=u.get("id", ""),
            name=u.get("name"),
            email=u.get("email"),
            email_verified=u.get("email_verified"),
        )

    async def get_user(self) -> UserInfo:
        """Get current user information."""
        data = await self._parent._agraphql(_GET_USER_QUERY)
        u = data.get("user") or {}
        return UserInfo(
            id=u.get("id", ""),
            name=u.get("name"),
            email=u.get("email"),
            email_verified=u.get("email_verified"),
        )

    def get_org_sync(self) -> OrgInfo:
        """Get current organization information including quota (sync)."""
        data = self._parent._graphql(_GET_ORG_QUERY)
        o = data.get("org") or {}
        return OrgInfo(
            id=o.get("id", ""),
            name=o.get("name"),
            motion_download_secs_per_month=o.get("motion_download_secs_per_month"),
            motion_download_secs_per_month_remaining=o.get(
                "motion_download_secs_per_month_remaining"
            ),
        )

    async def get_org(self) -> OrgInfo:
        """Get current organization information including quota."""
        data = await self._parent._agraphql(_GET_ORG_QUERY)
        o = data.get("org") or {}
        return OrgInfo(
            id=o.get("id", ""),
            name=o.get("name"),
            motion_download_secs_per_month=o.get("motion_download_secs_per_month"),
            motion_download_secs_per_month_remaining=o.get(
                "motion_download_secs_per_month_remaining"
            ),
        )


class JobsClient(_BaseSubClient):
    """Async job polling for video to motion and other long-running operations."""

    def get_sync(self, job_id: str) -> JobOutput:
        """Get the status and result of an async job (sync)."""
        data = self._parent._graphql(_GET_JOB_QUERY, {"job_id": job_id})
        job = data["job"]
        result = job.get("result")
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except json.JSONDecodeError:
                pass
        return JobOutput(
            job_id=job["id"],
            status=job["status"],
            result=result,
        )

    async def get(self, job_id: str) -> JobOutput:
        """Get the status and result of an async job."""
        data = await self._parent._agraphql(_GET_JOB_QUERY, {"job_id": job_id})
        job = data["job"]
        result = job.get("result")
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except json.JSONDecodeError:
                pass
        return JobOutput(
            job_id=job["id"],
            status=job["status"],
            result=result,
        )


class Uthana:
    """Main client for the Uthana API. Use sub-clients for organized access:

    - ttm: text to motion
    - vtm: video to motion
    - characters: character management
    - motions: motion management
    - org: user and organization info
    - jobs: async job polling
    """

    def __init__(
        self,
        api_key: str,
        *,
        staging: bool = False,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        domain = "staging.uthana.com" if staging else "uthana.com"
        self.base_url = f"https://{domain}"
        self.graphql_url = f"{self.base_url}/graphql"
        self.session = httpx.Client(auth=(api_key, ""), timeout=timeout)
        self.async_client = httpx.AsyncClient(auth=(api_key, ""), timeout=timeout)
        self._log_init(domain, "uthana-python", _pkg_version("uthana"), api_key)

        self.ttm = TTMClient(self)
        self.vtm = VTMClient(self)
        self.characters = CharactersClient(self)
        self.motions = MotionsClient(self)
        self.org = OrgClient(self)
        self.jobs = JobsClient(self)

    def _log_init(self, domain: str, app: str, version: str, apikey: str) -> dict:
        headers = {"User-Agent": f"{app}/{version}"}
        r = self.session.post(
            f"https://{domain}/graphql", json={"query": "{user{id}}"}, headers=headers
        )
        r.raise_for_status()
        data = r.json().get("data") or {}
        user = data.get("user") or {}
        uid = user.get("id") if isinstance(user, dict) else None

        anon_id = "00000000" + str(uuid.uuid1(clock_seq=1))[8:]

        evt = {
            "type": "track",
            "event": "initialized",
            "app": app,
            "userId": uid,
            "anonymousId": anon_id,
            "meta": {},
        }

        r = self.session.post(f"https://{domain}/event", json=evt, headers=headers)
        r.raise_for_status()
        return r.json()

    def _graphql(self, query: str, variables: dict | None = None) -> dict:
        response = self.session.post(
            self.graphql_url,
            json={"query": query, "variables": variables or {}},
        )
        if not response.is_success:
            raise APIError(response.status_code, response.text)
        result = response.json()
        if "errors" in result:
            raise APIError(400, f"GraphQL errors: {result['errors']}")
        return result.get("data", {})

    async def _agraphql(self, query: str, variables: dict | None = None) -> dict:
        response = await self.async_client.post(
            self.graphql_url,
            json={"query": query, "variables": variables or {}},
        )
        if not response.is_success:
            raise APIError(response.status_code, response.text)
        result = response.json()
        if "errors" in result:
            raise APIError(400, f"GraphQL errors: {result['errors']}")
        return result.get("data", {})

    def _check_response(self, response: httpx.Response) -> dict:
        if not response.is_success:
            raise APIError(response.status_code, response.text)
        result = response.json()
        if "errors" in result:
            raise APIError(400, f"GraphQL errors: {result['errors']}")
        return result

    def _motion_url(
        self,
        character_id: str,
        motion_id: str,
        output_format: OutputFormat,
        fps: int | None,
        no_mesh: bool | None,
    ) -> str:
        ext = output_format.lower()
        url = f"{self.base_url}/motion/file/motion_viewer/{character_id}/{motion_id}/{ext}/{character_id}-{motion_id}.{ext}"
        options = []
        if fps is not None:
            options.append(f"fps={fps}")
        if no_mesh is not None:
            options.append(f"no_mesh={'true' if no_mesh else 'false'}")
        if options:
            url += f"?{'&'.join(options)}"
        return url

    @staticmethod
    def _prepare_create_character(
        file_path: str, auto_rig: bool | None, front_facing: bool | None
    ) -> tuple[dict, str, str, str]:
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
        }
        return variables, name, ext, filename

    def _build_character_output(self, result: dict, ext: str) -> CharacterOutput:
        character = result["data"]["create_character"]["character"]
        character_id = character["id"]
        auto_rig_confidence = result["data"]["create_character"].get("auto_rig_confidence")

        url = f"{self.base_url}/motion/bundle/{character_id}/character.{ext}"
        return CharacterOutput(
            url=url,
            character_id=character_id,
            auto_rig_confidence=auto_rig_confidence,
        )

    @staticmethod
    def _prepare_text_to_motion_vqvae_v1(
        prompt: str, character_id: str | None, foot_ik: bool | None
    ) -> dict:
        return {
            "prompt": prompt,
            "character_id": character_id,
            "model": "text-to-motion",
            "foot_ik": foot_ik,
        }

    @staticmethod
    def _prepare_text_to_motion_diffusion_v2(
        prompt: str,
        character_id: str | None,
        foot_ik: bool | None,
        cfg_scale: float | None,
        length: float | None,
        seed: int | None,
        internal_ik: bool | None,
    ) -> dict:
        return {
            "prompt": prompt,
            "character_id": character_id,
            "model": "text-to-motion-bucmd",
            "foot_ik": foot_ik,
            "cfg_scale": cfg_scale,
            "length": length,
            "seed": seed,
            "retargeting_ik": internal_ik,
        }

    def _prepare_and_select_text_to_motion(
        self,
        model: ModelType,
        prompt: str,
        character_id: str | None,
        foot_ik: bool | None,
        length: float | None,
        cfg_scale: float | None,
        seed: int | None,
        internal_ik: bool | None,
    ) -> tuple[str, dict]:
        if model == "auto":
            model = get_default_ttm_model()
        if model == "vqvae-v1":
            variables = self._prepare_text_to_motion_vqvae_v1(prompt, character_id, foot_ik)
            return _TEXT_TO_MOTION_VQVAE_V1_MUTATION, variables
        elif model == "diffusion-v2":
            variables = self._prepare_text_to_motion_diffusion_v2(
                prompt, character_id, foot_ik, cfg_scale, length, seed, internal_ik
            )
            return _TEXT_TO_MOTION_DIFFUSION_V2_MUTATION, variables
        else:
            raise ValueError(
                f"Unknown model: {model!r}. Must be 'auto', 'vqvae-v1', or 'diffusion-v2'."
            )

    @staticmethod
    def _prepare_video_to_motion(file_path: str, motion_name: str | None) -> tuple[dict, str]:
        filename = os.path.basename(file_path)
        ext = os.path.splitext(filename)[1].lower()
        if ext not in _SUPPORTED_VIDEO_FORMATS:
            raise Error(
                f"Unsupported video format '{ext}'. Supported: {', '.join(sorted(_SUPPORTED_VIDEO_FORMATS))}"
            )
        if motion_name is None:
            motion_name = os.path.splitext(filename)[0]
        variables = {"motion_name": motion_name, "file": None}
        return variables, filename


# Backwards compatibility alias
Client = Uthana
