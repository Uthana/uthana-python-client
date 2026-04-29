.PHONY: install lint format typecheck precommit-install precommit test release-prepare release-push release-verify release-publish-dry-run release-publish-testpypi-dry-run

install:
	uv sync

lint:
	uv run ruff check src scripts tests

format:
	uv run ruff format src scripts tests

typecheck:
	uv run mypy src scripts

precommit-install:
	.venv/bin/python -m pre_commit install

precommit:
	.venv/bin/python -m pre_commit run --all-files

test:
	uv run pytest

release-prepare:
	@if [ -z "$(VERSION)" ]; then \
		echo "Usage: make release-prepare VERSION=MAJOR.MINOR.PATCH[-rc.N]"; \
		exit 1; \
	fi
	uv run python scripts/release.py prepare --version "$(VERSION)"

release-push:
	uv run python scripts/release.py push

release-verify:
	uv run python scripts/release.py verify

release-publish-dry-run:
	uv run python scripts/release.py publish --dry-run

release-publish-testpypi-dry-run:
	uv run python scripts/release.py publish --dry-run --index testpypi
