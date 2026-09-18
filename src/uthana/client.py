# (c) Copyright 2026 Uthana, Inc. All Rights Reserved

from __future__ import annotations

import json
import re
import uuid
from importlib.metadata import version as _pkg_version
from typing import BinaryIO, TypeVar, cast, overload

import httpx

from .graphql import q
from .models import models
from .modules import (
    CharactersModule,
    JobsModule,
    MotionsModule,
    OrgModule,
    TtmModule,
    VtmModule,
)
from .types import (
    DEFAULT_TIMEOUT,
    CreateCharacterResult,
    ModelType,
    OutputFormat,
    UthanaError,
)

_T = TypeVar("_T")


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
        timeout: float | httpx.Timeout = DEFAULT_TIMEOUT,
        telemetry: bool = True,
        transport: httpx.AsyncBaseTransport | None = None,
        trust_env: bool = True,
        max_response_bytes: int | None = None,
        max_mutation_response_bytes: int | None = None,
    ) -> None:
        """Create an Uthana client.

        Args:
            api_key: Your Uthana API key from account settings.
            domain: API host (e.g. "uthana.com"). Defaults to production when omitted.
            timeout: Request timeout in seconds or an HTTPX timeout configuration.
            telemetry: Log initialization when true; false avoids constructor network calls.
            transport: Optional transport for async API requests, including offline tests.
            trust_env: Honor HTTP proxy and certificate environment variables when true.
            max_response_bytes: Maximum decoded GraphQL query response size; None is unlimited.
            max_mutation_response_bytes: Optional separate mutation response limit. Exceeding
                it raises kind="uncertain": the operation may have succeeded; do not resubmit
                without reconciling the result. Mutations are unlimited by default.
        """
        domain = domain or "uthana.com"
        self.base_url = f"https://{domain}"
        self.graphql_url = f"{self.base_url}/graphql"
        self._api_key = api_key
        self._timeout = timeout
        self._transport = transport
        self._trust_env = trust_env
        self._validate_response_limit(max_response_bytes)
        self._validate_response_limit(max_mutation_response_bytes)
        self._max_response_bytes = max_response_bytes
        self._max_mutation_response_bytes = max_mutation_response_bytes
        self.session = httpx.Client(
            auth=(api_key, ""), timeout=timeout, trust_env=trust_env, follow_redirects=False
        )
        if telemetry:
            self._log_init()

        self.ttm = TtmModule(self)
        self.vtm = VtmModule(self)
        self.characters = CharactersModule(self)
        self.motions = MotionsModule(self)
        self.org = OrgModule(self)
        self.jobs = JobsModule(self)

    def _log_init(self) -> dict:
        """Log client initialization to Uthana analytics."""
        app = "uthana-python"
        version = _pkg_version("uthana")
        headers = {"User-Agent": f"{app}/{version}"}
        r = self.session.post(self.graphql_url, json={"query": "{user{id}}"}, headers=headers)
        r.raise_for_status()
        data = r.json().get("data") or {}
        user = data.get("user") or {}
        uid = user.get("id") if isinstance(user, dict) else None

        anon_id = "00000000" + str(uuid.uuid1(clock_seq=1))[8:]

        evt: dict[str, str | None | dict[str, str]] = {
            "type": "track",
            "event": "initialized",
            "app": app,
            "userId": uid,
            "anonymousId": anon_id,
            "meta": {},
        }

        r = self.session.post(f"{self.base_url}/event", json=evt, headers=headers)
        r.raise_for_status()
        return cast(dict, r.json())

    def close(self) -> None:
        """Close the synchronous session owned by this client."""
        self.session.close()

    @staticmethod
    def _validate_response_limit(value: int | None) -> None:
        if value is not None and (type(value) is not int or value < 1):
            raise ValueError("Response byte limits must be positive integers or None")

    @staticmethod
    def _error_response_data(body: bytes) -> dict | None:
        try:
            result = json.loads(body)
        except (ValueError, UnicodeDecodeError):
            return None
        return result if isinstance(result, dict) else None

    async def _request_bytes(
        self,
        method: str,
        url: str,
        *,
        max_bytes: int | None = None,
        mutating: bool = False,
        **kwargs,
    ) -> bytes:
        """Read a response with optional decoded-byte bounds and no automatic retries.

        A fresh client per call remains safe across sequential event loops. HTTPX transport
        failures are preserved so callers can distinguish connection failures from ambiguous
        failures after a write. Redirects are never followed, including for authenticated URLs.
        """
        self._validate_response_limit(max_bytes)
        async with httpx.AsyncClient(
            auth=(self._api_key, ""),
            timeout=self._timeout,
            transport=self._transport,
            trust_env=self._trust_env,
            follow_redirects=False,
        ) as client:
            async with client.stream(method, url, follow_redirects=False, **kwargs) as response:
                body = bytearray()
                # Retain the known HTTP status even if an error page is enormous. Successful
                # response limits are strict; error descriptions are bounded and may truncate.
                error_limit = min(max_bytes, 65536) if max_bytes is not None else 65536
                async for part in response.aiter_bytes(chunk_size=65536):
                    if not response.is_success:
                        body.extend(part[: error_limit - len(body)])
                        if len(body) >= error_limit:
                            break
                    else:
                        if max_bytes is not None and len(part) > max_bytes - len(body):
                            raise UthanaError(
                                response.status_code,
                                (
                                    "Mutation response exceeded the configured byte limit; "
                                    "the operation may have succeeded. Inspect the result "
                                    "before resubmitting."
                                    if mutating
                                    else "Response exceeded the configured byte limit"
                                ),
                                kind="uncertain" if mutating else "response_too_large",
                            )
                        body.extend(part)
                data = bytes(body)
                if not response.is_success:
                    raise UthanaError(
                        response.status_code,
                        data.decode("utf-8", errors="replace"),
                        kind="http",
                        response_data=self._error_response_data(data),
                    )
                return data

    @overload
    async def _graphql(
        self,
        query: str,
        variables: dict | None = None,
        *,
        path: str | None = None,
        path_default: object = None,
        return_type: None = None,
        upload: tuple[str, bytes | BinaryIO] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> dict: ...

    @overload
    async def _graphql(
        self,
        query: str,
        variables: dict | None = None,
        *,
        path: str | None = None,
        path_default: object = None,
        return_type: type[_T],
        upload: tuple[str, bytes | BinaryIO] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> _T: ...

    async def _graphql(
        self,
        query: str,
        variables: dict | None = None,
        *,
        path: str | None = None,
        path_default: object = None,
        return_type: type[_T] | None = None,
        upload: tuple[str, bytes | BinaryIO] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> dict | _T:
        """Execute a single GraphQL operation with optional upload and timeout.

        Query responses use the read limit; mutations use a separate opt-in limit.
        Strip leading GraphQL ignored tokens before identifying a read operation.
        Unrecognized/fragment-first documents conservatively use mutation handling.
        No operationName is sent, so multi-operation documents cannot execute.
        """
        document = re.sub(r"\A(?:[\s,\ufeff]|#[^\r\n]*)*", "", query)
        mutating = re.match(r"(?:query\b|\{)", document) is None
        response_limit = self._max_mutation_response_bytes if mutating else self._max_response_bytes
        operation = {"query": query, "variables": variables or {}}
        kwargs: dict = {"json": operation}
        if upload is not None:
            filename, content = upload
            kwargs = {
                "data": {
                    "operations": json.dumps(operation),
                    "map": json.dumps({"0": ["variables.file"]}),
                },
                "files": {"0": (filename, content, "application/octet-stream")},
            }
        kwargs["headers"] = {"Accept": "application/json"}
        if timeout is not None:
            kwargs["timeout"] = timeout
        body = await self._request_bytes(
            "POST", self.graphql_url, max_bytes=response_limit, mutating=mutating, **kwargs
        )
        result = self._parse_graphql_response(body)
        data = result["data"]
        if path is not None:
            default = path_default if path_default is not None else {}
            for key in path.split("."):
                if not isinstance(data, dict):
                    data = default
                    break
                data = data.get(key, default)
            if data is None and path_default is not None:
                data = path_default
        if return_type is not None:
            return cast(_T, data)
        return cast(dict, data)

    @staticmethod
    def _parse_graphql_response(body: bytes, status_code: int = 200) -> dict:
        return Uthana._validate_graphql_response(Uthana._error_response_data(body), status_code)

    @staticmethod
    def _validate_graphql_response(result: object, status_code: int) -> dict:
        if not isinstance(result, dict):
            raise UthanaError(status_code, "Invalid GraphQL response", kind="invalid_response")
        if result.get("errors"):
            raise UthanaError(
                400,
                f"GraphQL errors: {result['errors']}",
                kind="graphql",
                response_data=result,
            )
        if not isinstance(result.get("data"), dict):
            raise UthanaError(status_code, "Invalid GraphQL response", kind="invalid_response")
        return result

    def _check_response(self, response: httpx.Response) -> dict:
        """Validate a previously buffered response and raise structured API errors."""
        try:
            result = response.json()
        except (ValueError, UnicodeDecodeError):
            result = None
        if not response.is_success:
            raise UthanaError(
                response.status_code,
                response.text,
                kind="http",
                response_data=result if isinstance(result, dict) else None,
            )
        return self._validate_graphql_response(result, response.status_code)

    def _motion_url(
        self,
        *,
        character_id: str,
        motion_id: str,
        output_format: OutputFormat,
        fps: int | None,
        no_mesh: bool | None,
        in_place: bool | None = None,
        roblox_compatible: bool | None = None,
        speed_multiplier: float | None = None,
        torso_only: bool | None = None,
    ) -> str:
        """Build the download URL for a motion file."""
        ext = output_format.lower()
        url = f"{self.base_url}/motion/file/motion_viewer/{character_id}/{motion_id}/{ext}/{character_id}-{motion_id}.{ext}"
        options = []
        if fps is not None:
            options.append(f"fps={fps}")
        if no_mesh is not None:
            options.append(f"no_mesh={'true' if no_mesh else 'false'}")
        for key, value in (
            ("in_place", in_place),
            ("roblox_compatible", roblox_compatible),
            ("torso_only", torso_only),
        ):
            if value is not None:
                options.append(f"{key}={'true' if value else 'false'}")
        if speed_multiplier is not None:
            options.append(f"speed_multiplier={speed_multiplier}")
        if options:
            url += f"?{'&'.join(options)}"
        return url

    def _build_character_output(self, *, result: dict, ext: str) -> CreateCharacterResult:
        """Parse create_character response into CreateCharacterResult."""
        character = result["data"]["create_character"]["character"]
        character_id = character["id"]
        auto_rig_confidence = result["data"]["create_character"].get("auto_rig_confidence")

        url = f"{self.base_url}/motion/bundle/{character_id}/character.{ext}"
        return CreateCharacterResult(
            url=url,
            character_id=character_id,
            auto_rig_confidence=auto_rig_confidence,
            message=result["data"]["create_character"].get("message"),
        )

    @staticmethod
    def _prepare_text_to_motion_vqvae_v1(
        *,
        prompt: str,
        character_id: str | None,
        foot_ik: bool | None,
        model: str,
    ) -> dict:
        """Build variables for text-to-motion-1.0 mutation."""
        return {
            "prompt": prompt,
            "character_id": character_id,
            "model": model,
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
        model: str,
    ) -> dict:
        """Build variables for text-to-motion-2.0 mutation."""
        return {
            "prompt": prompt,
            "character_id": character_id,
            "model": model,
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
        """Normalize model, route to the correct mutation, and build variables."""
        from .utils import normalize_model_name

        if model == "auto":
            model = cast(ModelType, models.ttm.default)
        canonical = normalize_model_name(str(model))
        if canonical == "text-to-motion":
            variables = self._prepare_text_to_motion_vqvae_v1(
                prompt=prompt, character_id=character_id, foot_ik=foot_ik, model=canonical
            )
            return q.TEXT_TO_MOTION_VQVAE_V1, variables
        elif canonical == "text-to-motion-bucmd":
            variables = self._prepare_text_to_motion_diffusion_v2(
                prompt=prompt,
                character_id=character_id,
                foot_ik=foot_ik,
                cfg_scale=cfg_scale,
                length=length,
                seed=seed,
                internal_ik=internal_ik,
                model=canonical,
            )
            return q.TEXT_TO_MOTION_DIFFUSION_V2, variables
        else:
            raise ValueError(
                f"Unknown model: {model!r}. Must be one of: text-to-motion-1.0, text-to-motion-2.0,"
                " vqvae-v1, diffusion-v2, text-to-motion, text-to-motion-bucmd."
            )


# Backwards compatibility alias
Client = Uthana
