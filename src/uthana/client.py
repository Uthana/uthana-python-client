# (c) Copyright 2026 Uthana, Inc. All Rights Reserved

from __future__ import annotations

import uuid
from importlib.metadata import version as _pkg_version

import httpx

from .graphql import TEXT_TO_MOTION_DIFFUSION_V2, TEXT_TO_MOTION_VQVAE_V1
from .models import get_default_ttm_model
from .modules import (
    CharactersModule,
    JobsModule,
    MotionsModule,
    OrgModule,
    TTMModule,
    VTMModule,
)
from .types import (
    CharacterOutput,
    DEFAULT_TIMEOUT,
    ModelType,
    OutputFormat,
    UthanaError,
)


class Uthana:
    """Main client for the Uthana API. Use modules for organized access:

    - ttm: text to motion
    - vtm: video to motion
    - characters: character management
    - motions: motion management
    - org: user and organization info
    - jobs: async job polling
    """

    def __init__(
        self,
        api_key: str,
        *,
        domain: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        """Create an Uthana client.

        Args:
            api_key: Your Uthana API key from account settings.
            domain: API host (e.g. "uthana.com"). Defaults to production when omitted.
            timeout: Request timeout in seconds.
        """
        domain = domain or "uthana.com"
        self.base_url = f"https://{domain}"
        self.graphql_url = f"{self.base_url}/graphql"
        self.session = httpx.Client(auth=(api_key, ""), timeout=timeout)
        self.async_client = httpx.AsyncClient(auth=(api_key, ""), timeout=timeout)
        self._log_init()

        self.ttm = TTMModule(self)
        self.vtm = VTMModule(self)
        self.characters = CharactersModule(self)
        self.motions = MotionsModule(self)
        self.org = OrgModule(self)
        self.jobs = JobsModule(self)

    def _log_init(self) -> dict:
        """Log client initialization to Uthana analytics."""
        app = "uthana-python"
        version = _pkg_version("uthana")
        headers = {"User-Agent": f"{app}/{version}"}
        r = self.session.post(
            self.graphql_url, json={"query": "{user{id}}"}, headers=headers
        )
        r.raise_for_status()
        data = r.json().get("data") or {}
        user = data.get("user") or {}
        uid = user.get("id") if isinstance(user, dict) else None

        anon_id = "00000000" + str(uuid.uuid1(clock_seq=1))[8:]

        evt = {
            "type": "track",
            "event": "initialized",
            "app": app,
            "userId": uid,
            "anonymousId": anon_id,
            "meta": {},
        }

        r = self.session.post(f"{self.base_url}/event", json=evt, headers=headers)
        r.raise_for_status()
        return r.json()

    def _graphql_sync(self, query: str, variables: dict | None = None) -> dict:
        """Execute a GraphQL query (sync)."""
        response = self.session.post(
            self.graphql_url,
            json={"query": query, "variables": variables or {}},
        )
        if not response.is_success:
            raise UthanaError(response.status_code, response.text)
        result = response.json()
        if "errors" in result:
            raise UthanaError(400, f"GraphQL errors: {result['errors']}")
        return result.get("data", {})

    async def _graphql(self, query: str, variables: dict | None = None) -> dict:
        """Execute a GraphQL query (async)."""
        response = await self.async_client.post(
            self.graphql_url,
            json={"query": query, "variables": variables or {}},
        )
        if not response.is_success:
            raise UthanaError(response.status_code, response.text)
        result = response.json()
        if "errors" in result:
            raise UthanaError(400, f"GraphQL errors: {result['errors']}")
        return result.get("data", {})

    def _check_response(self, response: httpx.Response) -> dict:
        """Validate response and raise UthanaError on failure."""
        if not response.is_success:
            raise UthanaError(response.status_code, response.text)
        result = response.json()
        if "errors" in result:
            raise UthanaError(400, f"GraphQL errors: {result['errors']}")
        return result

    def _motion_url(
        self,
        *,
        character_id: str,
        motion_id: str,
        output_format: OutputFormat,
        fps: int | None,
        no_mesh: bool | None,
    ) -> str:
        """Build the download URL for a motion file."""
        ext = output_format.lower()
        url = f"{self.base_url}/motion/file/motion_viewer/{character_id}/{motion_id}/{ext}/{character_id}-{motion_id}.{ext}"
        options = []
        if fps is not None:
            options.append(f"fps={fps}")
        if no_mesh is not None:
            options.append(f"no_mesh={'true' if no_mesh else 'false'}")
        if options:
            url += f"?{'&'.join(options)}"
        return url

    def _build_character_output(self, *, result: dict, ext: str) -> CharacterOutput:
        """Parse create_character response into CharacterOutput."""
        character = result["data"]["create_character"]["character"]
        character_id = character["id"]
        auto_rig_confidence = result["data"]["create_character"].get(
            "auto_rig_confidence"
        )

        url = f"{self.base_url}/motion/bundle/{character_id}/character.{ext}"
        return CharacterOutput(
            url=url,
            character_id=character_id,
            auto_rig_confidence=auto_rig_confidence,
        )

    @staticmethod
    def _prepare_text_to_motion_vqvae_v1(
        *,
        prompt: str,
        character_id: str | None,
        foot_ik: bool | None,
    ) -> dict:
        """Build variables for vqvae-v1 text-to-motion mutation."""
        return {
            "prompt": prompt,
            "character_id": character_id,
            "model": "text-to-motion",
            "foot_ik": foot_ik,
        }

    @staticmethod
    def _prepare_text_to_motion_diffusion_v2(
        *,
        prompt: str,
        character_id: str | None,
        foot_ik: bool | None,
        cfg_scale: float | None,
        length: float | None,
        seed: int | None,
        internal_ik: bool | None,
    ) -> dict:
        """Build variables for diffusion-v2 text-to-motion mutation."""
        return {
            "prompt": prompt,
            "character_id": character_id,
            "model": "text-to-motion-bucmd",
            "foot_ik": foot_ik,
            "cfg_scale": cfg_scale,
            "length": length,
            "seed": seed,
            "retargeting_ik": internal_ik,
        }

    def _prepare_and_select_text_to_motion(
        self,
        *,
        model: ModelType,
        prompt: str,
        character_id: str | None,
        foot_ik: bool | None,
        length: float | None,
        cfg_scale: float | None,
        seed: int | None,
        internal_ik: bool | None,
    ) -> tuple[str, dict]:
        """Resolve model, build variables, and return mutation + variables for TTM."""
        if model == "auto":
            model = get_default_ttm_model()
        if model == "vqvae-v1":
            variables = self._prepare_text_to_motion_vqvae_v1(
                prompt=prompt, character_id=character_id, foot_ik=foot_ik
            )
            return TEXT_TO_MOTION_VQVAE_V1, variables
        elif model == "diffusion-v2":
            variables = self._prepare_text_to_motion_diffusion_v2(
                prompt=prompt,
                character_id=character_id,
                foot_ik=foot_ik,
                cfg_scale=cfg_scale,
                length=length,
                seed=seed,
                internal_ik=internal_ik,
            )
            return TEXT_TO_MOTION_DIFFUSION_V2, variables
        else:
            raise ValueError(
                f"Unknown model: {model!r}. Must be 'auto', 'vqvae-v1', or 'diffusion-v2'."
            )


# Backwards compatibility alias
Client = Uthana
