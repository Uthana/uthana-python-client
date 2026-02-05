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
def test_text_to_motion_v1_glb():
    client = Client(API_KEY, staging=True)
    output = client.text_to_motion_v1("a person walking forward", output_format="GLB", fps=30)

    assert output.url

    ARTIFACTS_DIR.mkdir(exist_ok=True)
    output.save(str(ARTIFACTS_DIR / "walking_forward_30.glb"))


@requires_api_key
def test_text_to_motion_v1_fbx():
    client = Client(API_KEY, staging=True)
    output = client.text_to_motion_v1("a person walking forward", output_format="FBX", fps=60)

    assert output.url

    ARTIFACTS_DIR.mkdir(exist_ok=True)
    output.save(str(ARTIFACTS_DIR / "walking_forward_60.fbx"))


@requires_api_key
def test_auto_rig_v1_glb():
    client = Client(API_KEY, staging=True)
    output = client.auto_rig_v1(str(FIXTURES_DIR / "icegoblin.glb"))

    assert output.character_id
    assert output.url
    assert output.auto_rig_confidence < 1.0

    ARTIFACTS_DIR.mkdir(exist_ok=True)
    output.save(str(ARTIFACTS_DIR / "icegoblin_rigged.glb"))


@requires_api_key
def test_auto_rig_v1_fbx():
    client = Client(API_KEY, staging=True)
    output = client.auto_rig_v1(str(FIXTURES_DIR / "wrestler.fbx"))

    assert output.character_id
    assert output.url
    assert output.auto_rig_confidence == 1.0

    ARTIFACTS_DIR.mkdir(exist_ok=True)
    output.save(str(ARTIFACTS_DIR / "wrestler_rigged.fbx"))
