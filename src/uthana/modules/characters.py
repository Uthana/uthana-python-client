# (c) Copyright 2026 Uthana, Inc. All Rights Reserved

"""Character management: upload, list, download, generate previews, rename, and delete."""

from __future__ import annotations

import asyncio
import inspect
import json
import os
from typing import Callable, List, Optional, overload

import httpx

from ..graphql import q
from ..types import (
    DEFAULT_OUTPUT_FORMAT,
    Character,
    CharacterPreviewResult,
    CreateCharacterResult,
    CreateFromGeneratedImageResult,
    OutputFormat,
    UthanaError,
)
from ..utils import prepare_create_character
from ._base import _BaseModule


class CharactersModule(_BaseModule):
    """Character management: upload, list, download, generate previews, rename, and delete."""

    async def create_from_file(
        self,
        file: str,
        *,
        auto_rig: bool | None = None,
        front_facing: bool | None = None,
    ) -> CreateCharacterResult:
        """Upload a GLB or FBX and optionally auto-rig. Returns CreateCharacterResult."""
        if not file:
            raise UthanaError(400, "file is required (.glb or .fbx)")
        variables, name, ext, _ = prepare_create_character(file, auto_rig, front_facing)
        operations = json.dumps({"query": q.CREATE_CHARACTER, "variables": variables})
        map_data = json.dumps({"0": ["variables.file"]})
        with open(file, "rb") as f:
            async with httpx.AsyncClient(
                auth=(self._client._api_key, ""), timeout=self._client._timeout
            ) as http:
                response = await http.post(
                    self._client.graphql_url,
                    data={"operations": operations, "map": map_data},
                    files={"0": (f"{name}.{ext}", f, "application/octet-stream")},
                )
        result = self._client._check_response(response)
        return self._client._build_character_output(result=result, ext=ext)

    def create_from_file_sync(
        self,
        file: str,
        *,
        auto_rig: bool | None = None,
        front_facing: bool | None = None,
    ) -> CreateCharacterResult:
        """Upload a GLB or FBX and optionally auto-rig (sync)."""
        return asyncio.run(
            self.create_from_file(file, auto_rig=auto_rig, front_facing=front_facing)
        )

    @overload
    async def create_from_prompt(
        self,
        *,
        prompt: str,
        name: str | None = None,
        on_previews_ready: Callable,
    ) -> CreateFromGeneratedImageResult: ...

    @overload
    async def create_from_prompt(
        self,
        *,
        prompt: str,
        name: str | None = None,
        on_previews_ready: None = None,
    ) -> CharacterPreviewResult: ...

    async def create_from_prompt(
        self,
        *,
        prompt: str,
        name: str | None = None,
        on_previews_ready: Optional[Callable] = None,
    ) -> CharacterPreviewResult | CreateFromGeneratedImageResult:
        """Generate a character from a text prompt.

        Without on_previews_ready, returns CharacterPreviewResult; call generate_from_image to
        finalize. With on_previews_ready, the callback returns a preview key and this returns
        CreateFromGeneratedImageResult.
        """
        if not prompt:
            raise UthanaError(400, "prompt is required")
        data = await self._client._graphql(
            q.CREATE_IMAGE_FROM_TEXT,
            {"prompt": prompt},
            path="create_image_from_text",
        )
        data = data or {}
        character_id, images = data.get("character_id", ""), data.get("images") or []
        if on_previews_ready is None:
            return CharacterPreviewResult(character_id=character_id, previews=images, prompt=prompt)
        raw = on_previews_ready(images)
        key = (await raw) if inspect.iscoroutine(raw) else raw
        if not key:
            raise UthanaError(400, "No preview image selected")
        return await self._finalize_from_image(character_id, key, name, prompt=prompt)

    @overload
    def create_from_prompt_sync(
        self,
        *,
        prompt: str,
        name: str | None = None,
        on_previews_ready: Callable,
    ) -> CreateFromGeneratedImageResult: ...

    @overload
    def create_from_prompt_sync(
        self,
        *,
        prompt: str,
        name: str | None = None,
        on_previews_ready: None = None,
    ) -> CharacterPreviewResult: ...

    def create_from_prompt_sync(
        self,
        *,
        prompt: str,
        name: str | None = None,
        on_previews_ready: Optional[Callable] = None,
    ) -> CharacterPreviewResult | CreateFromGeneratedImageResult:
        """Generate a character from a text prompt (sync)."""
        if on_previews_ready is None:
            # PRAGMA: Need to branch to keep mypy from inferring asyncio.run(..., object).
            return asyncio.run(
                self.create_from_prompt(prompt=prompt, name=name, on_previews_ready=None)
            )
        return asyncio.run(
            self.create_from_prompt(prompt=prompt, name=name, on_previews_ready=on_previews_ready)
        )

    async def create_from_image(
        self,
        file: str,
        *,
        name: str | None = None,
    ) -> CreateFromGeneratedImageResult:
        """Upload a reference image (PNG/JPEG) and generate a character. One-shot step."""
        if not file:
            raise UthanaError(400, "file is required (.png, .jpg, .jpeg)")
        name_part = os.path.splitext(os.path.basename(file))[0]
        ext = os.path.splitext(file)[1].lstrip(".")
        operations = json.dumps({"query": q.CREATE_IMAGE_FROM_IMAGE, "variables": {"file": None}})
        map_data = json.dumps({"0": ["variables.file"]})
        with open(file, "rb") as f:
            async with httpx.AsyncClient(
                auth=(self._client._api_key, ""), timeout=self._client._timeout
            ) as http:
                response = await http.post(
                    self._client.graphql_url,
                    data={"operations": operations, "map": map_data},
                    files={"0": (f"{name_part}.{ext}", f, "application/octet-stream")},
                )
        result = self._client._check_response(response)
        gql_data = (result.get("data") or {}).get("create_image_from_image") or {}
        character_id = gql_data.get("character_id", "")
        image = gql_data.get("image") or {}
        return await self._finalize_from_image(character_id, image.get("key", ""), name)

    def create_from_image_sync(
        self,
        file: str,
        *,
        name: str | None = None,
    ) -> CreateFromGeneratedImageResult:
        """Upload a reference image and generate a character (sync)."""
        return asyncio.run(self.create_from_image(file, name=name))

    async def generate_from_image(
        self,
        pending: CharacterPreviewResult,
        image_key: str,
    ) -> CreateFromGeneratedImageResult:
        """Finalize a character from a previously generated preview (step 2 of the two-step flow).

        Use when create_from_prompt was called without on_previews_ready and returned a
        CharacterPreviewResult. Pick a key from pending.previews and pass it here.
        """
        return await self._finalize_from_image(
            pending.character_id, image_key, prompt=pending.prompt
        )

    def generate_from_image_sync(
        self,
        pending: CharacterPreviewResult,
        image_key: str,
    ) -> CreateFromGeneratedImageResult:
        """Finalize a character from a previously generated preview (sync)."""
        return asyncio.run(self.generate_from_image(pending, image_key))

    async def list(self) -> list[Character]:
        """List all characters for the authenticated user."""
        return await self._client._graphql(
            q.LIST_CHARACTERS,
            path="characters",
            path_default=[],
            return_type=list[Character],
        )

    def list_sync(self) -> List[Character]:
        """List all characters for the authenticated user (sync)."""
        return asyncio.run(self.list())

    async def download(
        self,
        character_id: str,
        *,
        output_format: OutputFormat = DEFAULT_OUTPUT_FORMAT,
    ) -> bytes:
        """Download a character model in the requested format."""
        ext = output_format.lower()
        url = f"{self._client.base_url}/motion/bundle/{character_id}/character.{ext}"
        async with httpx.AsyncClient(
            auth=(self._client._api_key, ""), timeout=self._client._timeout
        ) as http:
            response = await http.get(url)
        if not response.is_success:
            raise UthanaError(response.status_code, response.text)
        return response.content

    def download_sync(
        self,
        character_id: str,
        *,
        output_format: OutputFormat = DEFAULT_OUTPUT_FORMAT,
    ) -> bytes:
        """Download a character model in the requested format (sync)."""
        return asyncio.run(self.download(character_id, output_format=output_format))

    async def rename(self, character_id: str, name: str) -> Character:
        """Rename a character by ID."""
        return await self._client._graphql(
            q.RENAME_CHARACTER,
            {"character_id": character_id, "name": name},
            path="update_character.character",
            return_type=Character,
        )

    def rename_sync(self, character_id: str, name: str) -> Character:
        """Rename a character by ID (sync)."""
        return asyncio.run(self.rename(character_id, name))

    async def delete(self, character_id: str) -> Character:
        """Soft-delete a character by ID."""
        return await self._client._graphql(
            q.DELETE_CHARACTER,
            {"character_id": character_id},
            path="update_character.character",
            return_type=Character,
        )

    def delete_sync(self, character_id: str) -> Character:
        """Soft-delete a character by ID (sync)."""
        return asyncio.run(self.delete(character_id))

    # ---------------------------------------------------------------------------
    # Private helpers
    # ---------------------------------------------------------------------------

    async def _finalize_from_image(
        self,
        character_id: str,
        image_key: str,
        name: str | None = None,
        prompt: str = "",
    ) -> CreateFromGeneratedImageResult:
        """CREATE_CHARACTER_FROM_IMAGE — shared finalization step."""
        data = await self._client._graphql(
            q.CREATE_CHARACTER_FROM_IMAGE,
            {"character_id": character_id, "image_key": image_key, "prompt": prompt, "name": name},
            path="create_character_from_image",
        )
        data = data or {}
        return CreateFromGeneratedImageResult(
            character=data.get("character") or {},
            auto_rig_confidence=data.get("auto_rig_confidence"),
        )
