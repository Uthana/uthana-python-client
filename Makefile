.PHONY: install lint format typecheck precommit-install precommit test set-version release-publish-dry-run release-publish

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

set-version:
	@if [ -z "$(VERSION)" ]; then \
		echo "Usage: make set-version VERSION=MAJOR.MINOR.PATCH[-rc.N]"; \
		exit 1; \
	fi
	uv run python scripts/set_version.py "$(VERSION)"

release-publish-dry-run:
	uv run python scripts/release.py publish --dry-run

release-publish:
	uv run python scripts/release.py publish
