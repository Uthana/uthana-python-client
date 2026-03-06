# (c) Copyright 2026 Uthana, Inc. All Rights Reserved

"""Motion management: list, download, delete, rename, favorite."""

from __future__ import annotations

from ..graphql import q
from ..types import (
    DEFAULT_OUTPUT_FORMAT,
    MotionInfo,
    OutputFormat,
    UpdateMotionResult,
    UthanaError,
)
from ._base import _BaseModule


class MotionsModule(_BaseModule):
    """Motion management: list, download, delete, rename, favorite."""

    def list_sync(self) -> list[MotionInfo]:  # noqa: A001
        """List all motions for the authenticated user (sync)."""
        data = self._parent._graphql_sync(q.LIST_MOTIONS)
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
        data = await self._parent._graphql(q.LIST_MOTIONS)
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
        data = self._parent._graphql_sync(q.UPDATE_MOTION, {"id": motion_id, "deleted": True})
        return data.get("update_motion", {})

    async def delete(self, motion_id: str) -> UpdateMotionResult:
        """Soft-delete a motion by ID."""
        data = await self._parent._graphql(q.UPDATE_MOTION, {"id": motion_id, "deleted": True})
        return data.get("update_motion", {})

    def rename_sync(self, motion_id: str, new_name: str) -> UpdateMotionResult:
        """Rename a motion by ID (sync)."""
        data = self._parent._graphql_sync(q.UPDATE_MOTION, {"id": motion_id, "name": new_name})
        return data.get("update_motion", {})

    async def rename(self, motion_id: str, new_name: str) -> UpdateMotionResult:
        """Rename a motion by ID."""
        data = await self._parent._graphql(q.UPDATE_MOTION, {"id": motion_id, "name": new_name})
        return data.get("update_motion", {})

    def favorite_sync(self, motion_id: str, favorite: bool) -> None:
        """Set or unset a motion as favorite (sync)."""
        if favorite:
            self._parent._graphql_sync(q.CREATE_MOTION_FAVORITE, {"motion_id": motion_id})
        else:
            self._parent._graphql_sync(q.DELETE_MOTION_FAVORITE, {"motion_id": motion_id})

    async def favorite(self, motion_id: str, favorite: bool) -> None:
        """Set or unset a motion as favorite."""
        if favorite:
            await self._parent._graphql(q.CREATE_MOTION_FAVORITE, {"motion_id": motion_id})
        else:
            await self._parent._graphql(q.DELETE_MOTION_FAVORITE, {"motion_id": motion_id})
