import os
from pathlib import Path

from uthana import Client

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_client_init():
    client = Client("test-key")
    assert client.base_url == "https://uthana.com"
    assert client.graphql_url == "https://uthana.com/graphql"


def test_client_staging():
    client = Client("test-key", staging=True)
    assert client.base_url == "https://staging.uthana.com"


ARTIFACTS_DIR = Path(__file__).parent / "artifacts"


def test_auto_rig_v1():
    api_key = os.environ.get("UTHANA_API_KEY")
    if not api_key:
        return

    client = Client(api_key, staging=True)
    output = client.auto_rig_v1(str(FIXTURES_DIR / "icegoblin.glb"))

    assert output.character_id
    assert output.url
    assert output.auto_rig_confidence < 1.0

    ARTIFACTS_DIR.mkdir(exist_ok=True)
    output.save(str(ARTIFACTS_DIR / "icegoblin_rigged.glb"))
