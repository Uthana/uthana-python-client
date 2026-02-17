# (c) Copyright 2025 Uthana, Inc. All Rights Reserved

import json
import os
import uuid

from dataclasses import dataclass
from importlib.metadata import version as _pkg_version
from typing import Literal

import httpx


class Error(Exception):
    """Base exception for Uthana API errors."""

    pass


class APIError(Error):
    """Raised when the API returns an error response."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"API error {status_code}: {message}")


@dataclass
class MotionOutput:
    character_id: str
    motion_id: str


@dataclass
class JobOutput:
    job_id: str
    status: str
    result: dict | None = None


@dataclass
class CharacterOutput:
    url: str
    character_id: str
    auto_rig_confidence: float | None = None


def detect_mesh_format(filepath: str) -> str | None:
    with open(filepath, "rb") as f:
        header = f.read(20)

    if header[:4] == b"glTF":
        return "glb"
    if header.startswith(b"Kaydara FBX Binary"):
        return "fbx"
    if header.startswith(b"; FBX"):
        return "fbx"
    return None


ModelType = Literal["vqvae-v1", "diffusion-v2"]
OutputFormat = Literal["glb", "fbx"]


@dataclass(frozen=True)
class DefaultCharacters:
    tar: str = "cXi2eAP19XwQ"
    ava: str = "cmEE2fT4aSaC"
    manny: str = "c43tbGks3crJ"
    quinn: str = "czCjWEMtWxt8"
    y_bot: str = "cJM4ngRqXg83"


DEFAULT_OUTPUT_FORMAT: OutputFormat = "glb"

DEFAULT_TIMEOUT = 120.0
_SUPPORTED_VIDEO_FORMATS = {".mp4", ".mov", ".avi"}

_TEXT_TO_MOTION_VQVAE_V1_MUTATION = """
mutation TextToMotion($prompt: String!, $character_id: String, $model: String!, $foot_ik: Boolean) {
    create_text_to_motion(prompt: $prompt, character_id: $character_id, model: $model, foot_ik: $foot_ik) {
        motion {
            id
            name
        }
    }
}
"""

_TEXT_TO_MOTION_DIFFUSION_V2_MUTATION = """
mutation CreateTextToMotion($prompt: String!, $character_id: String, $model: String!, $foot_ik: Boolean, $cfg_scale: Float, $length: Float, $seed: Int, $retargeting_ik: Boolean) {
    create_text_to_motion(prompt: $prompt, character_id: $character_id, model: $model, foot_ik: $foot_ik, cfg_scale: $cfg_scale, length: $length, seed: $seed, retargeting_ik: $retargeting_ik) {
        motion {
            id
            name
        }
    }
}
"""

_CREATE_CHARACTER_MUTATION = """
mutation CreateCharacter($name: String!, $file: Upload!, $auto_rig: Boolean, $auto_rig_front_facing: Boolean) {
    create_character(name: $name, file: $file, auto_rig: $auto_rig, auto_rig_front_facing: $auto_rig_front_facing) {
        character {
            id
            name
        }
        auto_rig_confidence
    }
}
"""

_CREATE_VIDEO_TO_MOTION_MUTATION = """
mutation CreateVideoToMotion($file: Upload!, $motion_name: String!) {
    create_video_to_motion(file: $file, motion_name: $motion_name) {
        job {
            id
            status
        }
    }
}
"""

_GET_JOB_QUERY = """
query GetJob($job_id: String!) {
    job(job_id: $job_id) {
        id
        status
        result
    }
}
"""


class Client:
    def __init__(self, api_key: str, *, staging: bool = False, timeout: float = DEFAULT_TIMEOUT):
        domain = "staging.uthana.com" if staging else "uthana.com"
        self.base_url = f"https://{domain}"
        self.graphql_url = f"{self.base_url}/graphql"
        self.session = httpx.Client(auth=(api_key, ""), timeout=timeout)
        self.async_client = httpx.AsyncClient(auth=(api_key, ""), timeout=timeout)
        self._log_init(domain, "uthana-python", _pkg_version("uthana"), api_key)

    def _log_init(self, domain: str, app: str, version: str, apikey: str):
        headers = {"User-Agent": f"{app}/{version}"}
        r = self.session.post(f"https://{domain}/graphql", json={'query': '{user{id}}'}, headers=headers)
        r.raise_for_status()
        uid = (r.json()["data"].get("user") or {}).get("id")

        anon_id = "00000000" + str(uuid.uuid1(clock_seq=1))[8:]

        evt = {
            "type": "track",
            "event": "initialized",
            "app": app,
            "userId": uid,
            "anonymousId": anon_id,
            "meta": {},
        }

        r = self.session.post(f"https://{domain}/event", json=evt, headers=headers)
        r.raise_for_status()
        return r.json()

    def _graphql(self, query: str, variables: dict | None = None) -> dict:
        response = self.session.post(
            self.graphql_url,
            json={"query": query, "variables": variables or {}},
        )
        if not response.is_success:
            raise APIError(response.status_code, response.text)
        result = response.json()
        if "errors" in result:
            raise APIError(400, f"GraphQL errors: {result['errors']}")
        return result["data"]

    async def _agraphql(self, query: str, variables: dict | None = None) -> dict:
        response = await self.async_client.post(
            self.graphql_url,
            json={"query": query, "variables": variables or {}},
        )
        if not response.is_success:
            raise APIError(response.status_code, response.text)
        result = response.json()
        if "errors" in result:
            raise APIError(400, f"GraphQL errors: {result['errors']}")
        return result["data"]

    def _graphql_upload(self, query: str, variables: dict, file_path: str, file_variable: str = "file") -> dict:
        variables[file_variable] = None
        operations = json.dumps({"query": query, "variables": variables})
        map_data = json.dumps({"0": [f"variables.{file_variable}"]})

        with open(file_path, "rb") as f:
            response = self.session.post(
                self.graphql_url,
                data={"operations": operations, "map": map_data},
                files={"0": (file_path, f, "application/octet-stream")},
            )

        if not response.is_success:
            raise APIError(response.status_code, response.text)
        result = response.json()
        if "errors" in result:
            raise APIError(400, f"GraphQL errors: {result['errors']}")
        return result["data"]

    @staticmethod
    def _prepare_text_to_motion_vqvae_v1(prompt: str, character_id: str | None, foot_ik: bool | None) -> dict:
        return {
            "prompt": prompt,
            "character_id": character_id,
            "model": "text-to-motion",
            "foot_ik": foot_ik,
        }

    @staticmethod
    def _prepare_text_to_motion_diffusion_v2(
        prompt: str,
        character_id: str | None,
        foot_ik: bool | None,
        cfg_scale: float | None,
        length: float | None,
        seed: int | None,
        internal_ik: bool | None,
    ) -> dict:
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

    def _motion_url(
        self, character_id: str, motion_id: str, output_format: OutputFormat, fps: int | None, no_mesh: bool | None
    ) -> str:
        ext = output_format.lower()
        url = f"{self.base_url}/motion/file/motion_viewer/{character_id}/{motion_id}/{ext}/{character_id}-{motion_id}.{ext}"
        options = []
        if fps is not None:
            options.append(f"fps={fps}")
        if no_mesh is not None:
            options.append(f"no_mesh={'true' if no_mesh else 'false'}")
        if len(options) > 0:
            url += f"?{'&'.join(options)}"
        return url

    @staticmethod
    def _prepare_create_character(
        file_path: str, auto_rig: bool | None, front_facing: bool | None
    ) -> tuple[dict, str, str, str]:
        filename = os.path.basename(file_path)
        name = os.path.splitext(filename)[0]
        ext = detect_mesh_format(file_path)
        if ext is None:
            ext = os.path.splitext(filename)[1].lstrip(".")

        variables = {
            "name": name,
            "file": None,
            "auto_rig": auto_rig,
            "auto_rig_front_facing": front_facing,
        }
        return variables, name, ext, filename

    def _build_character_output(self, result: dict, ext: str) -> CharacterOutput:
        character = result["data"]["create_character"]["character"]
        character_id = character["id"]
        auto_rig_confidence = result["data"]["create_character"]["auto_rig_confidence"]

        url = f"{self.base_url}/motion/bundle/{character_id}/character.{ext}"
        return CharacterOutput(
            url=url,
            character_id=character_id,
            auto_rig_confidence=auto_rig_confidence,
        )

    def _check_response(self, response: httpx.Response) -> dict:
        if not response.is_success:
            raise APIError(response.status_code, response.text)
        result = response.json()
        if "errors" in result:
            raise APIError(400, f"GraphQL errors: {result['errors']}")
        return result

    def _prepare_and_select_text_to_motion(
        self,
        model: ModelType,
        prompt: str,
        character_id: str | None,
        foot_ik: bool | None,
        length: float | None,
        cfg_scale: float | None,
        seed: int | None,
        internal_ik: bool | None,
    ) -> tuple[str, dict]:
        if model == "vqvae-v1":
            variables = self._prepare_text_to_motion_vqvae_v1(prompt, character_id, foot_ik)
            return _TEXT_TO_MOTION_VQVAE_V1_MUTATION, variables
        elif model == "diffusion-v2":
            variables = self._prepare_text_to_motion_diffusion_v2(
                prompt, character_id, foot_ik, cfg_scale, length, seed, internal_ik,
            )
            return _TEXT_TO_MOTION_DIFFUSION_V2_MUTATION, variables
        else:
            raise ValueError(f"Unknown model: {model!r}. Must be 'vqvae-v1' or 'diffusion-v2'.")

    def create_text_to_motion(
        self,
        model: ModelType,
        prompt: str,
        *,
        character_id: str | None = None,
        foot_ik: bool | None = None,
        length: float | None = None,
        cfg_scale: float | None = None,
        seed: int | None = None,
        internal_ik: bool | None = None,
    ) -> MotionOutput:
        """Generate a 3D character animation from a natural language prompt.

        Args:
            model: Model to use for generation. ``"vqvae-v1"`` for the
                original model or ``"diffusion-v2"`` for advanced control
                over steps, cfg_scale, length, and seed.
            prompt: Natural language description of the desired animation.
            character_id: Character to animate. Defaults to
                ``DefaultCharacters.tar``.
            foot_ik: Enable foot inverse-kinematics for better ground
                contact. Server default is ``False``.
            length: Motion duration in seconds (diffusion-v2 only,
                0.25--10, server default 10).
            cfg_scale: Classifier-free guidance scale (diffusion-v2 only,
                0--10, server default 2.0).
            seed: Random seed for reproducibility (diffusion-v2 only,
                1--99999).
            internal_ik: Enable inverse-kinematics during retargeting
                (diffusion-v2 only, server default ``True``).

        Returns:
            MotionOutput containing the ``motion_id`` and ``character_id``
            which can be passed to :meth:`download_motion`.
        """
        mutation, variables = self._prepare_and_select_text_to_motion(
            model, prompt, character_id, foot_ik, length, cfg_scale, seed, internal_ik,
        )
        data = self._graphql(mutation, variables)
        motion_id = data["create_text_to_motion"]["motion"]["id"]
        if character_id is None:
            character_id = DefaultCharacters.tar
        return MotionOutput(character_id=character_id, motion_id=motion_id)

    async def acreate_text_to_motion(
        self,
        model: ModelType,
        prompt: str,
        *,
        character_id: str | None = None,
        foot_ik: bool | None = None,
        length: float | None = None,
        cfg_scale: float | None = None,
        seed: int | None = None,
        internal_ik: bool | None = None,
    ) -> MotionOutput:
        """Async version of :meth:`create_text_to_motion`."""
        mutation, variables = self._prepare_and_select_text_to_motion(
            model, prompt, character_id, foot_ik, length, cfg_scale, seed, internal_ik,
        )
        data = await self._agraphql(mutation, variables)
        motion_id = data["create_text_to_motion"]["motion"]["id"]
        if character_id is None:
            character_id = DefaultCharacters.tar
        return MotionOutput(character_id=character_id, motion_id=motion_id)

    def create_character(
        self,
        file_path: str,
        *,
        auto_rig: bool | None = None,
        front_facing: bool | None = None,
    ) -> CharacterOutput:
        """Upload and optionally auto-rig a 3D character model.

        The character must be a humanoid mesh in FBX, GLB, or GLTF format
        (max 20 MB by default, up to 100 MB for some organisations).  If
        ``auto_rig`` is enabled and no skeleton is found, the service will
        automatically rig the character.  Auto-rigging typically takes
        30--60 seconds.

        The character mesh should include at least a pelvis, left/right
        hips, and left/right shoulders.  Non-humanoid structures, extreme
        proportions, overlapping limbs, or large appendages (wings, tails)
        may reduce rigging quality.

        Args:
            file_path: Local path to an FBX, GLB, or GLTF file.
            auto_rig: Automatically rig the character when no skeleton is
                detected. Server default is ``True``.
            front_facing: Orient the auto-rigged character to face forward.
                Server default is ``True``.

        Returns:
            CharacterOutput containing the ``character_id``, a download
            ``url``, and an ``auto_rig_confidence`` score (0--1.0, where
            1.0 indicates high confidence).
        """
        variables, name, ext, _ = self._prepare_create_character(file_path, auto_rig, front_facing)
        operations = json.dumps({"query": _CREATE_CHARACTER_MUTATION, "variables": variables})
        map_data = json.dumps({"0": ["variables.file"]})

        with open(file_path, "rb") as f:
            response = self.session.post(
                self.graphql_url,
                data={"operations": operations, "map": map_data},
                files={"0": (f"{name}.{ext}", f, "application/octet-stream")},
            )

        result = self._check_response(response)
        return self._build_character_output(result, ext)

    async def acreate_character(
        self,
        file_path: str,
        *,
        auto_rig: bool | None = None,
        front_facing: bool | None = None,
    ) -> CharacterOutput:
        """Async version of :meth:`create_character`."""
        variables, name, ext, _ = self._prepare_create_character(file_path, auto_rig, front_facing)
        operations = json.dumps({"query": _CREATE_CHARACTER_MUTATION, "variables": variables})
        map_data = json.dumps({"0": ["variables.file"]})

        with open(file_path, "rb") as f:
            response = await self.async_client.post(
                self.graphql_url,
                data={"operations": operations, "map": map_data},
                files={"0": (f"{name}.{ext}", f, "application/octet-stream")},
            )

        result = self._check_response(response)
        return self._build_character_output(result, ext)

    def download_character(
        self,
        character_id: str,
        *,
        output_format: OutputFormat = DEFAULT_OUTPUT_FORMAT,
    ) -> bytes:
        """Download a previously uploaded (and optionally auto-rigged) character model.

        Args:
            character_id: Identifier of the character to download (e.g.
                from :class:`CharacterOutput`).
            output_format: File format — ``"glb"`` (default) or
                ``"fbx"``.

        Returns:
            Raw bytes of the character model file in the requested format.
        """
        ext = output_format.lower()
        url = f"{self.base_url}/motion/bundle/{character_id}/character.{ext}"
        response = self.session.get(url)
        if not response.is_success:
            raise APIError(response.status_code, response.text)
        return response.content

    async def adownload_character(
        self,
        character_id: str,
        *,
        output_format: OutputFormat = DEFAULT_OUTPUT_FORMAT,
    ) -> bytes:
        """Async version of :meth:`download_character`."""
        ext = output_format.lower()
        url = f"{self.base_url}/motion/bundle/{character_id}/character.{ext}"
        response = await self.async_client.get(url)
        if not response.is_success:
            raise APIError(response.status_code, response.text)
        return response.content

    def download_motion(
        self,
        character_id: str,
        motion_id: str,
        *,
        output_format: OutputFormat = DEFAULT_OUTPUT_FORMAT,
        fps: int | None = None,
        no_mesh: bool | None = None,
    ) -> bytes:
        """Download a motion animation file, automatically retargeted to the given character.

        Args:
            character_id: Identifier of the character to retarget the
                motion onto (e.g. from :class:`CharacterOutput`).
            motion_id: Identifier of the motion to download (e.g. from
                :class:`MotionOutput` or a completed :class:`JobOutput`).
            output_format: File format — ``"glb"`` (default) or
                ``"fbx"``.
            fps: Frame rate of the exported animation.  Must be 24, 30,
                or 60.
            no_mesh: When ``True``, return only the animation data
                without the character mesh.  Server default is ``False``.

        Returns:
            Raw bytes of the animation file in the requested format.
        """
        url = self._motion_url(character_id, motion_id, output_format, fps, no_mesh)
        response = self.session.get(url)
        if not response.is_success:
            raise APIError(response.status_code, response.text)
        return response.content

    async def adownload_motion(
        self,
        character_id: str,
        motion_id: str,
        *,
        output_format: OutputFormat = DEFAULT_OUTPUT_FORMAT,
        fps: int | None = None,
        no_mesh: bool | None = None,
    ) -> bytes:
        """Async version of :meth:`download_motion`."""
        url = self._motion_url(character_id, motion_id, output_format, fps, no_mesh)
        response = await self.async_client.get(url)
        if not response.is_success:
            raise APIError(response.status_code, response.text)
        return response.content

    def get_job(self, job_id: str) -> JobOutput:
        data = self._graphql(_GET_JOB_QUERY, {"job_id": job_id})
        job = data["job"]
        return JobOutput(job_id=job["id"], status=job["status"], result=job.get("result"))

    async def aget_job(self, job_id: str) -> JobOutput:
        data = await self._agraphql(_GET_JOB_QUERY, {"job_id": job_id})
        job = data["job"]
        return JobOutput(job_id=job["id"], status=job["status"], result=job.get("result"))

    @staticmethod
    def _prepare_video_to_motion(file_path: str, motion_name: str | None) -> tuple[dict, str]:
        filename = os.path.basename(file_path)
        ext = os.path.splitext(filename)[1].lower()
        if ext not in _SUPPORTED_VIDEO_FORMATS:
            raise Error(f"Unsupported video format '{ext}'. Supported: {', '.join(sorted(_SUPPORTED_VIDEO_FORMATS))}")
        if motion_name is None:
            motion_name = os.path.splitext(filename)[0]
        variables = {"motion_name": motion_name, "file": None}
        return variables, filename

    @staticmethod
    def _build_video_to_motion_output(result: dict) -> JobOutput:
        job = result["data"]["create_video_to_motion"]["job"]
        return JobOutput(job_id=job["id"], status=job["status"])

    def create_video_to_motion(
        self,
        file_path: str,
        *,
        motion_name: str | None = None,
    ) -> JobOutput:
        """Extract motion capture data from a video of a person performing an action.

        This is an asynchronous operation.  The returned :class:`JobOutput`
        contains a ``job_id`` whose status can be polled (e.g. via
        :meth:`get_job`) until it reaches ``FINISHED``.  Poll at
        5-second intervals.  Possible statuses are ``RESERVED`` (queued),
        ``READY`` (processing), ``FINISHED``, and ``FAILED``.

        **Video requirements**

        * Formats: MP4, MOV, or AVI.
        * Duration: 2--60 seconds.
        * Frame rate: 24--120 fps.
        * Resolution: 300--4096 px.
        * A single person must be fully visible in frame.
        * The subject should begin standing with both feet on the ground.
        * Use a stable camera (tripod or flat surface), a plain
          well-lit background, and avoid harsh shadows.

        Args:
            file_path: Local path to an MP4, MOV, or AVI video file.
            motion_name: Name for the resulting motion.  Defaults to the
                filename stem.

        Returns:
            JobOutput containing the ``job_id`` and initial ``status``.
            Once the job reaches ``FINISHED``, the ``result`` dict holds
            the motion ``id`` for downloading.
        """
        variables, filename = self._prepare_video_to_motion(file_path, motion_name)
        operations = json.dumps({"query": _CREATE_VIDEO_TO_MOTION_MUTATION, "variables": variables})
        map_data = json.dumps({"0": ["variables.file"]})

        with open(file_path, "rb") as f:
            response = self.session.post(
                self.graphql_url,
                data={"operations": operations, "map": map_data},
                files={"0": (filename, f, "application/octet-stream")},
            )

        result = self._check_response(response)
        return self._build_video_to_motion_output(result)

    async def acreate_video_to_motion(
        self,
        file_path: str,
        *,
        motion_name: str | None = None,
    ) -> JobOutput:
        """Async version of :meth:`create_video_to_motion`."""
        variables, filename = self._prepare_video_to_motion(file_path, motion_name)
        operations = json.dumps({"query": _CREATE_VIDEO_TO_MOTION_MUTATION, "variables": variables})
        map_data = json.dumps({"0": ["variables.file"]})

        with open(file_path, "rb") as f:
            response = await self.async_client.post(
                self.graphql_url,
                data={"operations": operations, "map": map_data},
                files={"0": (filename, f, "application/octet-stream")},
            )

        result = self._check_response(response)
        return self._build_video_to_motion_output(result)
