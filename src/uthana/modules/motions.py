# (c) Copyright 2026 Uthana, Inc. All Rights Reserved

"""Motion management: list, download, delete, rename, favorite, bake, locomotion."""

from __future__ import annotations

import asyncio
import math
from typing import List, Literal
from urllib.parse import quote

import httpx

from ..graphql import q
from ..stitch import StitchParams, validate_stitch_params
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
    """Motion management: list, download, delete, rename, favorite, bake, locomotion."""

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

    async def get(self, motion_id: str) -> Motion:
        """Get a motion and its asset metadata, including native bundle information."""
        return await self._client._graphql(
            q.GET_MOTION,
            {"motion_id": motion_id},
            path="motion",
            path_default={},
            return_type=Motion,
        )

    def get_sync(self, motion_id: str) -> Motion:
        """Get a motion and its asset metadata (sync)."""
        return asyncio.run(self.get(motion_id))

    async def catalog(self) -> dict:
        """List motion-viewer motions with tags and their owning organization IDs.

        Includes the authenticated organization ID to distinguish its motions from
        library motions. The simpler :meth:`list` interface remains unchanged.
        """
        return await self._client._graphql(q.MOTION_CATALOG)

    def catalog_sync(self) -> dict:
        """Get the motion-viewer catalog and authenticated organization ID (sync)."""
        return asyncio.run(self.catalog())

    async def trim(self, motion_id: str, start: float, end: float, name: str) -> Motion:
        """Create a trimmed motion from normalized start/end fractions without looping.

        Fractions address the source duration, with ``0 <= start < end <= 1``.
        Convert time values to fractions using the source motion's native duration.
        """
        if (
            isinstance(start, bool)
            or isinstance(end, bool)
            or not isinstance(start, (int, float))
            or not isinstance(end, (int, float))
            or not math.isfinite(start)
            or not math.isfinite(end)
            or not 0 <= start < end <= 1
        ):
            raise ValueError("Trim fractions must be finite and satisfy 0 <= start < end <= 1")
        return await self._client._graphql(
            q.TRIM_MOTION,
            {"motion_id": motion_id, "start": start, "end": end, "name": name},
            path="trim_and_loop_motion.motion",
            return_type=Motion,
        )

    def trim_sync(self, motion_id: str, start: float, end: float, name: str) -> Motion:
        """Create a trimmed motion without enabling looping (sync)."""
        return asyncio.run(self.trim(motion_id, start, end, name))

    async def create_stitched_motion(
        self,
        character_id: str,
        prefix: StitchParams,
        suffix: StitchParams,
        *,
        timeout: float | httpx.Timeout | None = None,
    ) -> Motion:
        """Join two sampled clips through the enhanced stitch preview API.

        The caller supplies world-space root/pelvis samples on the same character
        at zero, lower trim, and upper trim. Positions use meters in Y-up space,
        rotations use x/y/z/w quaternions, and yaw uses radians. No placeholder
        poses, sampling, spatial alignment, or retries are supplied by the client.
        This synchronous API operation creates a new motion and may be charged.
        """
        if not isinstance(character_id, str) or not character_id.strip():
            raise ValueError("character_id is required")
        return await self._client._graphql(
            q.CREATE_ENHANCED_STITCHED_MOTION,
            {
                "stitch_input": {
                    "character_id": character_id,
                    "prefix": validate_stitch_params(prefix),
                    "suffix": validate_stitch_params(suffix),
                }
            },
            path="create_enhanced_stitched_motion.motion",
            return_type=Motion,
            timeout=timeout,
        )

    def create_stitched_motion_sync(
        self,
        character_id: str,
        prefix: StitchParams,
        suffix: StitchParams,
        *,
        timeout: float | httpx.Timeout | None = None,
    ) -> Motion:
        """Join two sampled motion clips through the preview API (sync)."""
        return asyncio.run(
            self.create_stitched_motion(character_id, prefix, suffix, timeout=timeout)
        )

    async def create_looped_motion(
        self,
        character_id: str,
        motion_id: str,
        *,
        trim_start_pct: float = 0.0,
        trim_end_pct: float = 1.0,
        zone_duration: float = 2.0,
        loop_mode: Literal["closed", "open"] = "closed",
        zone_mode: Literal["modify", "extend"] = "modify",
        zone_end_position: dict[str, float] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> Motion:
        """Create a new looped motion through the simplified preview API.

        Trims are normalized fractions. Closed loops return to their start;
        open loops continue traveling. Modify replaces an existing interval,
        while extend adds a transition. The optional open-loop target uses the
        API's planar x/y coordinates and facing_angle in radians. Without a
        target, the API estimates continued travel. This synchronous operation
        can be charged and is never retried by the client.
        """

        def finite(value):
            return (
                not isinstance(value, bool)
                and isinstance(value, (int, float))
                and math.isfinite(value)
            )

        if not all(isinstance(v, str) and v.strip() for v in (character_id, motion_id)):
            raise ValueError("character_id and motion_id are required")
        if not all(finite(v) for v in (trim_start_pct, trim_end_pct, zone_duration)):
            raise ValueError("Trim fractions and zone_duration must be finite numbers")
        if not 0 <= trim_start_pct < trim_end_pct <= 1 or zone_duration <= 0:
            raise ValueError(
                "Require 0 <= trim_start_pct < trim_end_pct <= 1 and zone_duration > 0"
            )
        if loop_mode not in {"closed", "open"} or zone_mode not in {"modify", "extend"}:
            raise ValueError("Invalid loop_mode or zone_mode")
        if zone_end_position is not None:
            if (
                loop_mode != "open"
                or not isinstance(zone_end_position, dict)
                or not {"x", "y"} <= zone_end_position.keys() <= {"x", "y", "facing_angle"}
                or not all(finite(v) for v in zone_end_position.values())
            ):
                raise ValueError(
                    "An open-loop target requires finite x/y and optional facing_angle"
                )
        return await self._client._graphql(
            q.CREATE_LOOPED_MOTION,
            {
                "character_id": character_id,
                "motion_id": motion_id,
                "trim_start_pct": trim_start_pct,
                "trim_end_pct": trim_end_pct,
                "zone_duration": zone_duration,
                "loop_mode": loop_mode,
                "zone_mode": zone_mode,
                "zone_end_position": zone_end_position,
            },
            path="create_looped_motion.motion",
            return_type=Motion,
            timeout=timeout,
        )

    def create_looped_motion_sync(
        self,
        character_id: str,
        motion_id: str,
        *,
        trim_start_pct: float = 0.0,
        trim_end_pct: float = 1.0,
        zone_duration: float = 2.0,
        loop_mode: Literal["closed", "open"] = "closed",
        zone_mode: Literal["modify", "extend"] = "modify",
        zone_end_position: dict[str, float] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> Motion:
        """Create a loop through the simplified preview API (sync)."""
        return asyncio.run(
            self.create_looped_motion(
                character_id,
                motion_id,
                trim_start_pct=trim_start_pct,
                trim_end_pct=trim_end_pct,
                zone_duration=zone_duration,
                loop_mode=loop_mode,
                zone_mode=zone_mode,
                zone_end_position=zone_end_position,
                timeout=timeout,
            )
        )

    async def download_allowed(self, motion_id: str, character_id: str) -> dict:
        """Check download eligibility for a motion/character pair without downloading."""
        return await self._client._graphql(
            q.DOWNLOAD_ALLOWED,
            {"motion_id": motion_id, "character_id": character_id},
            path="motion_download_allowed",
        )

    def download_allowed_sync(self, motion_id: str, character_id: str) -> dict:
        """Check download eligibility for a motion/character pair (sync)."""
        return asyncio.run(self.download_allowed(motion_id, character_id))

    async def download(
        self,
        character_id: str,
        motion_id: str,
        *,
        output_format: OutputFormat = DEFAULT_OUTPUT_FORMAT,
        fps: int | None = None,
        no_mesh: bool | None = None,
        in_place: bool | None = None,
        roblox_compatible: bool | None = None,
        speed_multiplier: float | None = None,
        torso_only: bool | None = None,
        max_bytes: int | None = None,
    ) -> bytes:
        """Download a GLB, FBX, or BVH animation retargeted to the given character.

        Optional export parameters retain backend defaults when omitted. ``no_mesh``
        controls mesh inclusion; skeleton and animation remain in supported formats.
        ``max_bytes`` bounds the downloaded response when supplied.
        """
        url = self._client._motion_url(
            character_id=character_id,
            motion_id=motion_id,
            output_format=output_format,
            fps=fps,
            no_mesh=no_mesh,
            in_place=in_place,
            roblox_compatible=roblox_compatible,
            speed_multiplier=speed_multiplier,
            torso_only=torso_only,
        )
        return await self._client._request_bytes("GET", url, max_bytes=max_bytes)

    def download_sync(
        self,
        character_id: str,
        motion_id: str,
        *,
        output_format: OutputFormat = DEFAULT_OUTPUT_FORMAT,
        fps: int | None = None,
        no_mesh: bool | None = None,
        in_place: bool | None = None,
        roblox_compatible: bool | None = None,
        speed_multiplier: float | None = None,
        torso_only: bool | None = None,
        max_bytes: int | None = None,
    ) -> bytes:
        """Download a motion animation retargeted to the given character (sync)."""
        return asyncio.run(
            self.download(
                character_id,
                motion_id,
                output_format=output_format,
                fps=fps,
                no_mesh=no_mesh,
                in_place=in_place,
                roblox_compatible=roblox_compatible,
                speed_multiplier=speed_multiplier,
                torso_only=torso_only,
                max_bytes=max_bytes,
            )
        )

    async def preview(
        self,
        character_id: str,
        motion_id: str,
        *,
        format: Literal["webm", "apng"] = "webm",
        max_bytes: int | None = None,
        timeout: float | httpx.Timeout = 60.0,
    ) -> bytes:
        """Download a WebM or APNG preview without charging download seconds.

        WebM and a 60-second request timeout remain the defaults. APNG uses the
        existing ``preview.png`` endpoint. Export effects do not apply to previews.
        """
        if format not in ("webm", "apng"):
            raise ValueError("Preview format must be webm or apng")
        suffix = "png" if format == "apng" else "webm"
        character = quote(character_id, safe="")
        motion = quote(motion_id, safe="")
        url = f"{self._client.base_url}/app/preview/{character}/{motion}/preview.{suffix}"
        return await self._client._request_bytes("GET", url, max_bytes=max_bytes, timeout=timeout)

    def preview_sync(
        self,
        character_id: str,
        motion_id: str,
        *,
        format: Literal["webm", "apng"] = "webm",
        max_bytes: int | None = None,
        timeout: float | httpx.Timeout = 60.0,
    ) -> bytes:
        """Download a WebM or APNG motion preview (sync)."""
        return asyncio.run(
            self.preview(
                character_id, motion_id, format=format, max_bytes=max_bytes, timeout=timeout
            )
        )

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
        source_motion_id: str | None = None,
    ) -> TextToMotionResult:
        """Bake GLTF content as a new motion for an existing character.

        Use this to submit custom or edited GLTF animation data to the platform.
        Returns the resulting motion_id and character_id. ``source_motion_id``
        optionally associates the baked motion with its source animation.
        """
        char_id = character_id or UthanaCharacters.tar
        variables = {
            "gltf": gltf_content,
            "motionName": motion_name,
            "characterId": char_id,
        }
        if source_motion_id is not None:
            variables["sourceMotionId"] = source_motion_id
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
        source_motion_id: str | None = None,
    ) -> TextToMotionResult:
        """Bake GLTF content as a new motion for an existing character (sync)."""
        return asyncio.run(
            self.bake_with_changes(
                gltf_content,
                motion_name,
                character_id=character_id,
                source_motion_id=source_motion_id,
            )
        )

    async def create_locomotion(
        self,
        character_id: str,
        *,
        strides: int | None = None,
        move_speed: float | None = None,
        style_id: str | None = None,
        travel_angle: float | None = None,
    ) -> TextToMotionResult:
        """Generate controllable locomotion for a character.

        See `https://uthana.com/docs/api/capabilities/locomotion` for full details.

        Optional parameters use API defaults when omitted:

        - **strides**: number of full stride pairs (1–5; default 4).
        - **move_speed**: speed in m/s (0.25–8.0; default 1.2; recommended up to 6.0).
        - **style_id**: from :meth:`list_locomotion_styles` (default ``neutral_male_a``).
        - **travel_angle**: direction in degrees on the ground plane, -180 to 180
          (0 forward, 90 right; default 0.0).

        Returns ``character_id`` and ``motion_id`` like text-to-motion.
        """
        variables: dict[str, object] = {"character_id": character_id}
        if strides is not None:
            variables["strides"] = strides
        if move_speed is not None:
            variables["move_speed"] = move_speed
        if style_id is not None:
            variables["style_id"] = style_id
        if travel_angle is not None:
            variables["travel_angle"] = travel_angle

        data = await self._client._graphql(q.CREATE_LOCOMOTION, variables, path="create_locomotion")
        data = data or {}
        motion = data.get("motion") or {}
        motion_id = motion.get("id")
        if not motion_id:
            raise UthanaError(400, "create_locomotion did not return motion id")
        return TextToMotionResult(character_id=character_id, motion_id=motion_id)

    def create_locomotion_sync(
        self,
        character_id: str,
        *,
        strides: int | None = None,
        move_speed: float | None = None,
        style_id: str | None = None,
        travel_angle: float | None = None,
    ) -> TextToMotionResult:
        """Generate locomotion for a character (sync)."""
        return asyncio.run(
            self.create_locomotion(
                character_id,
                strides=strides,
                move_speed=move_speed,
                style_id=style_id,
                travel_angle=travel_angle,
            )
        )

    async def list_locomotion_styles(self) -> List[str]:
        """Return all ``style_id`` values accepted by :meth:`create_locomotion`."""
        return await self._client._graphql(
            q.LOCOMOTION_STYLES,
            path="locomotion_styles",
            path_default=[],
            return_type=List[str],
        )

    def list_locomotion_styles_sync(self) -> List[str]:
        """Return locomotion style IDs (sync)."""
        return asyncio.run(self.list_locomotion_styles())
