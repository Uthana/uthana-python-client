# Inspect a motion

`motions.get(id)` and `get_sync(id)` include record creation/update dates, saved tags, the authenticated user's favorite/rating metadata and native asset metadata. Missing or inaccessible motions retain the existing error behavior.

```python
motion = await client.motions.get(motion_id)
tags = motion.get("tags")
if isinstance(tags, dict):
    print(tags.get("Method"))
print(motion.get("favorite"), motion.get("rating"))
# rating includes creation/update timestamps, or is None when you have not voted
# favorite: {"created": "...", "updated": "..."} or None
```

Tags can be a dictionary, a string array or null; inspect the type before using dictionary methods. Missing dates remain unknown. Favorite and rating records include creation/update times when present. Asset metadata describes identity/timing, not visual quality, and reading it does not regenerate or modify the motion.

These fields describe your own feedback for the entire motion. They are not organization-wide summaries. No user selector is accepted, and these records omit internal user and annotation IDs. A null rating means you have not rated this motion; a null favorite means it is not in your favorites.

To set a favorite, call `await client.motions.favorite(motion_id)`; to remove it, call `await client.motions.unfavorite(motion_id)`. This is an explicit state, not a toggle: passing True twice keeps it favorited. Reading the favorite metadata does not change it.

Use "like", "dislike" or None to set or clear your vote; see [Motion feedback](motion-feedback.md).
