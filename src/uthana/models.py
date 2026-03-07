# (c) Copyright 2026 Uthana, Inc. All Rights Reserved

"""Load model configuration from models.ini. Singleton loaded once at import."""

from __future__ import annotations

import configparser
from importlib.resources import files
from typing import Generic, TypeVar, cast

from .types import TtmModelType, VtmModelType

_T = TypeVar("_T", bound=str)


class _Capability(Generic[_T]):
    """Typed capability: default model + list of available models."""

    def __init__(self, default: _T, models: tuple[str, ...]) -> None:
        self.default = default
        self.models = models


class _Models:
    """Typed access to models.ini: models.ttm.default, models.vtm.default."""

    ttm: _Capability[TtmModelType]
    vtm: _Capability[VtmModelType]

    def __init__(self) -> None:
        try:
            config = configparser.ConfigParser()
            with (files("uthana") / "models.ini").open() as f:
                config.read_file(f)
        except Exception as e:
            raise Exception("Failed to load Uthana model configuration from models.ini") from e

        def _get(section: str, key: str, fallback: str) -> str:
            if not config.has_section(section):
                return fallback
            return config.get(section, key, fallback=fallback)

        def _models(section: str, fallback: str) -> tuple[str, ...]:
            raw = _get(section, "models", fallback)
            return tuple(m.strip() for m in raw.split(","))

        self.ttm = _Capability(
            cast(TtmModelType, _get("ttm", "default", "vqvae-v1")),
            _models("ttm", "vqvae-v1, diffusion-v2, flow-matching-v1, nearest-neighbor-v1"),
        )
        self.vtm = _Capability(
            cast(VtmModelType, _get("vtm", "default", "video-to-motion-v1")),
            _models("vtm", "video-to-motion-v1, video-to-motion-v2"),
        )


models = _Models()
