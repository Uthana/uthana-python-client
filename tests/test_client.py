import os
import time
from pathlib import Path

import pytest

from uthana import Client
from uthana.client import DefaultCharacters

FIXTURES_DIR = Path(__file__).parent / "fixtures"
ARTIFACTS_DIR = Path(__file__).parent / "artifacts"

API_KEY = os.environ.get("UTHANA_API_KEY")
requires_api_key = pytest.mark.skipif(not API_KEY, reason="UTHANA_API_KEY not set")


def test_client_init():
    client = Client("test-key")
    assert client.base_url == "https://uthana.com"
    assert client.graphql_url == "https://uthana.com/graphql"


def test_client_staging():
    client = Client("test-key", staging=True)
    assert client.base_url == "https://staging.uthana.com"


@requires_api_key
def test_create_text_to_motion_v1_glb():
    client = Client(API_KEY, staging=True)
    output = client.create_text_to_motion_v1("a person walking forward")

    assert output.character_id
    assert output.motion_id

    ARTIFACTS_DIR.mkdir(exist_ok=True)
    data = client.download_motion(output.character_id, output.motion_id, output_format="glb", fps=30)
    (ARTIFACTS_DIR / "walking_forward_30.glb").write_bytes(data)


@requires_api_key
def test_create_text_to_motion_v1_fbx():
    client = Client(API_KEY, staging=True)
    output = client.create_text_to_motion_v1("a person walking forward")

    assert output.character_id
    assert output.motion_id

    ARTIFACTS_DIR.mkdir(exist_ok=True)
    data = client.download_motion(output.character_id, output.motion_id, output_format="fbx", fps=60)
    (ARTIFACTS_DIR / "walking_forward_60.fbx").write_bytes(data)


@requires_api_key
def test_create_character_glb():
    client = Client(API_KEY, staging=True)
    output = client.create_character(str(FIXTURES_DIR / "icegoblin.glb"))

    assert output.character_id
    assert output.url
    assert output.auto_rig_confidence is not None and output.auto_rig_confidence < 1.0

    ARTIFACTS_DIR.mkdir(exist_ok=True)
    data = client.download_character(output.character_id, output_format="glb")
    (ARTIFACTS_DIR / "icegoblin_rigged.glb").write_bytes(data)


@requires_api_key
def test_create_character_fbx():
    client = Client(API_KEY, staging=True)
    output = client.create_character(str(FIXTURES_DIR / "wrestler.fbx"))

    assert output.character_id
    assert output.url
    assert output.auto_rig_confidence is not None and output.auto_rig_confidence > 0.0

    ARTIFACTS_DIR.mkdir(exist_ok=True)
    data = client.download_character(output.character_id, output_format="fbx")
    (ARTIFACTS_DIR / "wrestler_rigged.fbx").write_bytes(data)


# Async tests


@requires_api_key
@pytest.mark.asyncio
async def test_acreate_text_to_motion_v1_glb():
    client = Client(API_KEY, staging=True)
    output = await client.acreate_text_to_motion_v1("a person walking forward")

    assert output.character_id
    assert output.motion_id

    ARTIFACTS_DIR.mkdir(exist_ok=True)
    data = await client.adownload_motion(output.character_id, output.motion_id, output_format="glb", fps=30)
    (ARTIFACTS_DIR / "async_walking_forward_30.glb").write_bytes(data)


@requires_api_key
@pytest.mark.asyncio
async def test_acreate_text_to_motion_v1_fbx():
    client = Client(API_KEY, staging=True)
    output = await client.acreate_text_to_motion_v1("a person walking forward")

    assert output.character_id
    assert output.motion_id

    ARTIFACTS_DIR.mkdir(exist_ok=True)
    data = await client.adownload_motion(output.character_id, output.motion_id, output_format="fbx", fps=60)
    (ARTIFACTS_DIR / "async_walking_forward_60.fbx").write_bytes(data)


@requires_api_key
@pytest.mark.asyncio
async def test_acreate_text_to_motion_v2_glb():
    client = Client(API_KEY, staging=True)
    output = await client.acreate_text_to_motion_v2("a person dancing")

    assert output.character_id
    assert output.motion_id

    ARTIFACTS_DIR.mkdir(exist_ok=True)
    data = await client.adownload_motion(output.character_id, output.motion_id, output_format="glb", fps=30)
    (ARTIFACTS_DIR / "async_dancing_30.glb").write_bytes(data)


@requires_api_key
@pytest.mark.asyncio
async def test_acreate_character_glb():
    client = Client(API_KEY, staging=True)
    output = await client.acreate_character(str(FIXTURES_DIR / "icegoblin.glb"))

    assert output.character_id
    assert output.url
    assert output.auto_rig_confidence is not None and output.auto_rig_confidence < 1.0

    ARTIFACTS_DIR.mkdir(exist_ok=True)
    data = await client.adownload_character(output.character_id, output_format="glb")
    (ARTIFACTS_DIR / "async_icegoblin_rigged.glb").write_bytes(data)


@requires_api_key
@pytest.mark.asyncio
async def test_acreate_character_fbx():
    client = Client(API_KEY, staging=True)
    output = await client.acreate_character(str(FIXTURES_DIR / "wrestler.fbx"))

    assert output.character_id
    assert output.url
    assert output.auto_rig_confidence is not None and output.auto_rig_confidence > 0.0

    ARTIFACTS_DIR.mkdir(exist_ok=True)
    data = await client.adownload_character(output.character_id, output_format="fbx")
    (ARTIFACTS_DIR / "async_wrestler_rigged.fbx").write_bytes(data)


def _poll_job(client: Client, job_id: str, timeout: float = 900.0, interval: float = 2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = client.get_job(job_id)
        if job.status in ("FINISHED", "FAILED"):
            return job
        time.sleep(interval)
    raise TimeoutError(f"Job {job_id} did not complete within {timeout}s")


async def _apoll_job(client: Client, job_id: str, timeout: float = 900.0, interval: float = 2.0):
    import asyncio
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = await client.aget_job(job_id)
        if job.status in ("FINISHED", "FAILED"):
            return job
        await asyncio.sleep(interval)
    raise TimeoutError(f"Job {job_id} did not complete within {timeout}s")


@requires_api_key
def test_create_video_to_motion():
    client = Client(API_KEY, staging=True)
    job_output = client.create_video_to_motion(str(FIXTURES_DIR / "dance.mp4"))

    assert job_output.job_id
    assert job_output.status

    job_output = _poll_job(client, job_output.job_id)
    assert job_output.status == "FINISHED"

    motion_id = job_output.result["result"]["id"]
    assert motion_id

    ARTIFACTS_DIR.mkdir(exist_ok=True)
    data = client.download_motion(
        DefaultCharacters.tar, motion_id, output_format="glb", fps=30,
    )
    (ARTIFACTS_DIR / "video_dance_30.glb").write_bytes(data)


@requires_api_key
@pytest.mark.asyncio
async def test_acreate_video_to_motion():
    client = Client(API_KEY, staging=True)
    job_output = await client.acreate_video_to_motion(str(FIXTURES_DIR / "dance.mp4"))

    assert job_output.job_id
    assert job_output.status

    job_output = await _apoll_job(client, job_output.job_id)
    assert job_output.status == "FINISHED"

    motion_id = job_output.result["result"]["id"]
    assert motion_id

    ARTIFACTS_DIR.mkdir(exist_ok=True)
    data = await client.adownload_motion(
        DefaultCharacters.tar, motion_id, output_format="glb", fps=30,
    )
    (ARTIFACTS_DIR / "async_video_dance_30.glb").write_bytes(data)
