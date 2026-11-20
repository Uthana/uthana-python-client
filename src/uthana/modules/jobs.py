# (c) Copyright 2026 Uthana, Inc. All Rights Reserved

"""Async job polling for video to motion and other long-running operations."""

from __future__ import annotations

import asyncio
import math
import time
from typing import List, cast

import httpx

from ..graphql import q
from ..types import DEFAULT_TIMEOUT, Job, UthanaError
from ._base import _BaseModule

JOB_POLL_INTERVAL_SECONDS = 5.0


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

    async def wait(
        self,
        job_id: str,
        *,
        interval_seconds: float = JOB_POLL_INTERVAL_SECONDS,
        timeout_seconds: float | None = None,
    ) -> Job:
        """Poll existing work until FINISHED or FAILED, without resubmitting it.

        Defaults to five-second polling and the client's read timeout (120 seconds
        when unbounded). A timeout leaves the upstream job running; use its same ID
        to resume polling. A finished job can still need result/quality inspection.
        """
        if timeout_seconds is None:
            configured = self._client._timeout
            timeout_seconds = (
                configured.read if isinstance(configured, httpx.Timeout) else configured
            )
            if timeout_seconds is None:
                timeout_seconds = DEFAULT_TIMEOUT
        for name, value in (
            ("interval_seconds", interval_seconds),
            ("timeout_seconds", timeout_seconds),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value <= 0
            ):
                raise ValueError(f"{name} must be a positive finite number of seconds")
        deadline = time.monotonic() + timeout_seconds
        timeout_error = UthanaError(
            408, f"Job {job_id} did not finish within {timeout_seconds:g} seconds"
        )
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise timeout_error
            try:
                job = await asyncio.wait_for(self.get(job_id), timeout=remaining)
            except asyncio.TimeoutError as exc:
                raise timeout_error from exc
            status = job.get("status")
            if status == "FINISHED":
                return job
            if status == "FAILED":
                result = job.get("result")
                message = result.get("message") if isinstance(result, dict) else None
                raise UthanaError(
                    500, message if isinstance(message, str) else f"Job {job_id} failed"
                )
            remaining = deadline - time.monotonic()
            await asyncio.sleep(max(0, min(interval_seconds, remaining)))

    def wait_sync(
        self,
        job_id: str,
        *,
        interval_seconds: float = JOB_POLL_INTERVAL_SECONDS,
        timeout_seconds: float | None = None,
    ) -> Job:
        """Poll existing work until finished or failed (sync)."""
        return asyncio.run(
            self.wait(job_id, interval_seconds=interval_seconds, timeout_seconds=timeout_seconds)
        )
