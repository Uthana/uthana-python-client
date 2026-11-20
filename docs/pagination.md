# Find characters and motions

Use `characters.list_paged()` and `motions.list_paged()` to search saved names, choose an order, and retrieve one page at a time. These methods require the API's `characters_paged` and `motions_paged` fields. Existing `list()` methods keep their behavior and return lists.

```python
from uthana import Uthana

client = Uthana("YOUR_API_KEY")
page = client.characters.list_paged_sync(source="mine", order="created_desc", limit=20)
for character in page["items"]:
    print(character["id"], character["name"], character["created"])
```

`mine` means your organization's assets, including teammates' assets. `uthana` selects shared Uthana examples, and `all` includes both (the default). Creation time is the asset record's creation time, not a separate upload date. A missing date remains `None`; visibility does not imply permission to edit.

## Search and continue

```python
page = await client.motions.list_paged(
    query="walk slow", source="mine", order="name_asc", method="TextToMotion", limit=50
)
while True:
    for motion in page["items"]:
        print(motion["id"], motion["name"])
    if page["next_cursor"] is None:
        break
    page = await client.motions.list_paged(
        query="walk slow", source="mine", order="name_asc", method="TextToMotion",
        limit=50, cursor=page["next_cursor"]
    )
```

Search matches every word in the name, ignoring case. Each word needs at least three consecutive letters or digits; the complete query is at most 200 characters. The optional motion `method` matches the saved Method tag exactly, ignoring case, and is at most 100 characters; it does not reliably identify the model version. This searches saved assets, not library candidates.

Choose `created_desc` (default), `created_asc`, `name_asc`, or `name_desc`. IDs break ties and missing sort values come last. Page size is 1–100, default 20. Omitted and `None` options use server defaults; other invalid options raise API errors rather than silently changing the request.

Pass the opaque `next_cursor` unchanged with the same account, query, source, method, and order. You may change the page size. A null cursor ends the results. If a cursor becomes invalid, start again without it. Pages are not a snapshot: assets can be created, renamed, or deleted between calls. Unlike the existing recent-motion list, these queries can find older matching motions beyond the recent 1,000. Refined video motions replace their base version in this listing.

Both methods also have synchronous forms, `list_paged_sync()`. No method automatically fetches every page or retries a failed request.
