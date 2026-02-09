import os
from pathlib import Path

import pytest

from uthana import Client

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
    output = client.create_text_to_motion_v1("a person walking forward", output_format="GLB", fps=30)

    assert output.url


@requires_api_key
def test_create_text_to_motion_v1_fbx():
    client = Client(API_KEY, staging=True)
    output = client.create_text_to_motion_v1("a person walking forward", output_format="FBX", fps=60)

    assert output.url


@requires_api_key
def test_create_character_glb():
    client = Client(API_KEY, staging=True)
    output = client.create_character(str(FIXTURES_DIR / "icegoblin.glb"))

    assert output.character_id
    assert output.url
    assert output.auto_rig_confidence < 1.0

    ARTIFACTS_DIR.mkdir(exist_ok=True)
    data = client.download_character(output.character_id, output_format="GLB")
    (ARTIFACTS_DIR / "icegoblin_rigged.glb").write_bytes(data)


@requires_api_key
def test_create_character_fbx():
    client = Client(API_KEY, staging=True)
    output = client.create_character(str(FIXTURES_DIR / "wrestler.fbx"))

    assert output.character_id
    assert output.url
    assert output.auto_rig_confidence >= 0.7

    ARTIFACTS_DIR.mkdir(exist_ok=True)
    data = client.download_character(output.character_id, output_format="FBX")
    (ARTIFACTS_DIR / "wrestler_rigged.fbx").write_bytes(data)


# Async tests


@requires_api_key
@pytest.mark.asyncio
async def test_acreate_text_to_motion_v1_glb():
    client = Client(API_KEY, staging=True)
    output = await client.acreate_text_to_motion_v1("a person walking forward", output_format="GLB", fps=30)

    assert output.url


@requires_api_key
@pytest.mark.asyncio
async def test_acreate_text_to_motion_v1_fbx():
    client = Client(API_KEY, staging=True)
    output = await client.acreate_text_to_motion_v1("a person walking forward", output_format="FBX", fps=60)

    assert output.url


@requires_api_key
@pytest.mark.asyncio
async def test_acreate_text_to_motion_v2_glb():
    client = Client(API_KEY, staging=True)
    output = await client.acreate_text_to_motion_v2("a person dancing", output_format="GLB", fps=30)

    assert output.url


@requires_api_key
@pytest.mark.asyncio
async def test_acreate_character_glb():
    client = Client(API_KEY, staging=True)
    output = await client.acreate_character(str(FIXTURES_DIR / "icegoblin.glb"))

    assert output.character_id
    assert output.url
    assert output.auto_rig_confidence < 1.0

    ARTIFACTS_DIR.mkdir(exist_ok=True)
    data = await client.adownload_character(output.character_id, output_format="GLB")
    (ARTIFACTS_DIR / "async_icegoblin_rigged.glb").write_bytes(data)


@requires_api_key
@pytest.mark.asyncio
async def test_acreate_character_fbx():
    client = Client(API_KEY, staging=True)
    output = await client.acreate_character(str(FIXTURES_DIR / "wrestler.fbx"))

    assert output.character_id
    assert output.url
    assert output.auto_rig_confidence >= 0.7

    ARTIFACTS_DIR.mkdir(exist_ok=True)
    data = await client.adownload_character(output.character_id, output_format="FBX")
    (ARTIFACTS_DIR / "async_wrestler_rigged.fbx").write_bytes(data)
