# Jobs, ratings and download history

`jobs.wait()` polls an existing job. It never submits generation or repeats an operation. Both async and sync forms preserve the job's result and normalize timestamps like `jobs.get()`.

```python
job = await client.jobs.wait(job_id, interval_seconds=5, timeout_seconds=300)
# Or: client.jobs.wait_sync(job_id, interval_seconds=5, timeout_seconds=300)
```

Intervals and deadlines are positive finite seconds. The interval defaults to five seconds; the deadline defaults to the client's read timeout or 120 seconds if that timeout is unbounded. A failed job raises `UthanaError` with status 500. An elapsed deadline, including during a slow read, raises status 408. That stops local polling, not the upstream job: keep the same job ID to resume. A missing or inaccessible job raises status 404 immediately. A missing or malformed status raises `kind="invalid_response"` instead of polling until timeout. Transport and authorization errors propagate without retry. FINISHED means processing ended; inspect its result and visual quality separately.

## Rating

```python
await client.motions.rate(motion_id, "like")
await client.motions.rate(motion_id, "dislike")
await client.motions.rate(motion_id, None)  # clear your whole-motion vote
client.motions.rate_sync(motion_id, "like")
```

Use "like" or "dislike" to rate a motion, or `None` to clear your vote.

### Advanced annotation workflows

The optional `label_id` parameter remains available for existing integrations that rate a particular motion annotation. It is an internal annotation identifier; omit it for ordinary whole-motion ratings.

## Download history

```python
records = await client.motions.list_downloads()
# Or: client.motions.list_downloads_sync()
for record in records:
    print(record["motion_id"], record["character_id"], record["secs"])
```

This is the same download-history query exposed by the JS client's `motionDownloads.list()`. The API provides no page cursor or filters for this query. Preserve missing/null dates and nested motion records. Download seconds are not generation charges; use `org.get_ledger()` for actual PAYG charges. `motions.download_allowed()` remains the eligibility check.
