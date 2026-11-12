# (c) Copyright 2026 Uthana, Inc. All Rights Reserved

"""Organization and user info."""

from __future__ import annotations

import asyncio
import datetime
from collections.abc import Sequence

from ..graphql import q
from ..types import LedgerEntry, Org, User
from ._base import _BaseModule

LEDGER_MAX_LIMIT = 500
"""Largest page the backend returns for one ledger request."""


def _ledger_time(name: str, value: datetime.datetime | str) -> str:
    """Return an ISO 8601 timestamp; naive datetimes are treated as UTC."""
    if isinstance(value, str):
        try:
            datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(
                f"{name} must be an ISO 8601 timestamp such as 2026-11-01T00:00:00Z, got {value!r}."
            ) from exc
        return value
    if not isinstance(value, datetime.datetime):
        raise ValueError(f"{name} must be a datetime or ISO 8601 string.")
    if value.tzinfo is None:
        value = value.replace(tzinfo=datetime.timezone.utc)
    return value.isoformat()


def _ledger_query(
    *,
    limit: int,
    before_id: str | None,
    since: datetime.datetime | str | None,
    until: datetime.datetime | str | None,
    types: Sequence[str] | None,
) -> tuple[str, dict]:
    """Build the ledger query, sending only the filters the caller set."""
    is_valid_limit = (
        isinstance(limit, int) and not isinstance(limit, bool) and 1 <= limit <= LEDGER_MAX_LIMIT
    )
    if not is_valid_limit:
        raise ValueError(f"limit must be an integer from 1 to {LEDGER_MAX_LIMIT}, got {limit!r}.")
    declared = ["$limit: Int"]
    arguments = ["limit: $limit"]
    variables: dict[str, object] = {"limit": limit}
    if before_id is not None:
        if not isinstance(before_id, str) or not before_id:
            raise ValueError("before_id must be a ledger entry id from a previous page.")
        declared.append("$before_id: ID")
        arguments.append("before_id: $before_id")
        variables["before_id"] = before_id
    for name, value in (("since", since), ("until", until)):
        if value is not None:
            declared.append(f"${name}: DateTime")
            arguments.append(f"{name}: ${name}")
            variables[name] = _ledger_time(name, value)
    if types is not None:
        if isinstance(types, str) or not all(isinstance(t, str) and t for t in types):
            raise ValueError("types must be a list of entry type names, such as ['debit'].")
        declared.append("$types: [String!]")
        arguments.append("types: $types")
        variables["types"] = list(types)
    query = (
        f"query Ledger({', '.join(declared)}) {{\n"
        f"    payg_ledger({', '.join(arguments)}) {{{q.LEDGER_FIELDS}    }}\n}}\n"
    )
    return query, variables


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

    async def get_usage(self) -> dict:
        """Get account quotas, subscription state, PAYG balance, and current prices."""
        return await self._client._graphql(q.GET_USAGE)

    def get_usage_sync(self) -> dict:
        """Get account usage, subscription state, and current prices (sync)."""
        return asyncio.run(self.get_usage())

    async def get_ledger(
        self,
        *,
        limit: int = 50,
        before_id: str | None = None,
        since: datetime.datetime | str | None = None,
        until: datetime.datetime | str | None = None,
        types: Sequence[str] | None = None,
    ) -> list[LedgerEntry]:
        """Get the org's PAYG ledger (charges, payments, credits), newest first.

        Page backwards by passing the last entry's ``id`` as ``before_id``. ``since``
        is inclusive and ``until`` exclusive; naive datetimes are UTC. ``types``
        keeps only those entry types (``debit``, ``topup``, ``credit_grant``,
        ``adjustment``). ``before_id``, ``since``, ``until`` and ``types`` need a
        backend that supports ledger filters; ``limit`` alone works everywhere.
        """
        query, variables = _ledger_query(
            limit=limit, before_id=before_id, since=since, until=until, types=types
        )
        return await self._client._graphql(
            query,
            variables,
            path="payg_ledger",
            path_default=[],
            return_type=list[LedgerEntry],
        )

    def get_ledger_sync(
        self,
        *,
        limit: int = 50,
        before_id: str | None = None,
        since: datetime.datetime | str | None = None,
        until: datetime.datetime | str | None = None,
        types: Sequence[str] | None = None,
    ) -> list[LedgerEntry]:
        """Get the org's PAYG ledger, newest first (sync)."""
        return asyncio.run(
            self.get_ledger(limit=limit, before_id=before_id, since=since, until=until, types=types)
        )

    async def get_prices(self) -> list[dict]:
        """Get current PAYG model prices with their billing units."""
        return await self._client._graphql(
            q.GET_PRICES, path="payg_prices", path_default=[], return_type=list[dict]
        )

    def get_prices_sync(self) -> list[dict]:
        """Get current PAYG model prices with their billing units (sync)."""
        return asyncio.run(self.get_prices())
