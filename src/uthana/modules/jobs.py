# (c) Copyright 2026 Uthana, Inc. All Rights Reserved

"""Async job polling for video to motion and other long-running operations."""

from __future__ import annotations

import asyncio
from typing import List, cast

from ..graphql import q
from ..types import Job
from ._base import _BaseModule


def _normalize_job(job: dict) -> None:
    """Rename API timestamp fields to their public names."""
    if "created_at" in job:
        job["created"] = job.pop("created_at")
    if "started_at" in job:
        job["started"] = job.pop("started_at")
    if "ended_at" in job:
        job["ended"] = job.pop("ended_at")


class JobsModule(_BaseModule):
    """Async job polling for video to motion and other long-running operations."""

    async def list(self, method: str | None = None) -> list[Job]:
        """List jobs, optionally filtered by method (e.g. 'VideoToMotion')."""
        variables = {} if method is None else {"method": method}
        jobs: list[Job] = await self._client._graphql(
            q.LIST_JOBS,
            variables,
            path="jobs",
            path_default=[],
            return_type=list[Job],
        )
        for job in jobs:
            _normalize_job(cast(dict, job))
        return jobs

    def list_sync(self, method: str | None = None) -> List[Job]:
        """List jobs, optionally filtered by method (sync)."""
        return asyncio.run(self.list(method=method))

    async def get(self, job_id: str) -> Job:
        """Get the status and result of an async job."""
        job: Job = await self._client._graphql(
            q.GET_JOB,
            {"job_id": job_id},
            path="job",
            path_default={},
            return_type=Job,
        )
        _normalize_job(cast(dict, job))
        return job

    def get_sync(self, job_id: str) -> Job:
        """Get the status and result of an async job (sync)."""
        return asyncio.run(self.get(job_id))
