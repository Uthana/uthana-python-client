# uthana-python-client

[![PyPI version](https://badge.fury.io/py/uthana.svg)](https://badge.fury.io/py/uthana)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

A Python client for Uthana: generate lifelike human motion from text or 2D video, create and auto-rig characters, and manage your motions.

## Install

```bash
pip install uthana
```

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
    # Basic usage (model defaults from models.ini)
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
        model="diffusion-v2",
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

## Video to motion (vtm)

[Docs: Video to motion](https://uthana.com/docs/api/capabilities/video-to-motion)

Extract motion capture from video files. Returns a job to poll until complete.

```python
import asyncio
from uthana import Uthana, UthanaCharacters

uthana_client = Uthana("your-api-key")


async def video_to_motion():
    job = await uthana_client.vtm.create("path/to/dance.mp4", motion_name="my_dance")
    while job.status not in ("FINISHED", "FAILED"):
        await asyncio.sleep(5)  # Non-blocking; other tasks can run while waiting
        job = await uthana_client.jobs.get(job.job_id)
    if job.status == "FINISHED":
        motion_id = job.result["result"]["id"]
        data = await uthana_client.motions.download(
            UthanaCharacters.tar, motion_id, output_format="glb", fps=30
        )
        with open("dance.glb", "wb") as f:
            f.write(data)


asyncio.run(video_to_motion())
```

## Characters

[Docs: Auto-rig / add a character](https://uthana.com/docs/api/capabilities/auto-rig-and-add-character) · [Download a character](https://uthana.com/docs/api/capabilities/downloading-character)

Upload, list, and download characters. Supports auto-rigging for humanoid meshes.

```python
import asyncio
from uthana import Uthana

uthana_client = Uthana("your-api-key")


async def manage_characters():
    # Upload and auto-rig a character
    output = await uthana_client.characters.create("path/to/character.glb")
    print(output.character_id)
    print(output.auto_rig_confidence)  # 0–1.0, higher is better

    # Download the rigged character
    data = await uthana_client.characters.download(output.character_id, output_format="glb")
    with open("character_rigged.glb", "wb") as f:
        f.write(data)

    # List all characters
    for c in await uthana_client.characters.list():
        print(c.id, c.name)

    # Download motion preview (WebM, does not charge download seconds)
    preview_bytes = await uthana_client.characters.download_preview(
        character_id, motion_id
    )
    with open("preview.webm", "wb") as f:
        f.write(preview_bytes)


asyncio.run(manage_characters())
```

## Motions

[Docs: Asset management](https://uthana.com/docs/api/capabilities/asset-management) · [Retargeting](https://uthana.com/docs/api/capabilities/retargeting)

List, download, delete, rename, and favorite motions.

```python
import asyncio
from uthana import Uthana, UthanaCharacters

uthana_client = Uthana("your-api-key")


async def manage_motions():
    # List all motions
    for m in await uthana_client.motions.list():
        print(m.id, m.name)

    # Download a motion
    data = await uthana_client.motions.download(
        UthanaCharacters.tar,
        "motion-id",
        output_format="glb",
        fps=30,
        no_mesh=False,
    )

    # Rename a motion
    await uthana_client.motions.rename("motion-id", "New name")

    # Delete a motion (soft delete)
    await uthana_client.motions.delete("motion-id")

    # Favorite / unfavorite
    await uthana_client.motions.favorite("motion-id", True)

    # Stitch two motions together (model defaults from models.ini)
    output = await uthana_client.motions.create_stitched(
        character_id=UthanaCharacters.tar,
        leading_motion_id="motion-1",
        trailing_motion_id="motion-2",
        duration=0.5,
    )
    print(output.motion_id)


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
    print(user.id, user.name, user.email)

    org = await uthana_client.org.get_org()
    print(org.name)
    print(org.motion_download_secs_per_month_remaining, "seconds remaining")


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
    print(job.status)   # RESERVED, READY, FINISHED, FAILED
    print(job.result)   # Result payload when FINISHED


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
