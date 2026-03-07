# (c) Copyright 2026 Uthana, Inc. All Rights Reserved
#
# Loads .env and .env.local before tests. .env.local overrides .env.
# Use UTHANA_API_KEY and UTHANA_DOMAIN for integration tests.

from pathlib import Path

from dotenv import load_dotenv

_root = Path(__file__).resolve().parent.parent
load_dotenv(_root / ".env")
load_dotenv(_root / ".env.local", override=True)
