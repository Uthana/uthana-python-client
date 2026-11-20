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

These change only your feedback. They never generate a motion. Each favorite call sets a state; repeating it does not toggle. A cleared rating is different from a dislike. The returned motion's `rating` is null when you have not rated it.

Async applications use `await client.motions.rate(id, value)`, `await client.motions.favorite(id)` and `await client.motions.unfavorite(id)`. Existing `rate(id, 1)`, `rate(id, 0)` and `favorite(id, False)` calls remain supported, including their synchronous forms. Numeric scores mean 1=like and 0=dislike; 2 is invalid.

Clearing requires server support for `clear_motion_rating`. Servers without that field reject the request; the client does not replace a clear with a dislike or retry it automatically. A missing clear confirmation raises `kind="uncertain"`; inspect the current vote before another attempt.

## Advanced annotation ratings

Existing calls with `label_id` and a like/dislike value still work. Clearing applies only to the whole motion: passing `label_id` with None is rejected before any write. No operation accepts a user selector.
