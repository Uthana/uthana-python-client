# (c) Copyright 2026 Uthana, Inc. All Rights Reserved
#
# Loads .env and .env.local before tests. .env.local overrides .env.
# Use UTHANA_API_KEY and UTHANA_DOMAIN for integration tests.
# Uses pytest_configure so env is loaded before any test module is imported.

from pathlib import Path

from dotenv import load_dotenv


def pytest_configure(config):
    """Load .env files before collection so UTHANA_* are set when test_client is imported."""
    root = Path(__file__).resolve().parent.parent
    load_dotenv(root / ".env")
    load_dotenv(root / ".env.local", override=True)


def pytest_report_header(config):
    """Show in the pytest header whether UTHANA_API_KEY was loaded from .env."""
    import os

    key = os.environ.get("UTHANA_API_KEY", "")
    status = "yes" if key and key != "xxx" else "no"
    return f"UTHANA_API_KEY from .env: {status}"
