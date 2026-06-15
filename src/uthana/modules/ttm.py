# (c) Copyright 2026 Uthana, Inc. All Rights Reserved

"""Text to motion: generate animations from natural language prompts."""

from __future__ import annotations

import asyncio
from typing import cast

from ..graphql import q
from ..models import models
from ..types import Job, TextToMotionResult, TtmJobModelType, TtmModelType, UthanaCharacters
from ..utils import normalize_model_name
from ._base import _BaseModule


class TtmModule(_BaseModule):
    """Text to motion: generate animations from natural language prompts."""

    async def create(
        self,
        prompt: str,
        *,
        model: TtmModelType | None = None,
        character_id: str | None = None,
        foot_ik: bool | None = None,
        length: float | None = None,
        cfg_scale: float | None = None,
        seed: int | None = None,
        internal_ik: bool | None = None,
    ) -> TextToMotionResult:
        """Generate a 3D character animation from a natural language prompt.

        Model defaults to the value in models.toml when omitted or set to "auto".
        """
        resolved: str = normalize_model_name(model) if model is not None else models.ttm.default
        mutation, variables = self._client._prepare_and_select_text_to_motion(
            model=cast(TtmModelType, resolved),
            prompt=prompt,
            character_id=character_id,
            foot_ik=foot_ik,
            length=length,
            cfg_scale=cfg_scale,
            seed=seed,
            internal_ik=internal_ik,
        )
        data = await self._client._graphql(mutation, variables, path="create_text_to_motion")
        motion_id = data["motion"]["id"]
        if character_id is None:
            character_id = UthanaCharacters.tar
        return TextToMotionResult(character_id=character_id, motion_id=motion_id)

    def create_sync(
        self,
        prompt: str,
        *,
        model: TtmModelType | None = None,
        character_id: str | None = None,
        foot_ik: bool | None = None,
        length: float | None = None,
        cfg_scale: float | None = None,
        seed: int | None = None,
        internal_ik: bool | None = None,
    ) -> TextToMotionResult:
        """Generate a 3D character animation from a natural language prompt (sync)."""
        return asyncio.run(
            self.create(
                prompt,
                model=model,
                character_id=character_id,
                foot_ik=foot_ik,
                length=length,
                cfg_scale=cfg_scale,
                seed=seed,
                internal_ik=internal_ik,
            ),
        )

    async def create_job(
        self,
        prompt: str,
        *,
        model: TtmJobModelType,
        character_id: str | None = None,
        length: float | None = None,
        rewrite_prompt: bool | None = None,
    ) -> Job:
        """Submit an async text-to-motion job (TTM 3.0). Returns a Job to poll via jobs.get().

        Access is org-gated server-side; the server returns an error if the caller's org is not
        whitelisted.
        """
        variables = {
            "prompt": prompt,
            "model": normalize_model_name(model),
            "character_id": character_id,
            "length": length,
            "rewrite_prompt": rewrite_prompt,
        }
        data = await self._client._graphql(
            q.CREATE_TEXT_TO_MOTION_JOB, variables, path="create_text_to_motion_job.job"
        )
        return cast(Job, data)

    def create_job_sync(
        self,
        prompt: str,
        *,
        model: TtmJobModelType,
        character_id: str | None = None,
        length: float | None = None,
        rewrite_prompt: bool | None = None,
    ) -> Job:
        """Submit an async text-to-motion job (TTM 3.0), blocking. Returns a Job to poll via
        jobs.get_sync()."""
        return asyncio.run(
            self.create_job(
                prompt,
                model=model,
                character_id=character_id,
                length=length,
                rewrite_prompt=rewrite_prompt,
            )
        )
