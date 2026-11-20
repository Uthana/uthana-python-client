# Like, dislike and favorite motions

```python
from uthana import Uthana

client = Uthana("YOUR_API_KEY")
try:
    client.motions.rate_sync("motion-id", "like")
    client.motions.rate_sync("motion-id", "dislike")
    client.motions.rate_sync("motion-id", None)  # remove your vote
    client.motions.favorite_sync("motion-id")
    client.motions.unfavorite_sync("motion-id")
finally:
    client.close()
```

Use "like" or "dislike" to rate a motion, or `None` to clear your vote.

Async applications use `await client.motions.rate(id, value)`, `await client.motions.favorite(id)` and `await client.motions.unfavorite(id)`.

A missing confirmation when clearing a vote raises `kind="uncertain"`. Check your current vote before trying again; the client does not retry automatically.

## Advanced annotation ratings

Existing calls with `label_id` and a like/dislike value still work. Clearing applies only to the whole motion: passing `label_id` with None is rejected before any write. No operation accepts a user selector.
