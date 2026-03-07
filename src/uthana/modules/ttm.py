# (c) Copyright 2026 Uthana, Inc. All Rights Reserved

"""Text to motion: generate animations from natural language prompts."""

from __future__ import annotations

import asyncio

from ..models import models
from ..types import TextToMotionResult, TtmModelType, UthanaCharacters
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

        Model defaults to the value in models.ini when omitted or set to \"auto\".
        """
        if model is None:
            model = models.ttm.default
        mutation, variables = self._client._prepare_and_select_text_to_motion(
            model=model,
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
