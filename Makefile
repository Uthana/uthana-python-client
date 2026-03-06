.PHONY: install lint format typecheck precommit-install precommit test release-prepare

install:
	uv sync

lint:
	uv run ruff check src scripts tests

format:
	uv run ruff format src scripts tests

typecheck:
	uv run mypy src scripts

precommit-install:
	uv run pre-commit install

precommit:
	uv run pre-commit run --all-files

test:
	uv run pytest

release-prepare:
	@if [ -z "$(VERSION)" ]; then \
		echo "Usage: make release-prepare VERSION=MAJOR.MINOR.PATCH[-rc.N]"; \
		exit 1; \
	fi
	uv run python scripts/release.py prepare --version "$(VERSION)"
