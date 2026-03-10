# (c) Copyright 2026 Uthana, Inc. All Rights Reserved

"""Character management: upload, list, download, generate previews, and create from images."""

from __future__ import annotations

import asyncio
import inspect
import json
from typing import Callable, List, Optional

import httpx

from ..graphql import q
from ..types import (
    DEFAULT_OUTPUT_FORMAT,
    Character,
    CreateCharacterResult,
    CreateFromGeneratedImageResult,
    GenerateFromImageResult,
    GenerateFromTextResult,
    OutputFormat,
    UthanaError,
)
from ..utils import prepare_create_character
from ._base import _BaseModule


class CharactersModule(_BaseModule):
    """Character management: upload, list, download, generate previews, and create from images."""

    async def create(
        self,
        file_path: str,
        *,
        auto_rig: bool | None = None,
        front_facing: bool | None = None,
    ) -> CreateCharacterResult:
        """Upload and optionally auto-rig a 3D character model."""
        variables, name, ext, _ = prepare_create_character(file_path, auto_rig, front_facing)
        operations = json.dumps({"query": q.CREATE_CHARACTER, "variables": variables})
        map_data = json.dumps({"0": ["variables.file"]})

        with open(file_path, "rb") as f:
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

    def create_sync(
        self,
        file_path: str,
        *,
        auto_rig: bool | None = None,
        front_facing: bool | None = None,
    ) -> CreateCharacterResult:
        """Upload and optionally auto-rig a 3D character model (sync)."""
        return asyncio.run(self.create(file_path, auto_rig=auto_rig, front_facing=front_facing))

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

    async def generate_from_text(self, prompt: str) -> GenerateFromTextResult:
        """Generate character preview images from a text prompt. Returns character_id and images."""
        data = await self._client._graphql(
            q.CREATE_IMAGE_FROM_TEXT,
            {"prompt": prompt},
            path="create_image_from_text",
        )
        data = data or {}
        return GenerateFromTextResult(
            character_id=data.get("character_id", ""),
            images=data.get("images") or [],
        )

    def generate_from_text_sync(self, prompt: str) -> GenerateFromTextResult:
        """Generate character preview images from a text prompt (sync)."""
        return asyncio.run(self.generate_from_text(prompt))

    async def generate_from_image(self, file_path: str) -> GenerateFromImageResult:
        """Generate a character preview image from an uploaded image file."""
        import os

        name = os.path.splitext(os.path.basename(file_path))[0]
        ext = os.path.splitext(file_path)[1].lstrip(".")
        operations = json.dumps(
            {
                "query": q.CREATE_IMAGE_FROM_IMAGE,
                "variables": {"file": None},
            }
        )
        map_data = json.dumps({"0": ["variables.file"]})

        with open(file_path, "rb") as f:
            async with httpx.AsyncClient(
                auth=(self._client._api_key, ""), timeout=self._client._timeout
            ) as http:
                response = await http.post(
                    self._client.graphql_url,
                    data={"operations": operations, "map": map_data},
                    files={"0": (f"{name}.{ext}", f, "application/octet-stream")},
                )

        result = self._client._check_response(response)
        data = (result.get("data") or {}).get("create_image_from_image") or {}
        return GenerateFromImageResult(
            character_id=data.get("character_id", ""),
            image=data.get("image") or {},
        )

    def generate_from_image_sync(self, file_path: str) -> GenerateFromImageResult:
        """Generate a character preview image from an uploaded image file (sync)."""
        return asyncio.run(self.generate_from_image(file_path))

    async def create_from_generated_image(
        self,
        character_id: str,
        image_key: str,
        prompt: str,
        *,
        name: Optional[str] = None,
    ) -> CreateFromGeneratedImageResult:
        """Create a character from a previously generated image
        (from generate_from_text or generate_from_image)."""
        data = await self._client._graphql(
            q.CREATE_CHARACTER_FROM_IMAGE,
            {
                "character_id": character_id,
                "image_key": image_key,
                "prompt": prompt,
                "name": name,
            },
            path="create_character_from_image",
        )
        data = data or {}
        return CreateFromGeneratedImageResult(
            character=data.get("character") or {},
            auto_rig_confidence=data.get("auto_rig_confidence"),
        )

    def create_from_generated_image_sync(
        self,
        character_id: str,
        image_key: str,
        prompt: str,
        *,
        name: Optional[str] = None,
    ) -> CreateFromGeneratedImageResult:
        """Create a character from a previously generated image (sync)."""
        return asyncio.run(
            self.create_from_generated_image(character_id, image_key, prompt, name=name)
        )

    async def create_from_text(
        self,
        prompt: str,
        *,
        name: Optional[str] = None,
        on_previews_ready: Optional[Callable] = None,
    ) -> CreateFromGeneratedImageResult:
        """Create a character from a text prompt.

        Generates preview images, calls ``on_previews_ready(previews)`` to select
        one (defaults to first), then finalizes the character. ``on_previews_ready``
        may be a regular function or an async function.
        """
        result = await self.generate_from_text(prompt)
        if on_previews_ready is not None:
            raw = on_previews_ready(result.images)
            key = (await raw) if inspect.iscoroutine(raw) else raw
        else:
            key = result.images[0]["key"] if result.images else None
        if not key:
            raise UthanaError(400, "No preview image selected")
        return await self.create_from_generated_image(result.character_id, key, prompt, name=name)

    def create_from_text_sync(
        self,
        prompt: str,
        *,
        name: Optional[str] = None,
        on_previews_ready: Optional[Callable] = None,
    ) -> CreateFromGeneratedImageResult:
        """Create a character from a text prompt (sync)."""
        return asyncio.run(
            self.create_from_text(prompt, name=name, on_previews_ready=on_previews_ready)
        )

    async def create_from_image(
        self,
        file_path: str,
        *,
        prompt: str,
        name: Optional[str] = None,
        on_previews_ready: Optional[Callable] = None,
    ) -> CreateFromGeneratedImageResult:
        """Create a character from an image file.

        Generates a preview image, calls ``on_previews_ready([preview])`` to
        confirm (defaults to auto-confirming the single preview), then finalizes
        the character. ``on_previews_ready`` may be a regular or async function.
        """
        result = await self.generate_from_image(file_path)
        previews = [result.image]
        if on_previews_ready is not None:
            raw = on_previews_ready(previews)
            key = (await raw) if inspect.iscoroutine(raw) else raw
        else:
            key = result.image.get("key")
        if not key:
            raise UthanaError(400, "No preview image selected")
        return await self.create_from_generated_image(result.character_id, key, prompt, name=name)

    def create_from_image_sync(
        self,
        file_path: str,
        *,
        prompt: str,
        name: Optional[str] = None,
        on_previews_ready: Optional[Callable] = None,
    ) -> CreateFromGeneratedImageResult:
        """Create a character from an image file (sync)."""
        return asyncio.run(
            self.create_from_image(
                file_path, prompt=prompt, name=name, on_previews_ready=on_previews_ready
            )
        )
