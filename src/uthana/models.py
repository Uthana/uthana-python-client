# (c) Copyright 2026 Uthana, Inc. All Rights Reserved

"""Load model configuration from models.toml. Singleton loaded once at import."""

from __future__ import annotations

import sys
from importlib.resources import files
from typing import Generic, TypeVar, cast

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[import-not-found]

from .types import TtmModelType, VtmModelType

_T = TypeVar("_T", bound=str)


class _Capability(Generic[_T]):
    """Typed capability: default model + list of available models."""

    def __init__(self, default: _T, models: tuple[str, ...]) -> None:
        self.default = default
        self.models = models


class _Models:
    """Typed access to models.toml: models.ttm.default, models.vtm.default."""

    ttm: _Capability[TtmModelType]
    vtm: _Capability[VtmModelType]

    def __init__(self) -> None:
        try:
            with (files("uthana") / "models.toml").open("rb") as f:
                config = tomllib.load(f)
        except Exception as e:
            raise Exception("Failed to load Uthana model configuration from models.toml") from e

        def _get(section: str, key: str, fallback: str) -> str:
            return str(config.get(section, {}).get(key, fallback))

        def _models(section: str, fallback: tuple[str, ...]) -> tuple[str, ...]:
            value = config.get(section, {}).get("models")
            return tuple(value) if value else fallback

        self.ttm = _Capability(
            cast(TtmModelType, _get("ttm", "default", "vqvae-v1")),
            _models("ttm", ("vqvae-v1", "diffusion-v2", "flow-matching-v1", "nearest-neighbor-v1")),
        )
        self.vtm = _Capability(
            cast(VtmModelType, _get("vtm", "default", "video-to-motion-v1")),
            _models("vtm", ("video-to-motion-v1", "video-to-motion-v2")),
        )


models = _Models()
