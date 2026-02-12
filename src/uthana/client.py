import json
import os
from dataclasses import dataclass
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

_TEXT_TO_MOTION_V1_MUTATION = """
mutation TextToMotion($prompt: String!, $character_id: String, $model: String!, $foot_ik: Boolean) {
    create_text_to_motion(prompt: $prompt, character_id: $character_id, model: $model, foot_ik: $foot_ik) {
        motion {
            id
            name
        }
    }
}
"""

_TEXT_TO_MOTION_V2_MUTATION = """
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
    def _prepare_text_to_motion_v1(prompt: str, character_id: str | None, foot_ik: bool | None) -> dict:
        return {
            "prompt": prompt,
            "character_id": character_id,
            "model": "text-to-motion",
            "foot_ik": foot_ik,
        }

    @staticmethod
    def _prepare_text_to_motion_v2(
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
    def _prepare_create_character(file_path: str, front_facing: bool | None) -> tuple[dict, str, str, str]:
        filename = os.path.basename(file_path)
        name = os.path.splitext(filename)[0]
        ext = detect_mesh_format(file_path)
        if ext is None:
            ext = os.path.splitext(filename)[1].lstrip(".")

        variables = {
            "name": name,
            "file": None,
            "auto_rig": True,
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

    def create_text_to_motion_v1(
        self,
        prompt: str,
        *,
        character_id: str | None = None,
        foot_ik: bool | None = None,
    ) -> MotionOutput:
        variables = self._prepare_text_to_motion_v1(prompt, character_id, foot_ik)
        data = self._graphql(_TEXT_TO_MOTION_V1_MUTATION, variables)
        motion_id = data["create_text_to_motion"]["motion"]["id"]
        if character_id is None:
            character_id = DefaultCharacters.tar
        return MotionOutput(character_id=character_id, motion_id=motion_id)

    async def acreate_text_to_motion_v1(
        self,
        prompt: str,
        *,
        character_id: str | None = None,
        foot_ik: bool | None = None,
    ) -> MotionOutput:
        variables = self._prepare_text_to_motion_v1(prompt, character_id, foot_ik)
        data = await self._agraphql(_TEXT_TO_MOTION_V1_MUTATION, variables)
        motion_id = data["create_text_to_motion"]["motion"]["id"]
        if character_id is None:
            character_id = DefaultCharacters.tar
        return MotionOutput(character_id=character_id, motion_id=motion_id)

    def create_text_to_motion_v2(
        self,
        prompt: str,
        *,
        character_id: str | None = None,
        foot_ik: bool | None = None,
        length: float | None = None,
        cfg_scale: float | None = None,
        seed: int | None = None,
        internal_ik: bool | None = None,
    ) -> MotionOutput:
        variables = self._prepare_text_to_motion_v2(
            prompt,
            character_id,
            foot_ik,
            cfg_scale,
            length,
            seed,
            internal_ik,
        )
        data = self._graphql(_TEXT_TO_MOTION_V2_MUTATION, variables)
        motion_id = data["create_text_to_motion"]["motion"]["id"]
        if character_id is None:
            character_id = DefaultCharacters.tar
        return MotionOutput(character_id=character_id, motion_id=motion_id)

    async def acreate_text_to_motion_v2(
        self,
        prompt: str,
        *,
        character_id: str | None = None,
        foot_ik: bool | None = None,
        length: float | None = None,
        cfg_scale: float | None = None,
        seed: int | None = None,
        internal_ik: bool | None = None,
    ) -> MotionOutput:
        variables = self._prepare_text_to_motion_v2(
            prompt,
            character_id,
            foot_ik,
            cfg_scale,
            length,
            seed,
            internal_ik,
        )
        data = await self._agraphql(_TEXT_TO_MOTION_V2_MUTATION, variables)
        motion_id = data["create_text_to_motion"]["motion"]["id"]
        if character_id is None:
            character_id = DefaultCharacters.tar
        return MotionOutput(character_id=character_id, motion_id=motion_id)

    def create_character(
        self,
        file_path: str,
        *,
        front_facing: bool | None = None,
    ) -> CharacterOutput:
        variables, name, ext, _ = self._prepare_create_character(file_path, front_facing)
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
        front_facing: bool | None = None,
    ) -> CharacterOutput:
        variables, name, ext, _ = self._prepare_create_character(file_path, front_facing)
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
