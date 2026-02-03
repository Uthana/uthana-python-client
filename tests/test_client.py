from uthana import Client


def test_client_init():
    client = Client("test-key")
    assert client.base_url == "https://uthana.com"
    assert client.graphql_url == "https://uthana.com/graphql"


def test_client_staging():
    client = Client("test-key", staging=True)
    assert client.base_url == "https://staging.uthana.com"
