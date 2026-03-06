# (c) Copyright 2026 Uthana, Inc. All Rights Reserved

"""API modules (TTM, VTM, characters, motions, org, jobs)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from .graphql import (
    CREATE_CHARACTER,
    CREATE_MOTION_FAVORITE,
    CREATE_MOTION_FROM_GLTF,
    CREATE_VIDEO_TO_MOTION,
    DELETE_MOTION_FAVORITE,
    GET_JOB,
    GET_ORG,
    GET_USER,
    LIST_CHARACTERS,
    LIST_MOTIONS,
    UPDATE_MOTION,
)
from .models import get_default_ttm_model, get_default_vtm_model
from .types import (
    DEFAULT_OUTPUT_FORMAT,
    CharacterInfo,
    CharacterOutput,
    JobOutput,
    ModelType,
    MotionInfo,
    MotionOutput,
    OrgInfo,
    OutputFormat,
    UpdateMotionResult,
    UserInfo,
    UthanaCharacters,
    UthanaError,
)
from .utils import prepare_create_character, prepare_video_to_motion

if TYPE_CHECKING:
    from .client import Uthana


class _BaseModule:
    """Base for modules that delegate to the parent Uthana instance."""

    def __init__(self, parent: Uthana) -> None:
        self._parent = parent


class TTMModule(_BaseModule):
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
            model=model,
            prompt=prompt,
            character_id=character_id,
            foot_ik=foot_ik,
            length=length,
            cfg_scale=cfg_scale,
            seed=seed,
            internal_ik=internal_ik,
        )
        data = self._parent._graphql_sync(mutation, variables)
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
            model=model,
            prompt=prompt,
            character_id=character_id,
            foot_ik=foot_ik,
            length=length,
            cfg_scale=cfg_scale,
            seed=seed,
            internal_ik=internal_ik,
        )
        data = await self._parent._graphql(mutation, variables)
        motion_id = data["create_text_to_motion"]["motion"]["id"]
        if character_id is None:
            character_id = UthanaCharacters.tar
        return MotionOutput(character_id=character_id, motion_id=motion_id)


class VTMModule(_BaseModule):
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
        variables, filename = prepare_video_to_motion(file_path, motion_name)
        if model is None or model == "auto":
            model = get_default_vtm_model()
        variables["model"] = model
        operations = json.dumps({"query": CREATE_VIDEO_TO_MOTION, "variables": variables})
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
        variables, filename = prepare_video_to_motion(file_path, motion_name)
        if model is None or model == "auto":
            model = get_default_vtm_model()
        variables["model"] = model
        operations = json.dumps({"query": CREATE_VIDEO_TO_MOTION, "variables": variables})
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


class CharactersModule(_BaseModule):
    """Character management: upload, list, download, and create motions from GLTF."""

    def create_sync(
        self,
        file_path: str,
        *,
        auto_rig: bool | None = None,
        front_facing: bool | None = None,
    ) -> CharacterOutput:
        """Upload and optionally auto-rig a 3D character model (sync)."""
        variables, name, ext, _ = prepare_create_character(file_path, auto_rig, front_facing)
        operations = json.dumps({"query": CREATE_CHARACTER, "variables": variables})
        map_data = json.dumps({"0": ["variables.file"]})

        with open(file_path, "rb") as f:
            response = self._parent.session.post(
                self._parent.graphql_url,
                data={"operations": operations, "map": map_data},
                files={"0": (f"{name}.{ext}", f, "application/octet-stream")},
            )

        result = self._parent._check_response(response)
        return self._parent._build_character_output(result=result, ext=ext)

    async def create(
        self,
        file_path: str,
        *,
        auto_rig: bool | None = None,
        front_facing: bool | None = None,
    ) -> CharacterOutput:
        """Upload and optionally auto-rig a 3D character model."""
        variables, name, ext, _ = prepare_create_character(file_path, auto_rig, front_facing)
        operations = json.dumps({"query": CREATE_CHARACTER, "variables": variables})
        map_data = json.dumps({"0": ["variables.file"]})

        with open(file_path, "rb") as f:
            response = await self._parent.async_client.post(
                self._parent.graphql_url,
                data={"operations": operations, "map": map_data},
                files={"0": (f"{name}.{ext}", f, "application/octet-stream")},
            )

        result = self._parent._check_response(response)
        return self._parent._build_character_output(result=result, ext=ext)

    def list_sync(self) -> list[CharacterInfo]:  # noqa: A001
        """List all characters for the authenticated user (sync)."""
        data = self._parent._graphql_sync(LIST_CHARACTERS)
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
        data = await self._parent._graphql(LIST_CHARACTERS)
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
            raise UthanaError(response.status_code, response.text)
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
            raise UthanaError(response.status_code, response.text)
        return response.content

    def download_preview_sync(self, character_id: str, motion_id: str) -> bytes:
        """Download motion preview WebM (does not charge download seconds) (sync)."""
        url = f"{self._parent.base_url}/app/preview/{character_id}/{motion_id}/preview.webm"
        response = self._parent.session.get(url, timeout=60.0)
        if not response.is_success:
            raise UthanaError(response.status_code, response.text)
        return response.content

    async def download_preview(self, character_id: str, motion_id: str) -> bytes:
        """Download motion preview WebM (does not charge download seconds)."""
        url = f"{self._parent.base_url}/app/preview/{character_id}/{motion_id}/preview.webm"
        response = await self._parent.async_client.get(url, timeout=60.0)
        if not response.is_success:
            raise UthanaError(response.status_code, response.text)
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
        data = self._parent._graphql_sync(CREATE_MOTION_FROM_GLTF, variables)
        gltf_data = data.get("create_motion_from_gltf", {})
        motion = gltf_data.get("motion") or {}
        motion_id = motion.get("id")
        if not motion_id:
            raise UthanaError(400, "create_motion_from_gltf did not return motion id")
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
        data = await self._parent._graphql(CREATE_MOTION_FROM_GLTF, variables)
        gltf_data = data.get("create_motion_from_gltf", {})
        motion = gltf_data.get("motion") or {}
        motion_id = motion.get("id")
        if not motion_id:
            raise UthanaError(400, "create_motion_from_gltf did not return motion id")
        return MotionOutput(character_id=char_id, motion_id=motion_id)


class MotionsModule(_BaseModule):
    """Motion management: list, download, delete, rename, favorite."""

    def list_sync(self) -> list[MotionInfo]:  # noqa: A001
        """List all motions for the authenticated user (sync)."""
        data = self._parent._graphql_sync(LIST_MOTIONS)
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
        data = await self._parent._graphql(LIST_MOTIONS)
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
        url = self._parent._motion_url(
            character_id=character_id,
            motion_id=motion_id,
            output_format=output_format,
            fps=fps,
            no_mesh=no_mesh,
        )
        response = self._parent.session.get(url)
        if not response.is_success:
            raise UthanaError(response.status_code, response.text)
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
        url = self._parent._motion_url(
            character_id=character_id,
            motion_id=motion_id,
            output_format=output_format,
            fps=fps,
            no_mesh=no_mesh,
        )
        response = await self._parent.async_client.get(url)
        if not response.is_success:
            raise UthanaError(response.status_code, response.text)
        return response.content

    def delete_sync(self, motion_id: str) -> UpdateMotionResult:
        """Soft-delete a motion by ID (sync)."""
        data = self._parent._graphql_sync(
            UPDATE_MOTION, {"id": motion_id, "deleted": True}
        )
        return data.get("update_motion", {})

    async def delete(self, motion_id: str) -> UpdateMotionResult:
        """Soft-delete a motion by ID."""
        data = await self._parent._graphql(
            UPDATE_MOTION, {"id": motion_id, "deleted": True}
        )
        return data.get("update_motion", {})

    def rename_sync(self, motion_id: str, new_name: str) -> UpdateMotionResult:
        """Rename a motion by ID (sync)."""
        data = self._parent._graphql_sync(
            UPDATE_MOTION, {"id": motion_id, "name": new_name}
        )
        return data.get("update_motion", {})

    async def rename(self, motion_id: str, new_name: str) -> UpdateMotionResult:
        """Rename a motion by ID."""
        data = await self._parent._graphql(
            UPDATE_MOTION, {"id": motion_id, "name": new_name}
        )
        return data.get("update_motion", {})

    def favorite_sync(self, motion_id: str, favorite: bool) -> None:
        """Set or unset a motion as favorite (sync)."""
        if favorite:
            self._parent._graphql_sync(
                CREATE_MOTION_FAVORITE, {"motion_id": motion_id}
            )
        else:
            self._parent._graphql_sync(
                DELETE_MOTION_FAVORITE, {"motion_id": motion_id}
            )

    async def favorite(self, motion_id: str, favorite: bool) -> None:
        """Set or unset a motion as favorite."""
        if favorite:
            await self._parent._graphql(
                CREATE_MOTION_FAVORITE, {"motion_id": motion_id}
            )
        else:
            await self._parent._graphql(
                DELETE_MOTION_FAVORITE, {"motion_id": motion_id}
            )


class OrgModule(_BaseModule):
    """Organization and user info."""

    def get_user_sync(self) -> UserInfo:
        """Get current user information (sync)."""
        data = self._parent._graphql_sync(GET_USER)
        u = data.get("user") or {}
        return UserInfo(
            id=u.get("id", ""),
            name=u.get("name"),
            email=u.get("email"),
            email_verified=u.get("email_verified"),
        )

    async def get_user(self) -> UserInfo:
        """Get current user information."""
        data = await self._parent._graphql(GET_USER)
        u = data.get("user") or {}
        return UserInfo(
            id=u.get("id", ""),
            name=u.get("name"),
            email=u.get("email"),
            email_verified=u.get("email_verified"),
        )

    def get_org_sync(self) -> OrgInfo:
        """Get current organization information including quota (sync)."""
        data = self._parent._graphql_sync(GET_ORG)
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
        data = await self._parent._graphql(GET_ORG)
        o = data.get("org") or {}
        return OrgInfo(
            id=o.get("id", ""),
            name=o.get("name"),
            motion_download_secs_per_month=o.get("motion_download_secs_per_month"),
            motion_download_secs_per_month_remaining=o.get(
                "motion_download_secs_per_month_remaining"
            ),
        )


class JobsModule(_BaseModule):
    """Async job polling for video to motion and other long-running operations."""

    def get_sync(self, job_id: str) -> JobOutput:
        """Get the status and result of an async job (sync)."""
        data = self._parent._graphql_sync(GET_JOB, {"job_id": job_id})
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
        data = await self._parent._graphql(GET_JOB, {"job_id": job_id})
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
