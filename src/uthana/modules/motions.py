# (c) Copyright 2026 Uthana, Inc. All Rights Reserved

"""Motion management: list, download, delete, rename, favorite, bake."""

from __future__ import annotations

import asyncio
from typing import List, cast

import httpx

from ..graphql import q
from ..types import (
    DEFAULT_OUTPUT_FORMAT,
    Motion,
    OutputFormat,
    TextToMotionResult,
    UthanaCharacters,
    UthanaError,
)
from ._base import _BaseModule


class MotionsModule(_BaseModule):
    """Motion management: list, download, delete, rename, favorite, bake."""

    async def list(self) -> list[Motion]:
        """List all motions for the authenticated user."""
        return await self._client._graphql(
            q.LIST_MOTIONS,
            path="motions",
            path_default=[],
            return_type=list[Motion],
        )

    def list_sync(self) -> List[Motion]:
        """List all motions for the authenticated user (sync)."""
        return asyncio.run(self.list())

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
        url = self._client._motion_url(
            character_id=character_id,
            motion_id=motion_id,
            output_format=output_format,
            fps=fps,
            no_mesh=no_mesh,
        )
        async with httpx.AsyncClient(
            auth=(self._client._api_key, ""), timeout=self._client._timeout
        ) as http:
            response = await http.get(url)
        if not response.is_success:
            raise UthanaError(response.status_code, response.text)
        return cast(bytes, response.content)

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
        return asyncio.run(
            self.download(
                character_id, motion_id, output_format=output_format, fps=fps, no_mesh=no_mesh
            )
        )

    async def preview(self, character_id: str, motion_id: str) -> bytes:
        """Download motion preview WebM (does not charge download seconds)."""
        url = f"{self._client.base_url}/app/preview/{character_id}/{motion_id}/preview.webm"
        async with httpx.AsyncClient(
            auth=(self._client._api_key, ""), timeout=self._client._timeout
        ) as http:
            response = await http.get(url, timeout=60.0)
        if not response.is_success:
            raise UthanaError(response.status_code, response.text)
        return cast(bytes, response.content)

    def preview_sync(self, character_id: str, motion_id: str) -> bytes:
        """Download motion preview WebM (does not charge download seconds) (sync)."""
        return asyncio.run(self.preview(character_id, motion_id))

    async def delete(self, motion_id: str) -> Motion:
        """Soft-delete a motion by ID."""
        return await self._client._graphql(
            q.UPDATE_MOTION,
            {"id": motion_id, "deleted": True},
            path="update_motion",
            return_type=Motion,
        )

    def delete_sync(self, motion_id: str) -> Motion:
        """Soft-delete a motion by ID (sync)."""
        return asyncio.run(self.delete(motion_id))

    async def rename(self, motion_id: str, new_name: str) -> Motion:
        """Rename a motion by ID."""
        return await self._client._graphql(
            q.UPDATE_MOTION,
            {"id": motion_id, "name": new_name},
            path="update_motion",
            return_type=Motion,
        )

    def rename_sync(self, motion_id: str, new_name: str) -> Motion:
        """Rename a motion by ID (sync)."""
        return asyncio.run(self.rename(motion_id, new_name))

    async def favorite(self, motion_id: str, favorite: bool) -> None:
        """Set or unset a motion as favorite."""
        if favorite:
            await self._client._graphql(q.CREATE_MOTION_FAVORITE, {"motion_id": motion_id})
        else:
            await self._client._graphql(q.DELETE_MOTION_FAVORITE, {"motion_id": motion_id})

    def favorite_sync(self, motion_id: str, favorite: bool) -> None:
        """Set or unset a motion as favorite (sync)."""
        asyncio.run(self.favorite(motion_id, favorite))

    async def bake_with_changes(
        self,
        gltf_content: str,
        motion_name: str,
        *,
        character_id: str | None = None,
    ) -> TextToMotionResult:
        """Bake GLTF content as a new motion for an existing character.

        Use this to submit custom or edited GLTF animation data to the platform.
        Returns the resulting motion_id and character_id.
        """
        char_id = character_id or UthanaCharacters.tar
        variables = {
            "gltf": gltf_content,
            "motionName": motion_name,
            "characterId": char_id,
        }
        data = await self._client._graphql(
            q.CREATE_MOTION_FROM_GLTF, variables, path="create_motion_from_gltf"
        )
        data = data or {}
        motion = data.get("motion") or {}
        motion_id = motion.get("id")
        if not motion_id:
            raise UthanaError(400, "create_motion_from_gltf did not return motion id")
        return TextToMotionResult(character_id=char_id, motion_id=motion_id)

    def bake_with_changes_sync(
        self,
        gltf_content: str,
        motion_name: str,
        *,
        character_id: str | None = None,
    ) -> TextToMotionResult:
        """Bake GLTF content as a new motion for an existing character (sync)."""
        return asyncio.run(
            self.bake_with_changes(gltf_content, motion_name, character_id=character_id)
        )
