# (c) Copyright 2026 Uthana, Inc. All Rights Reserved

"""Base class for API modules."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..client import Uthana


class _BaseModule:
    """Base for modules that delegate to the Uthana client instance."""

    def __init__(self, client: Uthana) -> None:
        self._client = client
