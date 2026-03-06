# (c) Copyright 2026 Uthana, Inc. All Rights Reserved

"""Organization and user info."""

from __future__ import annotations

from ._base import _BaseModule
from ..graphql import GET_ORG, GET_USER
from ..types import OrgInfo, UserInfo


class OrgModule(_BaseModule):
    """Organization and user info."""

    def get_user_sync(self) -> UserInfo:
        """Get current user information (sync)."""
        data = self._parent._graphql_sync(GET_USER)
        u = data.get("user") or {}
        return UserInfo(
            id=u.get("id", ""),
            name=u.get("name"),
            email=u.get("email"),
            email_verified=u.get("email_verified"),
        )

    async def get_user(self) -> UserInfo:
        """Get current user information."""
        data = await self._parent._graphql(GET_USER)
        u = data.get("user") or {}
        return UserInfo(
            id=u.get("id", ""),
            name=u.get("name"),
            email=u.get("email"),
            email_verified=u.get("email_verified"),
        )

    def get_org_sync(self) -> OrgInfo:
        """Get current organization information including quota (sync)."""
        data = self._parent._graphql_sync(GET_ORG)
        o = data.get("org") or {}
        return OrgInfo(
            id=o.get("id", ""),
            name=o.get("name"),
            motion_download_secs_per_month=o.get("motion_download_secs_per_month"),
            motion_download_secs_per_month_remaining=o.get(
                "motion_download_secs_per_month_remaining"
            ),
        )

    async def get_org(self) -> OrgInfo:
        """Get current organization information including quota."""
        data = await self._parent._graphql(GET_ORG)
        o = data.get("org") or {}
        return OrgInfo(
            id=o.get("id", ""),
            name=o.get("name"),
            motion_download_secs_per_month=o.get("motion_download_secs_per_month"),
            motion_download_secs_per_month_remaining=o.get(
                "motion_download_secs_per_month_remaining"
            ),
        )
