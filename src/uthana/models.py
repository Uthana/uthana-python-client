# (c) Copyright 2026 Uthana, Inc. All Rights Reserved

"""Load default model configuration from models.ini."""

from __future__ import annotations

import configparser
from importlib.resources import files

_TTM_DEFAULT = "vqvae-v1"
_VTM_DEFAULT = "video-to-motion-v1"


def _get_default(section: str, fallback: str) -> str:
    """Read default model from models.ini section, or return fallback."""
    try:
        config = configparser.ConfigParser()
        path = files("uthana") / "models.ini"
        with path.open() as f:
            config.read_file(f)
        return config.get(section, "default", fallback=fallback)
    except Exception:
        return fallback


def get_default_ttm_model() -> str:
    """Return the default text to motion model from models.ini."""
    return _get_default("ttm", _TTM_DEFAULT)


def get_default_vtm_model() -> str:
    """Return the default video to motion model from models.ini."""
    return _get_default("vtm", _VTM_DEFAULT)
