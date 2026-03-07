# (c) Copyright 2026 Uthana, Inc. All Rights Reserved

"""Motion management: list, download, delete, rename, favorite."""

from __future__ import annotations

import asyncio
from typing import cast

from ..graphql import q
from ..types import (
    DEFAULT_OUTPUT_FORMAT,
    Motion,
    OutputFormat,
    UthanaError,
)
from ._base import _BaseModule


class MotionsModule(_BaseModule):
    """Motion management: list, download, delete, rename, favorite."""

    async def list(self) -> list[Motion]:
        """List all motions for the authenticated user."""
        return await self._client._graphql(
            q.LIST_MOTIONS,
            path="motions",
            path_default=[],
            return_type=list[Motion],
        )

    def list_sync(self):
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
        response = await self._client.async_client.get(url)
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
    ):
        """Download a motion animation file, retargeted to the given character (sync)."""
        return asyncio.run(
            self.download(
                character_id,
                motion_id,
                output_format=output_format,
                fps=fps,
                no_mesh=no_mesh,
            )
        )

    async def download_preview(self, character_id: str, motion_id: str) -> bytes:
        """Download motion preview WebM (does not charge download seconds)."""
        url = f"{self._client.base_url}/app/preview/{character_id}/{motion_id}/preview.webm"
        response = await self._client.async_client.get(url, timeout=60.0)
        if not response.is_success:
            raise UthanaError(response.status_code, response.text)
        return cast(bytes, response.content)

    def download_preview_sync(self, character_id: str, motion_id: str) -> bytes:
        """Download motion preview WebM (does not charge download seconds) (sync)."""
        return asyncio.run(self.download_preview(character_id, motion_id))

    async def delete(self, motion_id: str):
        """Soft-delete a motion by ID."""
        return await self._client._graphql(
            q.UPDATE_MOTION,
            {"id": motion_id, "deleted": True},
            path="update_motion",
            return_type=Motion,
        )

    def delete_sync(self, motion_id: str):
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

    def rename_sync(self, motion_id: str, new_name: str):
        """Rename a motion by ID (sync)."""
        return asyncio.run(self.rename(motion_id, new_name))

    async def favorite(self, motion_id: str, favorite: bool) -> None:
        """Set or unset a motion as favorite."""
        if favorite:
            await self._client._graphql(q.CREATE_MOTION_FAVORITE, {"motion_id": motion_id})
        else:
            await self._client._graphql(q.DELETE_MOTION_FAVORITE, {"motion_id": motion_id})

    def favorite_sync(self, motion_id: str, favorite: bool):
        """Set or unset a motion as favorite (sync)."""
        return asyncio.run(self.favorite(motion_id, favorite))
