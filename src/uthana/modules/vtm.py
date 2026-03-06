# (c) Copyright 2026 Uthana, Inc. All Rights Reserved

"""Video to motion: extract motion capture from video files."""

from __future__ import annotations

import json

from ..graphql import q
from ..models import get_default_vtm_model
from ..types import JobOutput
from ..utils import prepare_video_to_motion
from ._base import _BaseModule


class VTMModule(_BaseModule):
    """Video to motion: extract motion capture from video files."""

    def create_sync(
        self,
        file_path: str,
        *,
        motion_name: str | None = None,
        model: str | None = None,
    ) -> JobOutput:
        """Extract motion capture data from a video (sync).

        Returns a job to poll via jobs.get_sync(). Model defaults to models.ini when omitted.
        """
        variables, filename = prepare_video_to_motion(file_path, motion_name)
        if model is None or model == "auto":
            model = get_default_vtm_model()
        variables["model"] = model
        operations = json.dumps({"query": q.CREATE_VIDEO_TO_MOTION, "variables": variables})
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
        operations = json.dumps({"query": q.CREATE_VIDEO_TO_MOTION, "variables": variables})
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
