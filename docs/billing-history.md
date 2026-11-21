# Recent billing history

`org.get_ledger()` and `org.get_ledger_sync()` return PAYG ledger entries from the last 7 days, newest first. Use the API directly or the web for older history.

```python
entries = client.org.get_ledger_sync(limit=50)
if entries:
    older = client.org.get_ledger_sync(limit=50, before_id=entries[-1]["id"])
```

Every request, including pagination, sends an inclusive `since` and exclusive `until` bound. Omitted or null bounds default to seven days ago and now, relative to the client clock. Explicit bounds must fall within that window, with `since` earlier than `until`; invalid bounds raise `ValueError` before any request. Naive datetimes and timestamps are treated as UTC. Pass timezone-aware timestamps to avoid ambiguity.

Retain explicit filters when paging. The limit defaults to 50 and accepts 1–500. These methods only read history; they do not change billing. The backend is unchanged, and this SDK limit is not an authorization restriction.
