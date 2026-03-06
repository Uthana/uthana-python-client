# (c) Copyright 2026 Uthana, Inc. All Rights Reserved

"""Async job polling for video to motion and other long-running operations."""

from __future__ import annotations

import json

from ._base import _BaseModule
from ..graphql import GET_JOB
from ..types import JobOutput


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
