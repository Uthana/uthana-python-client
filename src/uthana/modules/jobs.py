# (c) Copyright 2026 Uthana, Inc. All Rights Reserved

"""Async job polling for video to motion and other long-running operations."""

from __future__ import annotations

import asyncio
from typing import List

from ..graphql import q
from ..types import Job
from ._base import _BaseModule


class JobsModule(_BaseModule):
    """Async job polling for video to motion and other long-running operations."""

    async def list(self, method: str | None = None) -> list[Job]:
        """List jobs, optionally filtered by method (e.g. 'VideoToMotion')."""
        variables = {} if method is None else {"method": method}
        return await self._client._graphql(
            q.LIST_JOBS,
            variables,
            path="jobs",
            path_default=[],
            return_type=list[Job],
        )

    def list_sync(self, method: str | None = None) -> List[Job]:
        """List jobs, optionally filtered by method (sync)."""
        return asyncio.run(self.list(method=method))

    async def get(self, job_id: str) -> Job:
        """Get the status and result of an async job."""
        return await self._client._graphql(
            q.GET_JOB,
            {"job_id": job_id},
            path="job",
            path_default={},
            return_type=Job,
        )

    def get_sync(self, job_id: str) -> Job:
        """Get the status and result of an async job (sync)."""
        return asyncio.run(self.get(job_id))
