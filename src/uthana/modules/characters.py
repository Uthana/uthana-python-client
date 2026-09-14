# (c) Copyright 2026 Uthana, Inc. All Rights Reserved

"""Character management: upload, list, download, generate previews, rename, and delete."""

from __future__ import annotations

import asyncio
import inspect
import json
import os
from typing import BinaryIO, Callable, List, Optional, overload
from urllib.parse import quote

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
from ..utils import _validate_upload_limit, prepare_create_character
from ._base import _BaseModule


class CharactersModule(_BaseModule):
    """Character management: upload, list, download, generate previews, rename, and delete."""

    async def create_from_file(
        self,
        file: str,
        *,
        auto_rig: bool | None = None,
        front_facing: bool | None = None,
        rerig_target: str | None = None,
        include_fingers: bool | None = None,
        name: str | None = None,
        timeout: float | httpx.Timeout | None = None,
        max_bytes: int | None = None,
    ) -> CreateCharacterResult:
        """Upload a GLB or FBX and optionally auto-rig.

        Streams the source without an input-size limit by default and preserves
        the client's configured timeout. An explicit ``max_bytes`` instead reads a
        bounded snapshot. Set ``timeout`` to override this request's timeout.
        """
        if not file:
            raise UthanaError(400, "file is required (.glb or .fbx)")
        _validate_upload_limit(max_bytes)
        variables, source_name, ext, _ = prepare_create_character(
            file, auto_rig, front_facing, rerig_target, include_fingers
        )
        if name is not None:
            variables["name"] = name
        with open(file, "rb") as source:
            if max_bytes is None:
                data = await self._client._graphql(
                    q.CREATE_CHARACTER,
                    variables,
                    upload=(f"{source_name}.{ext}", source),
                    timeout=timeout,
                )
                return self._client._build_character_output(result={"data": data}, ext=ext)
            content = source.read(max_bytes + 1)
        return await self.create_from_bytes(
            f"{source_name}.{ext}",
            content,
            name=source_name if name is None else name,
            auto_rig=auto_rig,
            front_facing=front_facing,
            rerig_target=rerig_target,
            include_fingers=include_fingers,
            timeout=self._client._timeout if timeout is None else timeout,
            max_bytes=max_bytes,
        )

    def create_from_file_sync(
        self,
        file: str,
        *,
        auto_rig: bool | None = None,
        front_facing: bool | None = None,
        rerig_target: str | None = None,
        include_fingers: bool | None = None,
        name: str | None = None,
        timeout: float | httpx.Timeout | None = None,
        max_bytes: int | None = None,
    ) -> CreateCharacterResult:
        """Upload a GLB or FBX and optionally auto-rig (sync)."""
        return asyncio.run(
            self.create_from_file(
                file,
                auto_rig=auto_rig,
                front_facing=front_facing,
                rerig_target=rerig_target,
                include_fingers=include_fingers,
                name=name,
                timeout=timeout,
                max_bytes=max_bytes,
            )
        )

    async def create_from_bytes(
        self,
        filename: str,
        content: bytes,
        *,
        name: str | None = None,
        auto_rig: bool | None = None,
        front_facing: bool | None = None,
        rerig_target: str | None = None,
        include_fingers: bool | None = None,
        timeout: float | httpx.Timeout = httpx.Timeout(360, connect=15),
        max_bytes: int | None = 128 * 1024 * 1024,
    ) -> CreateCharacterResult:
        """Upload an existing byte snapshot without reopening its source file.

        ``filename`` supplies the format and default name; an explicit ``name`` is
        preserved exactly. Returns backend compatibility warnings in ``message``.
        The default timeout includes the backend's synchronous character processing.
        """
        _validate_upload_limit(max_bytes)
        if not isinstance(content, bytes) or not content:
            raise ValueError("Character upload content must be nonempty bytes")
        if max_bytes is not None and len(content) > max_bytes:
            raise ValueError("Character upload exceeds max_bytes")
        filename = os.path.basename(filename)
        stem, extension = os.path.splitext(filename)
        ext = extension.lstrip(".").lower()
        if ext not in ("glb", "fbx"):
            raise ValueError("Character filename must use .glb or .fbx")
        variables = {
            "file": None,
            "name": stem if name is None else name,
            "auto_rig": auto_rig,
            "auto_rig_front_facing": front_facing,
            "rerig_target": rerig_target,
            "include_fingers": include_fingers,
        }
        data = await self._client._graphql(
            q.CREATE_CHARACTER,
            variables,
            upload=(filename, content),
            timeout=timeout,
        )
        return self._client._build_character_output(result={"data": data}, ext=ext)

    def create_from_bytes_sync(
        self,
        filename: str,
        content: bytes,
        *,
        name: str | None = None,
        auto_rig: bool | None = None,
        front_facing: bool | None = None,
        rerig_target: str | None = None,
        include_fingers: bool | None = None,
        timeout: float | httpx.Timeout = httpx.Timeout(360, connect=15),
        max_bytes: int | None = 128 * 1024 * 1024,
    ) -> CreateCharacterResult:
        """Upload a character byte snapshot (sync)."""
        return asyncio.run(
            self.create_from_bytes(
                filename,
                content,
                name=name,
                auto_rig=auto_rig,
                front_facing=front_facing,
                rerig_target=rerig_target,
                include_fingers=include_fingers,
                timeout=timeout,
                max_bytes=max_bytes,
            )
        )

    async def metadata(self, character_id: str, *, max_bytes: int | None = None) -> dict:
        """Get character rig metadata used to validate character-specific edits."""
        url = f"{self._client.base_url}/motion/metadata/{quote(character_id, safe='')}"
        data = await self._client._request_bytes("GET", url, max_bytes=max_bytes)
        try:
            result = json.loads(data)
        except (ValueError, UnicodeDecodeError):
            raise UthanaError(
                502, "Invalid character metadata response", kind="invalid_response"
            ) from None
        if not isinstance(result, dict):
            raise UthanaError(502, "Invalid character metadata response", kind="invalid_response")
        return result

    def metadata_sync(self, character_id: str, *, max_bytes: int | None = None) -> dict:
        """Get character rig metadata (sync)."""
        return asyncio.run(self.metadata(character_id, max_bytes=max_bytes))

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
        max_bytes: int | None = None,
    ) -> CreateFromGeneratedImageResult:
        """Upload a reference image (PNG/JPEG) and generate a character in one step.

        Streams the source without an input-size limit by default. An explicit
        ``max_bytes`` reads a bounded snapshot instead.
        """
        if not file:
            raise UthanaError(400, "file is required (.png, .jpg, .jpeg)")
        _validate_upload_limit(max_bytes)
        with open(file, "rb") as source:
            upload_content: bytes | BinaryIO = source
            if max_bytes is not None:
                content = source.read(max_bytes + 1)
                if not content or len(content) > max_bytes:
                    raise ValueError("Image upload must be nonempty and fit max_bytes")
                upload_content = content
            data = await self._client._graphql(
                q.CREATE_IMAGE_FROM_IMAGE,
                {"file": None},
                upload=(os.path.basename(file), upload_content),
                path="create_image_from_image",
            )
        character_id = data.get("character_id", "")
        image = data.get("image") or {}
        return await self._finalize_from_image(character_id, image.get("key", ""), name)

    def create_from_image_sync(
        self,
        file: str,
        *,
        name: str | None = None,
        max_bytes: int | None = None,
    ) -> CreateFromGeneratedImageResult:
        """Upload a reference image and generate a character (sync)."""
        return asyncio.run(self.create_from_image(file, name=name, max_bytes=max_bytes))

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
        max_bytes: int | None = None,
    ) -> bytes:
        """Download a character model in the requested format, optionally size bounded."""
        ext = output_format.lower()
        url = (
            f"{self._client.base_url}/motion/bundle/{quote(character_id, safe='')}/character.{ext}"
        )
        return await self._client._request_bytes("GET", url, max_bytes=max_bytes)

    def download_sync(
        self,
        character_id: str,
        *,
        output_format: OutputFormat = DEFAULT_OUTPUT_FORMAT,
        max_bytes: int | None = None,
    ) -> bytes:
        """Download a character model in the requested format (sync)."""
        return asyncio.run(
            self.download(character_id, output_format=output_format, max_bytes=max_bytes)
        )

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
