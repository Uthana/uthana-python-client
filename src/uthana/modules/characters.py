# (c) Copyright 2026 Uthana, Inc. All Rights Reserved

"""Character management: upload, list, download, and create motions from GLTF."""

from __future__ import annotations

import json

from ._base import _BaseModule
from ..graphql import CREATE_CHARACTER, CREATE_MOTION_FROM_GLTF, LIST_CHARACTERS
from ..types import (
    CharacterInfo,
    CharacterOutput,
    DEFAULT_OUTPUT_FORMAT,
    MotionOutput,
    OutputFormat,
    UthanaCharacters,
    UthanaError,
)
from ..utils import prepare_create_character


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
        variables, name, ext, _ = prepare_create_character(
            file_path, auto_rig, front_facing
        )
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
        variables, name, ext, _ = prepare_create_character(
            file_path, auto_rig, front_facing
        )
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
