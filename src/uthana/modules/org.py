# (c) Copyright 2026 Uthana, Inc. All Rights Reserved

"""Organization and user info."""

from __future__ import annotations

import asyncio

from ..graphql import q
from ..types import Org, User
from ._base import _BaseModule


class OrgModule(_BaseModule):
    """Organization and user info."""

    async def get_user(self) -> User:
        """Get current user information."""
        return await self._client._graphql(
            q.GET_USER, path="user", path_default={}, return_type=User
        )

    def get_user_sync(self) -> User:
        """Get current user information (sync)."""
        return asyncio.run(self.get_user())

    async def get_org(self) -> Org:
        """Get current organization information including quota."""
        return await self._client._graphql(q.GET_ORG, path="org", path_default={}, return_type=Org)

    def get_org_sync(self) -> Org:
        """Get current organization information including quota (sync)."""
        return asyncio.run(self.get_org())
