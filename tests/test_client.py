# (c) Copyright 2026 Uthana, Inc. All Rights Reserved

import asyncio
import os
import time
from pathlib import Path

import pytest

from uthana import Job, Uthana, UthanaCharacters

FIXTURES_DIR = Path(__file__).parent / "fixtures"
ARTIFACTS_DIR = Path(__file__).parent / "artifacts"

API_KEY = os.environ.get("UTHANA_API_KEY", "")
requires_api_key = pytest.mark.skipif(
    not API_KEY or API_KEY == "xxx", reason="UTHANA_API_KEY not set"
)

USE_DOMAIN = os.environ.get("UTHANA_DOMAIN")  # e.g. set for non-production


@pytest.fixture(scope="module")
def client() -> Uthana:
    if not API_KEY or API_KEY == "xxx":
        pytest.skip("UTHANA_API_KEY not set")
    return Uthana(API_KEY, domain=USE_DOMAIN)


@pytest.mark.smoke
@requires_api_key
def test_create_text_to_motion_vqvae_v1_glb(client: Uthana) -> None:
    output = client.ttm.create_sync("a person walking forward", model="vqvae-v1")

    assert output.character_id
    assert output.motion_id

    ARTIFACTS_DIR.mkdir(exist_ok=True)
    data = client.motions.download_sync(
        output.character_id, output.motion_id, output_format="glb", fps=30
    )
    (ARTIFACTS_DIR / "vqvae_v1_walk_30.glb").write_bytes(data)


@requires_api_key
def test_create_text_to_motion_vqvae_v1_fbx(client: Uthana) -> None:
    output = client.ttm.create_sync("a person walking forward", model="vqvae-v1")

    assert output.character_id
    assert output.motion_id

    ARTIFACTS_DIR.mkdir(exist_ok=True)
    data = client.motions.download_sync(
        output.character_id, output.motion_id, output_format="fbx", fps=60
    )
    (ARTIFACTS_DIR / "vqvae_v1_walk_60.fbx").write_bytes(data)


@requires_api_key
def test_create_character_glb(client: Uthana) -> None:
    output = client.characters.create_sync(str(FIXTURES_DIR / "pig.glb"))

    assert output.character_id
    assert output.url
    assert output.auto_rig_confidence is not None and output.auto_rig_confidence < 0.5

    ARTIFACTS_DIR.mkdir(exist_ok=True)
    data = client.characters.download_sync(output.character_id, output_format="glb")
    (ARTIFACTS_DIR / "pig_rigged.glb").write_bytes(data)


@pytest.mark.smoke
@requires_api_key
def test_create_character_fbx(client: Uthana) -> None:
    output = client.characters.create_sync(str(FIXTURES_DIR / "wrestler.fbx"))

    assert output.character_id
    assert output.url
    assert output.auto_rig_confidence is not None and output.auto_rig_confidence > 0.5

    ARTIFACTS_DIR.mkdir(exist_ok=True)
    data = client.characters.download_sync(output.character_id, output_format="fbx")
    (ARTIFACTS_DIR / "wrestler_rigged.fbx").write_bytes(data)


# Async tests


@requires_api_key
@pytest.mark.asyncio
async def test_create_text_to_motion_vqvae_v1_glb_async(client: Uthana) -> None:
    output = await client.ttm.create("a person walking forward", model="vqvae-v1")

    assert output.character_id
    assert output.motion_id

    ARTIFACTS_DIR.mkdir(exist_ok=True)
    data = await client.motions.download(
        output.character_id, output.motion_id, output_format="glb", fps=30
    )
    (ARTIFACTS_DIR / "async_vqvae_v1_walk_30.glb").write_bytes(data)


@requires_api_key
@pytest.mark.asyncio
async def test_create_text_to_motion_vqvae_v1_fbx_async(client: Uthana) -> None:
    output = await client.ttm.create("a person walking forward", model="vqvae-v1")

    assert output.character_id
    assert output.motion_id

    ARTIFACTS_DIR.mkdir(exist_ok=True)
    data = await client.motions.download(
        output.character_id, output.motion_id, output_format="fbx", fps=60
    )
    (ARTIFACTS_DIR / "async_vqvae_v1_walk_60.fbx").write_bytes(data)


@pytest.mark.smoke
@requires_api_key
@pytest.mark.asyncio
async def test_create_text_to_motion_diffusion_v2_glb_async(client: Uthana) -> None:
    output = await client.ttm.create("a person dancing", model="diffusion-v2")

    assert output.character_id
    assert output.motion_id

    ARTIFACTS_DIR.mkdir(exist_ok=True)
    data = await client.motions.download(
        output.character_id, output.motion_id, output_format="glb", fps=30
    )
    (ARTIFACTS_DIR / "async_dancing_30.glb").write_bytes(data)


@requires_api_key
@pytest.mark.asyncio
async def test_create_character_glb_async(client: Uthana) -> None:
    output = await client.characters.create(str(FIXTURES_DIR / "pig.glb"))

    assert output.character_id
    assert output.url
    assert output.auto_rig_confidence is not None and output.auto_rig_confidence < 0.5

    ARTIFACTS_DIR.mkdir(exist_ok=True)
    data = await client.characters.download(output.character_id, output_format="glb")
    (ARTIFACTS_DIR / "async_pig_rigged.glb").write_bytes(data)


@requires_api_key
@pytest.mark.asyncio
async def test_create_character_fbx_async(client: Uthana) -> None:
    output = await client.characters.create(str(FIXTURES_DIR / "wrestler.fbx"))

    assert output.character_id
    assert output.url
    assert output.auto_rig_confidence is not None and output.auto_rig_confidence > 0.5

    ARTIFACTS_DIR.mkdir(exist_ok=True)
    data = await client.characters.download(output.character_id, output_format="fbx")
    (ARTIFACTS_DIR / "async_wrestler_rigged.fbx").write_bytes(data)


def _poll_job(client: Uthana, job_id: str, timeout: float = 300.0, interval: float = 2.0) -> Job:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = client.jobs.get_sync(job_id)
        if job["status"] in ("FINISHED", "FAILED"):
            return job
        time.sleep(interval)
    raise TimeoutError(f"Job {job_id} did not complete within {timeout}s")


async def _apoll_job(
    client: Uthana, job_id: str, timeout: float = 300.0, interval: float = 2.0
) -> Job:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = await client.jobs.get(job_id)
        if job["status"] in ("FINISHED", "FAILED"):
            return job
        await asyncio.sleep(interval)
    raise TimeoutError(f"Job {job_id} did not complete within {timeout}s")


@requires_api_key
@pytest.mark.timeout(300)
def test_create_video_to_motion(client: Uthana) -> None:
    job_output = client.vtm.create_sync(str(FIXTURES_DIR / "dance.mp4"))

    assert job_output["id"]
    assert job_output["status"]

    job_output = _poll_job(client, job_output["id"])
    assert job_output["status"] == "FINISHED"

    result = job_output.get("result")
    assert result is not None
    motion_id = result["result"]["id"]
    assert motion_id

    ARTIFACTS_DIR.mkdir(exist_ok=True)
    data = client.motions.download_sync(
        UthanaCharacters.tar, motion_id, output_format="glb", fps=30
    )
    (ARTIFACTS_DIR / "video_dance_30.glb").write_bytes(data)


@requires_api_key
@pytest.mark.asyncio
@pytest.mark.timeout(300)
async def test_create_video_to_motion_async(client: Uthana) -> None:
    job_output = await client.vtm.create(str(FIXTURES_DIR / "dance.mp4"))

    assert job_output["id"]
    assert job_output["status"]

    job_output = await _apoll_job(client, job_output["id"])
    assert job_output["status"] == "FINISHED"

    result = job_output.get("result")
    assert result is not None
    motion_id = result["result"]["id"]
    assert motion_id

    ARTIFACTS_DIR.mkdir(exist_ok=True)
    data = await client.motions.download(
        UthanaCharacters.tar, motion_id, output_format="glb", fps=30
    )
    (ARTIFACTS_DIR / "async_video_dance_30.glb").write_bytes(data)


@requires_api_key
def test_org_get_user(client: Uthana) -> None:
    user = client.org.get_user_sync()
    assert user.get("id")
    assert user.get("name") is not None or user.get("email") is not None


@requires_api_key
def test_org_get_org(client: Uthana) -> None:
    org = client.org.get_org_sync()
    assert org.get("id")
    assert org.get("name") is not None or org.get("motion_download_secs_per_month") is not None


@requires_api_key
def test_characters_list(client: Uthana) -> None:
    characters = client.characters.list_sync()
    assert isinstance(characters, list)
    for c in characters:
        assert c.get("id")
        assert "name" in c or "id" in c


@requires_api_key
def test_motions_list(client: Uthana) -> None:
    motions = client.motions.list_sync()
    assert isinstance(motions, list)
    for m in motions:
        assert m.get("id")
        assert "name" in m or "id" in m


@requires_api_key
def test_jobs_list(client: Uthana) -> None:
    jobs = client.jobs.list_sync()
    assert isinstance(jobs, list)
    for j in jobs:
        assert j.get("id")
        assert j.get("status")


@requires_api_key
def test_jobs_list_filtered_by_method(client: Uthana) -> None:
    jobs = client.jobs.list_sync(method="VideoToMotion")
    assert isinstance(jobs, list)
    for j in jobs:
        assert j.get("id")
        assert j.get("method") == "VideoToMotion"
