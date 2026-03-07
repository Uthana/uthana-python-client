# (c) Copyright 2026 Uthana, Inc. All Rights Reserved

"""Character management: upload, list, download, and create motions from GLTF."""

from __future__ import annotations

import asyncio
import json
from typing import List

import httpx

from ..graphql import q
from ..types import (
    DEFAULT_OUTPUT_FORMAT,
    Character,
    CreateCharacterResult,
    OutputFormat,
    TextToMotionResult,
    UthanaCharacters,
    UthanaError,
)
from ..utils import prepare_create_character
from ._base import _BaseModule


class CharactersModule(_BaseModule):
    """Character management: upload, list, download, and create motions from GLTF."""

    async def create(
        self,
        file_path: str,
        *,
        auto_rig: bool | None = None,
        front_facing: bool | None = None,
    ) -> CreateCharacterResult:
        """Upload and optionally auto-rig a 3D character model."""
        variables, name, ext, _ = prepare_create_character(file_path, auto_rig, front_facing)
        operations = json.dumps({"query": q.CREATE_CHARACTER, "variables": variables})
        map_data = json.dumps({"0": ["variables.file"]})

        with open(file_path, "rb") as f:
            async with httpx.AsyncClient(
                auth=(self._client._api_key, ""), timeout=self._client._timeout
            ) as http:
                response = await http.post(
                    self._client.graphql_url,
                    data={"operations": operations, "map": map_data},
                    files={"0": (f"{name}.{ext}", f, "application/octet-stream")},
                )

        result = self._client._check_response(response)
        return self._client._build_character_output(result=result, ext=ext)

    def create_sync(
        self,
        file_path: str,
        *,
        auto_rig: bool | None = None,
        front_facing: bool | None = None,
    ) -> CreateCharacterResult:
        """Upload and optionally auto-rig a 3D character model (sync)."""
        return asyncio.run(self.create(file_path, auto_rig=auto_rig, front_facing=front_facing))

    async def list(self) -> list[Character]:
        """List all characters for the authenticated user."""
        return await self._client._graphql(
            q.LIST_CHARACTERS,
            path="characters",
            path_default=[],
            return_type=list[Character],
        )

    def list_sync(self) -> List[Character]:
        """List all characters for the authenticated user (sync)."""
        return asyncio.run(self.list())

    async def download(
        self,
        character_id: str,
        *,
        output_format: OutputFormat = DEFAULT_OUTPUT_FORMAT,
    ) -> bytes:
        """Download a character model in the requested format."""
        ext = output_format.lower()
        url = f"{self._client.base_url}/motion/bundle/{character_id}/character.{ext}"
        async with httpx.AsyncClient(
            auth=(self._client._api_key, ""), timeout=self._client._timeout
        ) as http:
            response = await http.get(url)
        if not response.is_success:
            raise UthanaError(response.status_code, response.text)
        return response.content

    def download_sync(
        self,
        character_id: str,
        *,
        output_format: OutputFormat = DEFAULT_OUTPUT_FORMAT,
    ) -> bytes:
        """Download a character model in the requested format (sync)."""
        return asyncio.run(self.download(character_id, output_format=output_format))

    async def create_from_gltf(
        self,
        gltf_content: str,
        motion_name: str,
        *,
        character_id: str | None = None,
    ) -> TextToMotionResult:
        """Upload GLTF content as a new motion. Returns motion_id and character_id."""
        char_id = character_id or UthanaCharacters.tar
        variables = {
            "gltf": gltf_content,
            "motionName": motion_name,
            "characterId": char_id,
        }
        gltf_data = await self._client._graphql(
            q.CREATE_MOTION_FROM_GLTF, variables, path="create_motion_from_gltf"
        )
        gltf_data = gltf_data or {}
        motion = gltf_data.get("motion") or {}
        motion_id = motion.get("id")
        if not motion_id:
            raise UthanaError(400, "create_motion_from_gltf did not return motion id")
        return TextToMotionResult(character_id=char_id, motion_id=motion_id)

    def create_from_gltf_sync(
        self,
        gltf_content: str,
        motion_name: str,
        *,
        character_id: str | None = None,
    ) -> TextToMotionResult:
        """Upload GLTF content as a new motion (sync). Returns motion_id and character_id."""
        return asyncio.run(
            self.create_from_gltf(gltf_content, motion_name, character_id=character_id)
        )
