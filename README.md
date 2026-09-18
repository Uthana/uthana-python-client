# uthana-python-client

[![PyPI version](https://badge.fury.io/py/uthana.svg)](https://badge.fury.io/py/uthana)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

A Python client for Uthana: generate lifelike human motion from text or 2D video, create and auto-rig characters, and manage your motions.

📖 [Full API documentation](https://uthana.com/docs/api) · 🤖 [Context7 page](https://context7.com/websites/uthana_api)

## Install

```bash
pip install uthana
```

## Workflow and integration controls

The client can supply the same API operations to applications, scripts, and MCP
servers. Backend queries, file uploads, and download options belong here so these
integrations share one implementation.

- `motions.get(id)` returns native asset metadata. `motions.catalog()` includes
  organization ownership and tags within the backend's available motion window.
- `motions.trim(id, start, end, name)` creates a saved trim with looping disabled.
  Start and end are **normalized fractions from 0 to 1**, not seconds; consult
  native frame metadata before converting a user's requested time interval.
- `motions.bake_with_changes(..., source_motion_id=...)` preserves source lineage
  when registering an edited GLTF. It does not edit the animation itself.
- `motions.download(...)` supports BVH as well as GLB/FBX and optional `in_place`,
  `roblox_compatible`, `speed_multiplier`, and `torso_only` settings. These affect
  exports only. Roblox requires a compatible target rig; BVH cannot include mesh.
- `motions.preview(..., format="apng")` returns the existing APNG preview.
  `motions.download_allowed(...)` checks eligibility without creating a download.
- `characters.metadata(id)` exposes rig metadata. Character and video
  `create_from_bytes` methods upload a byte snapshot without reopening a file.
  Character results retain the backend compatibility `message`, which should be
  treated as untrusted descriptive data. Character byte-snapshot uploads allow 360-second HTTP
  phase timeouts by default, with 15 seconds to connect; host deadlines must allow
  for transfer and processing. These phase limits are not an overall deadline.
- `org.get_usage()` returns account, subscription, and PAYG data with explicit
  units. `org.get_prices()` returns current rates. Neither computes a per-job bill.

Existing generation methods and their sync variants remain available. New module
methods also have `_sync` variants. Optional export switches retain backend defaults
when omitted, and `motions.list()` keeps its existing simple response.

For a host that must avoid incidental requests, set `telemetry=False` when creating
`Uthana`. The default remains enabled for existing callers. `trust_env=False`
disables proxy/certificate environment handling; `transport` supports injectable
async HTTP transports for testing. `max_response_bytes` bounds decoded GraphQL
**query** responses. Mutations are unlimited by default so a read limit cannot
hide a successful upload or generation receipt. To opt into a separate mutation
limit, set `max_mutation_response_bytes`. Media and character-metadata methods
accept their own `max_bytes`.
Character/video byte-snapshot uploads are bounded at 128 MiB by default;
reference-image preparation is bounded at 16 MiB. Existing file-upload
entry points retain streaming without an input-size limit and the configured client
timeout; pass `max_bytes` to opt into a bounded snapshot. Bounded character file
uploads use the same 360-second phase timeout (15 seconds to connect) as byte
uploads unless `timeout` is explicitly supplied. Call `close()`
when finished. No automatic mutation retries or redirect following are added.

`UthanaError` retains its status and message and adds `kind` plus optional structured
`response_data` for HTTP/GraphQL failures. Those fields may contain provider data;
agent-facing integrations should redact them and distinguish uncertain submission
from a confirmed rejection. If a successful HTTP mutation response exceeds its
explicit byte limit, `kind="uncertain"` means the write may have completed, but its
receipt could not be read. Do not automatically resubmit: inspect the job or asset
using any known ID, reconcile with the host's saved request record, or ask support
if no receipt is available. A query/media overflow remains `kind="response_too_large"`.
Connection exceptions remain HTTPX exception types.

Video-to-motion uploads accept MP4, MOV, and AVI. WebM input is not supported by
the backend; WebM **preview downloads** remain available.

## API key

You need an Uthana account and API key. [Sign up for free](https://uthana.com), then get your API key from [account settings](https://uthana.com/app/settings) once logged in. For full setup, verification, and capabilities, see the [Uthana API docs](https://uthana.com/docs/api/).

## Quick start

### Context7

[Context7](https://context7.com/) helps LLMs and AI code editors pull up-to-date documentation instead of relying on stale training data. Use it in prompts, e.g.: "How do I create a text-to-motion animation with the Uthana API? use context7 library /websites/uthana_api". Add Uthana as a source: [context7.com/websites/uthana_api](https://context7.com/websites/uthana_api), then [install Context7](https://github.com/upstash/context7#installation) in your IDE.

### Async by default

All methods are **async** and return coroutines. Use `await` inside an async function and `asyncio.run()` to execute. Async calls are non-blocking: the event loop can run other tasks while waiting on I/O, which is ideal for concurrent requests or UI applications.

Sync variants exist for every method, suffixed with `_sync`. These block until the request completes and are simpler for scripts or when you don't need concurrency.

```python
import asyncio
from uthana import Uthana

uthana_client = Uthana("your-api-key")

# Async (non-blocking)
async def async_example():
    output = await uthana_client.ttm.create("a person walking")
    data = await uthana_client.motions.download(output.character_id, output.motion_id, output_format="glb")
    return data

data = asyncio.run(async_example())

# Sync (blocking)
def sync_example():
    output = uthana_client.ttm.create_sync("a person walking")
    data = uthana_client.motions.download_sync(output.character_id, output.motion_id, output_format="glb")
    return data

data = sync_example()
```

## Text to motion (ttm)

[Docs: Text to motion](https://uthana.com/docs/api/capabilities/text-to-motion)

Generate 3D character animations from natural language prompts.

```python
import asyncio
from uthana import Uthana, UthanaCharacters

uthana_client = Uthana("your-api-key")


async def text_to_motion():
    # Basic usage (default model: text-to-motion-1.0)
    output = await uthana_client.ttm.create("a person walking forward")
    print(output.character_id, output.motion_id)

    # Use a specific character (default is Tar)
    output = await uthana_client.ttm.create(
        "a person dancing",
        character_id=UthanaCharacters.ava,
    )

    # Explicit model and advanced options
    output = await uthana_client.ttm.create(
        "a person waving hello",
        model="text-to-motion-2.0",
        character_id=UthanaCharacters.manny,
        length=5.0,
        cfg_scale=2.5,
        seed=42,
    )

    # Download the motion
    data = await uthana_client.motions.download(
        output.character_id,
        output.motion_id,
        output_format="glb",
        fps=30,
    )


asyncio.run(text_to_motion())
```

**Available models:** `text-to-motion-1.0` (default), `text-to-motion-2.0`.

## Text to motion 3.0 async job (ttm.create_job)

`text-to-motion-3.0` runs as an async job and returns a job dict to poll — the same pattern as video-to-motion. Available to any account on the [pay-as-you-go plan](https://uthana.com/docs/api/pricing).

```python
import asyncio
from uthana import Uthana, UthanaCharacters

uthana_client = Uthana("your-api-key")


async def ttm_async_job():
    # Submit the job
    job = await uthana_client.ttm.create_job(
        "a person doing jumping jacks",
        model="text-to-motion-3.0",
        length=8,            # optional, 4–10 seconds
        rewrite_prompt=True, # optional, default True
        character_id=UthanaCharacters.tar,  # optional
    )

    # Poll until finished
    while job["status"] not in ("FINISHED", "FAILED"):
        await asyncio.sleep(5)
        job = await uthana_client.jobs.get(job["id"])
    if job["status"] == "FINISHED":
        motion_id = job["result"]["result"]["id"]
        print(motion_id)


asyncio.run(ttm_async_job())
```

Sync variant: `uthana_client.ttm.create_job_sync(...)`.

## Locomotion

[Docs: Locomotion](https://uthana.com/docs/api/capabilities/locomotion)

Generate controllable, loopable travel motion for a character (stride count, speed, style, direction).

```python
import asyncio
from uthana import Uthana, UthanaCharacters

uthana_client = Uthana("your-api-key")


async def locomotion_example():
    styles = await uthana_client.motions.list_locomotion_styles()
    print("Available style_id values:", styles)

    output = await uthana_client.motions.create_locomotion(
        UthanaCharacters.tar,
        strides=2,
        move_speed=1.3,
        style_id="neutral_male_a",
        travel_angle=0,
    )
    print(output.character_id, output.motion_id)


asyncio.run(locomotion_example())
```

## Loop an existing motion

[Docs: Stitch & loop motions](https://uthana.com/docs/api/capabilities/stitch-loop-motions)

The simplified looping API is a **preview API** and may change. It returns a new
`Motion` synchronously, preserving the source motion. Both async and `_sync`
variants are available.

```python
looped = await uthana_client.motions.create_looped_motion(
    character_id, motion_id,
    trim_start_pct=0.0, trim_end_pct=1.0,
    zone_duration=2.0, loop_mode="closed", zone_mode="modify",
)
print(looped["id"])
```

Trim bounds are normalized fractions (`0 <= start < end <= 1`), and the transition
is a positive number of seconds. `closed` returns to the start; `open` continues
travel. `modify` changes existing frames, while `extend` adds transition frames.
An open loop may specify `zone_end_position={"x": 1.0, "y": 2.0,
"facing_angle": 0.5}`: planar x/y coordinates and an optional facing angle in
radians. Omit the target to let the API infer travel. The SDK rejects nonfinite
values, booleans, invalid modes, and targets on closed loops before submission.
Omitting `timeout` (or passing `None`) uses 360-second HTTP phase limits with a
15-second connect limit, independently of the general client timeout. An explicit
`timeout` accepts seconds or `httpx.Timeout` and overrides those limits.

Looping uses the published stitching/looping price per generated output second;
it is not a free trim. Inspect the resulting motion's duration and repeated
playback before claiming a seamless loop.

## Stitch two existing motions

`motions.create_stitched_motion(character_id, prefix, suffix)` uses the enhanced
stitch preview API; its `_sync` variant has the same arguments. It returns a new
`Motion` dictionary synchronously. This is separate from single-motion looping.

Each clip is a `StitchParams` (import with `from uthana import StitchParams`)
containing its motion ID, duration,
trim times in seconds and matching fractions, root world position/rotation, and
pelvis states at zero/lower/upper trim. See the
[complete API input contract](https://uthana.com/docs/api/capabilities/stitch-loop-motions).
Use `stitch_loop=False`, a positive `stitch_duration` (recommended 0.1–3 seconds),
and `prompt=""` unless a transition prompt is intended. The prefix determines
transition settings; keep both inputs consistent.

```python
import httpx

# prefix_samples and suffix_samples are full StitchParams from your motion loader.
stitched = await uthana_client.motions.create_stitched_motion(
    character_id, prefix_samples, suffix_samples,
    timeout=httpx.Timeout(360, connect=15),
)
print(stitched["id"])
```

Supply real poses sampled on the same target character in a shared world scene.
Positions are meters in Y-up space (x/z horizontal), rotations are approximately
unit x/y/z/w quaternions, and facing yaw is in radians. The client validates
fields, finite values, quaternion length, and trim time/fraction consistency
before submitting. It copies validated inputs and never supplies guessed poses,
samples animations, aligns the scene, or automatically retries a mutation.

Stitching defaults to 360-second HTTP phase limits and 15 seconds to connect when
`timeout` is omitted or `None`; an explicit value overrides them. Allow the host
enough time for the synchronous stitch or loop (at least 420 seconds with these
phase limits, longer for transfers). Phase timeouts are not an overall deadline.
If either response lacks a nonempty motion ID, the client raises
`UthanaError(kind="uncertain")`: inspect existing work before resubmitting.
Stitching keeps its published price per generated output second.
Real playback and contact review are
still required to establish transition quality. No pose-loader dependency is
added to the Python client.

## Video to motion (vtm)

[Docs: Video to motion](https://uthana.com/docs/api/capabilities/video-to-motion)

Extract motion capture from video files. Returns a job to poll until complete.

```python
import asyncio
from uthana import Uthana, UthanaCharacters

uthana_client = Uthana("your-api-key")


async def video_to_motion():
    # Default model: video-to-motion-2.0 (single base motion)
    job = await uthana_client.vtm.create("path/to/dance.mp4", motion_name="my_dance")

    # Use video-to-motion-2.1 for DCM refinement motion IDs
    # job = await uthana_client.vtm.create(
    #     "path/to/dance.mp4", motion_name="my_dance", model="video-to-motion-2.1"
    # )

    while job["status"] not in ("FINISHED", "FAILED"):
        await asyncio.sleep(5)  # Non-blocking; other tasks can run while waiting
        job = await uthana_client.jobs.get(job["id"])
    if job["status"] == "FINISHED":
        motion_id = job["result"]["result"]["id"]
        data = await uthana_client.motions.download(
            UthanaCharacters.tar, motion_id, output_format="glb", fps=30
        )
        with open("dance.glb", "wb") as f:
            f.write(data)


asyncio.run(video_to_motion())
```

**Available models:** `video-to-motion-2.0` (default), `video-to-motion-2.1`.

## Characters

[Docs: Auto-rig / add a character](https://uthana.com/docs/api/capabilities/auto-rig-and-add-character) · [Download a character](https://uthana.com/docs/api/capabilities/downloading-character)

Upload, list, and download characters. Supports auto-rigging for humanoid meshes, and generation from text prompts or image files.

```python
import asyncio
from uthana import Uthana

uthana_client = Uthana("your-api-key")


async def manage_characters():
    # Upload and auto-rig a character from a file
    output = await uthana_client.characters.create_from_file("path/to/character.glb")
    print(output.character_id)
    print(output.auto_rig_confidence)  # 0–1.0, higher is better

    # Download the rigged character
    data = await uthana_client.characters.download(output.character_id, output_format="glb")
    with open("character_rigged.glb", "wb") as f:
        f.write(data)

    # List all characters
    for c in await uthana_client.characters.list():
        print(c.get("id"), c.get("name"))

    # Text-to-character: one-shot with callback
    result = await uthana_client.characters.create_from_prompt(
        prompt="a knight in shining armor",
        name="Knight",
        on_previews_ready=lambda previews: previews[0]["key"],
    )
    print(result.character.get("id"))

    # Text-to-character: async callback (e.g. show a UI and return the chosen key)
    result = await uthana_client.characters.create_from_prompt(
        prompt="a futuristic soldier",
        on_previews_ready=lambda previews: show_picker_ui(previews),
    )

    # Text-to-character: two-step (inspect previews before confirming)
    pending = await uthana_client.characters.create_from_prompt(prompt="a futuristic soldier")
    # pending.previews is a list of {"key": ..., "url": ...} — show them to the user
    result = await uthana_client.characters.generate_from_image(pending, pending.previews[0]["key"])

    # Image-to-character: upload an image file (always one-shot)
    result = await uthana_client.characters.create_from_image("path/to/reference.png")

    # Rename or delete
    await uthana_client.characters.rename(result.character["id"], "New name")
    await uthana_client.characters.delete(result.character["id"])


asyncio.run(manage_characters())
```

### Resumable image-to-character integration

`characters.create_from_image(path)` retains its existing one-shot behavior:
unbounded streaming unless `max_bytes` is supplied, the configured client timeout,
and no per-call `include_fingers` or `timeout` option. Use the two-step API below
when you need its longer operation defaults or explicit controls.
Integrations that must persist intermediate IDs can instead use two public steps:

```python
from pathlib import Path
import httpx

pending = await uthana_client.characters.prepare_from_image_bytes(
    "reference.png", Path("reference.png").read_bytes(),
    timeout=httpx.Timeout(360, connect=15),
)
# Persist pending.character_id and pending.previews[0]["key"] before proceeding.
result = await uthana_client.characters.generate_from_image(
    pending, pending.previews[0]["key"], name="My character", include_fingers=True,
    timeout=httpx.Timeout(660, connect=15),
)
print(result.character["id"])
```

Preparation accepts a nonempty PNG/JPEG byte snapshot up to 16 MiB by default.
The calling integration should validate image content and dimensions. Preparation
returns an intermediate character ID and image key, not a finished rig. Both
steps are synchronous API operations despite the async Python interface; set a
host deadline long enough for both stages and transfer. The SDK does not save
receipts or retry mutations. After an uncertain response, inspect the existing
character before attempting another paid generation. A confirmed rejection of
finalization can be retried explicitly using the persisted preparation result.
Preparation defaults to 360-second HTTP phase limits; finalization through
`generate_from_image` defaults to 660 seconds. Both allow 15 seconds to connect.
Omitted/`None` timeouts use these operation defaults instead of the general client
timeout; explicit seconds or `httpx.Timeout` overrides are honored. Host deadlines
must cover both stages and transfer. Omitted `name` and `include_fingers` retain
the backend defaults. Sync variants use the same limits. Character generation
retains its published price.

## Motions

[Docs: Asset management](https://uthana.com/docs/api/capabilities/asset-management) · [Retargeting](https://uthana.com/docs/api/capabilities/retargeting)

List, download, preview, delete, rename, favorite, and bake motions.

```python
import asyncio
from uthana import Uthana, UthanaCharacters

uthana_client = Uthana("your-api-key")


async def manage_motions():
    # List all motions
    for m in await uthana_client.motions.list():
        print(m.get("id"), m.get("name"))

    # Download a motion
    data = await uthana_client.motions.download(
        UthanaCharacters.tar,
        "motion-id",
        output_format="glb",
        fps=30,
        no_mesh=False,
    )

    # Download motion preview WebM (does not charge download seconds)
    preview_bytes = await uthana_client.motions.preview(character_id, motion_id)
    with open("preview.webm", "wb") as f:
        f.write(preview_bytes)

    # Rename a motion
    await uthana_client.motions.rename("motion-id", "New name")

    # Delete a motion (soft delete)
    await uthana_client.motions.delete("motion-id")

    # Favorite / unfavorite
    await uthana_client.motions.favorite("motion-id", True)

    # Bake custom GLTF animation data as a new motion for an existing character
    result = await uthana_client.motions.bake_with_changes(
        gltf_content, "My motion", character_id=character_id
    )
    print(result.motion_id, result.character_id)


asyncio.run(manage_motions())
```

## Organization and user (org)

[Docs: Account and organization](https://uthana.com/docs/api/capabilities/account-and-organization)

Get user and organization info, including quota.

```python
import asyncio
from uthana import Uthana

uthana_client = Uthana("your-api-key")


async def get_org_info():
    user = await uthana_client.org.get_user()
    print(user.get("id"), user.get("name"), user.get("email"))

    org = await uthana_client.org.get_org()
    print(org.get("name"))
    print(org.get("motion_download_secs_per_month_remaining"), "seconds remaining")


asyncio.run(get_org_info())
```

## Jobs

[Docs: Video to motion](https://uthana.com/docs/api/capabilities/video-to-motion) (job polling)

Poll async jobs (e.g. video to motion).

```python
import asyncio
from uthana import Uthana

uthana_client = Uthana("your-api-key")


async def poll_job():
    job = await uthana_client.jobs.get("job-id")
    print(job["status"])   # RESERVED, READY, FINISHED, FAILED
    print(job["result"])   # Result payload when FINISHED


asyncio.run(poll_job())
```

## Uthana characters

[Docs: Auto-rig / add a character](https://uthana.com/docs/api/capabilities/auto-rig-and-add-character)

Pre-built characters you can use without uploading your own:

| Attribute                | Character ID |
| ------------------------ | ------------ |
| `UthanaCharacters.tar`   | cXi2eAP19XwQ |
| `UthanaCharacters.ava`   | cmEE2fT4aSaC |
| `UthanaCharacters.manny` | c43tbGks3crJ |
| `UthanaCharacters.quinn` | czCjWEMtWxt8 |
| `UthanaCharacters.y_bot` | cJM4ngRqXg83 |

## Testing

Integration tests (`tests/test_client.py`) require `UTHANA_API_KEY`. Use `.env.local` (gitignored) or env vars:

```bash
# .env.local
UTHANA_API_KEY=your_key
UTHANA_DOMAIN=custom.uthana.com  # optional, for non-production
```

## Releasing and PyPI

The `uthana` package is published automatically. The workflow is:

1. In a PR, run `make set-version VERSION=1.2.3` to bump `pyproject.toml`, then commit and merge.
2. On merge to `main`, **`.github/workflows/release.yml`** detects that the new version is not yet on PyPI, runs tests, publishes via OIDC, and creates the `v1.2.3` git tag and GitHub Release.

Re-merging the same version is a no-op — the workflow checks PyPI before doing anything.

### Bump version in a branch

```bash
make set-version VERSION=1.2.3
```

Writes `1.2.3` to `pyproject.toml`. No git operations — just commit and open a PR.

### Manual publish (fallback if CI fails)

```bash
make release-publish-dry-run   # build + simulate, no upload
make release-publish           # build + publish for real
```

Both require a PyPI API token. Set `UV_PUBLISH_TOKEN` from your [PyPI account](https://pypi.org/manage/account/token/) then run the command. For TestPyPI, run directly:

```bash
uv run python scripts/release.py publish --dry-run --index testpypi
uv run python scripts/release.py publish --index testpypi
```

After a successful manual publish, create the git tag manually if CI did not:

```bash
git tag -a v1.2.3 -m "Release v1.2.3"
git push origin v1.2.3
```

### Auth: PyPI Trusted Publishing (OIDC)

The release workflow uses PyPI **Trusted Publishers** (OIDC) — no `PYPI_API_TOKEN` secret required. The Trusted Publisher must be configured on [pypi.org](https://pypi.org/manage/project/uthana/settings/publishing/) for this repository and workflow file (`release.yml`).

## Type hints

The package ships an empty `py.typed` marker ([PEP 561](https://peps.python.org/pep-0561/)) so type checkers treat `uthana` as providing inline types. Keep `src/uthana/py.typed` in the repo and in package data (`pyproject.toml`).

## Custom domain

Use a different API host by passing `domain=`:

```python
uthana_client = Uthana("your-api-key", domain="custom.example.com")
```

## Support

- [Discord](https://discord.gg/PbMzMPSyTG) for community support
- [support@uthana.com](mailto:support@uthana.com) or Slack for priority support

## License

Apache 2.0
