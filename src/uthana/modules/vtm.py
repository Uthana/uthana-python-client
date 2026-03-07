# (c) Copyright 2026 Uthana, Inc. All Rights Reserved

"""Video to motion: extract motion capture from video files."""

from __future__ import annotations

import asyncio
import json
from typing import cast

from ..graphql import q
from ..models import models
from ..types import VideoToMotionResult, VtmModelType
from ..utils import prepare_video_to_motion
from ._base import _BaseModule


class VTMModule(_BaseModule):
    """Video to motion: extract motion capture from video files."""

    async def create(
        self,
        file_path: str,
        *,
        motion_name: str | None = None,
        model: VtmModelType | None = None,
    ) -> VideoToMotionResult:
        """Extract motion capture data from a video. Returns a job to poll via jobs.get().

        Model defaults to models.ini when omitted or set to \"auto\".
        """
        variables, filename = prepare_video_to_motion(file_path, motion_name)
        if model is None:
            model = models.vtm.default
        variables["model"] = model
        operations = json.dumps({"query": q.CREATE_VIDEO_TO_MOTION, "variables": variables})
        map_data = json.dumps({"0": ["variables.file"]})

        with open(file_path, "rb") as f:
            response = await self._client.async_client.post(
                self._client.graphql_url,
                data={"operations": operations, "map": map_data},
                files={"0": (filename, f, "application/octet-stream")},
            )

        result = self._client._check_response(response)
        job = result["data"]["create_video_to_motion"]["job"]
        return cast(VideoToMotionResult, job)

    def create_sync(
        self,
        file_path: str,
        *,
        motion_name: str | None = None,
        model: VtmModelType | None = None,
    ):
        """Extract motion capture from video (sync). Returns job to poll via jobs.get_sync()."""
        return asyncio.run(self.create(file_path, motion_name=motion_name, model=model))
