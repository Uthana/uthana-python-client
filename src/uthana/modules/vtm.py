# (c) Copyright 2026 Uthana, Inc. All Rights Reserved

"""Video to motion: extract motion capture from video files."""

from __future__ import annotations

import asyncio
import os

from ..graphql import q
from ..models import models
from ..types import VideoToMotionResult, VtmModelType
from ..utils import _validate_upload_limit, normalize_model_name, prepare_video_to_motion
from ._base import _BaseModule

VIDEO_UPLOAD_MAX_BYTES = 200 * 1024 * 1024


class VtmModule(_BaseModule):
    """Video to motion: extract motion capture from video files."""

    async def create(
        self,
        file_path: str,
        *,
        motion_name: str | None = None,
        model: VtmModelType | None = None,
        max_bytes: int | None = None,
    ) -> VideoToMotionResult:
        """Extract motion capture data from a video; poll the returned job with jobs.get().

        Model defaults to models.toml when omitted. Reads a bounded snapshot up to
        200 MiB before submission; ``max_bytes`` can set a lower limit.
        The API limits organizations without an active payment method or agreement to 50 MiB.
        """
        _validate_upload_limit(max_bytes)
        variables, filename = prepare_video_to_motion(file_path, motion_name)
        variables["model"] = normalize_model_name(
            model if model is not None else models.vtm.default
        )
        with open(file_path, "rb") as source:
            if os.fstat(source.fileno()).st_size > VIDEO_UPLOAD_MAX_BYTES:
                raise ValueError("Video upload exceeds 200 MiB. Upload a smaller video.")
            limit = (
                VIDEO_UPLOAD_MAX_BYTES
                if max_bytes is None
                else min(max_bytes, VIDEO_UPLOAD_MAX_BYTES)
            )
            content = source.read(limit + 1)
        return await self.create_from_bytes(
            filename,
            content,
            motion_name=variables["motion_name"],
            model=model,
            max_bytes=max_bytes,
        )

    def create_sync(
        self,
        file_path: str,
        *,
        motion_name: str | None = None,
        model: VtmModelType | None = None,
        max_bytes: int | None = None,
    ) -> VideoToMotionResult:
        """Extract motion capture from video (sync). Returns job to poll via jobs.get_sync()."""
        return asyncio.run(
            self.create(file_path, motion_name=motion_name, model=model, max_bytes=max_bytes)
        )

    async def create_from_bytes(
        self,
        filename: str,
        content: bytes,
        *,
        motion_name: str | None = None,
        model: VtmModelType | None = None,
        max_bytes: int | None = VIDEO_UPLOAD_MAX_BYTES,
    ) -> VideoToMotionResult:
        """Submit a video byte snapshot without reopening a local file.

        ``filename`` determines supported video format and default motion name.
        An explicitly supplied motion name is preserved exactly. Videos cannot exceed
        200 MiB, even with ``max_bytes=None``. The API applies a 50 MiB limit to
        organizations without an active payment method or agreement.
        """
        _validate_upload_limit(max_bytes)
        if not isinstance(content, bytes) or not content:
            raise ValueError("Video upload content must be nonempty bytes")
        if len(content) > VIDEO_UPLOAD_MAX_BYTES:
            raise ValueError("Video upload exceeds 200 MiB. Upload a smaller video.")
        if max_bytes is not None and len(content) > max_bytes:
            raise ValueError("Video upload exceeds max_bytes")
        variables, filename = prepare_video_to_motion(filename, motion_name)
        variables["model"] = normalize_model_name(
            model if model is not None else models.vtm.default
        )
        return await self._client._graphql(
            q.CREATE_VIDEO_TO_MOTION,
            variables,
            upload=(filename, content),
            path="create_video_to_motion.job",
            return_type=VideoToMotionResult,
        )

    def create_from_bytes_sync(
        self,
        filename: str,
        content: bytes,
        *,
        motion_name: str | None = None,
        model: VtmModelType | None = None,
        max_bytes: int | None = VIDEO_UPLOAD_MAX_BYTES,
    ) -> VideoToMotionResult:
        """Submit a video byte snapshot (sync)."""
        return asyncio.run(
            self.create_from_bytes(
                filename,
                content,
                motion_name=motion_name,
                model=model,
                max_bytes=max_bytes,
            )
        )
