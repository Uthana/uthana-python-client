# (c) Copyright 2026 Uthana, Inc. All Rights Reserved

"""Load model configuration from models.ini. Singleton loaded once at import."""

from __future__ import annotations

import configparser
from importlib.resources import files


class _Capability:
    """Typed capability: default model + list of available models."""

    def __init__(self, default: str, models: tuple[str, ...]) -> None:
        self.default = default
        self.models = models


class _Models:
    """Typed access to models.ini: models.ttm.default, models.vtm.default."""

    ttm: _Capability
    vtm: _Capability

    def __init__(self) -> None:
        ttm_default = "vqvae-v1"
        vtm_default = "video-to-motion-v1"
        ttm_models = ("vqvae-v1", "diffusion-v2", "flow-matching-v1", "nearest-neighbor-v1")
        vtm_models = ("video-to-motion-v1", "video-to-motion-v2")

        try:
            config = configparser.ConfigParser()
            path = files("uthana") / "models.ini"
            with path.open() as f:
                config.read_file(f)
            if config.has_section("ttm"):
                ttm_default = config.get("ttm", "default", fallback=ttm_default)
                if config.has_option("ttm", "models"):
                    ttm_models = tuple(m.strip() for m in config.get("ttm", "models").split(","))
            if config.has_section("vtm"):
                vtm_default = config.get("vtm", "default", fallback=vtm_default)
                if config.has_option("vtm", "models"):
                    vtm_models = tuple(m.strip() for m in config.get("vtm", "models").split(","))
        except Exception:
            pass

        self.ttm = _Capability(ttm_default, ttm_models)
        self.vtm = _Capability(vtm_default, vtm_models)


models = _Models()
