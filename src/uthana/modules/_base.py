# (c) Copyright 2026 Uthana, Inc. All Rights Reserved

"""Base class for API modules."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..client import Uthana


class _BaseModule:
    """Base for modules that delegate to the parent Uthana instance."""

    def __init__(self, parent: Uthana) -> None:
        self._parent = parent
