# (c) Copyright 2026 Uthana, Inc. All Rights Reserved

"""Text to motion: generate animations from natural language prompts."""

from __future__ import annotations

from ._base import _BaseModule
from ..models import get_default_ttm_model
from ..types import ModelType, MotionOutput, UthanaCharacters


class TTMModule(_BaseModule):
    """Text to motion: generate animations from natural language prompts."""

    def create_sync(
        self,
        prompt: str,
        *,
        model: ModelType | None = None,
        character_id: str | None = None,
        foot_ik: bool | None = None,
        length: float | None = None,
        cfg_scale: float | None = None,
        seed: int | None = None,
        internal_ik: bool | None = None,
    ) -> MotionOutput:
        """Generate a 3D character animation from a natural language prompt.

        Model defaults to the value in models.ini when omitted or set to \"auto\".
        """
        if model is None or model == "auto":
            model = get_default_ttm_model()
        mutation, variables = self._parent._prepare_and_select_text_to_motion(
            model=model,
            prompt=prompt,
            character_id=character_id,
            foot_ik=foot_ik,
            length=length,
            cfg_scale=cfg_scale,
            seed=seed,
            internal_ik=internal_ik,
        )
        data = self._parent._graphql_sync(mutation, variables)
        motion_id = data["create_text_to_motion"]["motion"]["id"]
        if character_id is None:
            character_id = UthanaCharacters.tar
        return MotionOutput(character_id=character_id, motion_id=motion_id)

    async def create(
        self,
        prompt: str,
        *,
        model: ModelType | None = None,
        character_id: str | None = None,
        foot_ik: bool | None = None,
        length: float | None = None,
        cfg_scale: float | None = None,
        seed: int | None = None,
        internal_ik: bool | None = None,
    ) -> MotionOutput:
        """Generate a 3D character animation from a natural language prompt (async).

        Model defaults to the value in models.ini when omitted or set to \"auto\".
        """
        if model is None or model == "auto":
            model = get_default_ttm_model()
        mutation, variables = self._parent._prepare_and_select_text_to_motion(
            model=model,
            prompt=prompt,
            character_id=character_id,
            foot_ik=foot_ik,
            length=length,
            cfg_scale=cfg_scale,
            seed=seed,
            internal_ik=internal_ik,
        )
        data = await self._parent._graphql(mutation, variables)
        motion_id = data["create_text_to_motion"]["motion"]["id"]
        if character_id is None:
            character_id = UthanaCharacters.tar
        return MotionOutput(character_id=character_id, motion_id=motion_id)
