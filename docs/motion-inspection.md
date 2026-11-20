# Inspect a motion

`motions.get(id)` and `get_sync(id)` include record creation/update dates, saved tags, the caller's favorite/rating metadata and native asset metadata, matching the JS client lookup. Missing or inaccessible motions retain the existing error behavior.

```python
motion = await client.motions.get(motion_id)
tags = motion.get("tags")
if isinstance(tags, dict):
    print(tags.get("Method"))
print(motion.get("favorite"), motion.get("rating"))
```

Tags can be a dictionary, a string array or null; inspect the type before using dictionary methods. Missing dates, labels and ratings remain unknown. A known zero rating means thumbs down. Asset metadata describes identity/timing, not visual quality, and reading it does not regenerate or modify the motion.
