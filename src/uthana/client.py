import json
import os
from dataclasses import dataclass
from typing import Literal

import httpx

from .exceptions import APIError


@dataclass
class MotionOutput:
    url: str


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


Character = Literal["Tar", "Ava", "Manny", "Quinn", "Y Bot"]
OutputFormat = Literal["GLB", "FBX"]

CHARACTER_IDS = {
    "Tar": "cXi2eAP19XwQ",
    "Ava": "cmEE2fT4aSaC",
    "Manny": "c43tbGks3crJ",
    "Quinn": "czCjWEMtWxt8",
    "Y Bot": "cJM4ngRqXg83",
}

DEFAULT_CHARACTER: Character = "Tar"
DEFAULT_OUTPUT_FORMAT: OutputFormat = "GLB"
DEFAULT_FPS = 30
DEFAULT_NO_MESH = True
DEFAULT_FOOT_IK = True
DEFAULT_MOTION_LENGTH = 1.0
DEFAULT_CFG_SCALE = 1.0
DEFAULT_SEED = 0
DEFAULT_INTERNAL_IK = True
DEFAULT_FRONT_FACING = True
DEFAULT_TIMEOUT = 120.0

_TEXT_TO_MOTION_V1_MUTATION = """
mutation TextToMotion($prompt: String!, $character_id: String!, $model: String!, $foot_ik: Boolean!) {
    create_text_to_motion(prompt: $prompt, character_id: $character_id, model: $model, foot_ik: $foot_ik) {
        motion {
            id
            name
        }
    }
}
"""

_TEXT_TO_MOTION_V2_MUTATION = """
mutation CreateTextToMotion($prompt: String!, $character_id: String!, $model: String!, $foot_ik: Boolean!, $cfg_scale: Float, $motion_length: Int, $seed: Int, $retargeting_ik: Boolean) {
    create_text_to_motion(prompt: $prompt, character_id: $character_id, model: $model, foot_ik: $foot_ik, cfg_scale: $cfg_scale, motion_length: $motion_length, seed: $seed, retargeting_ik: $retargeting_ik) {
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
    def _prepare_text_to_motion_v1(prompt: str, character: Character, foot_ik: bool) -> tuple[dict, str]:
        character_id = CHARACTER_IDS[character]
        variables = {
            "prompt": prompt,
            "character_id": character_id,
            "model": "text-to-motion",
            "foot_ik": foot_ik,
        }
        return variables, character_id

    @staticmethod
    def _prepare_text_to_motion_v2(
        prompt: str,
        character: Character,
        foot_ik: bool,
        cfg_scale: float,
        motion_length: float,
        seed: int,
        internal_ik: bool,
    ) -> tuple[dict, str]:
        character_id = CHARACTER_IDS[character]
        motion_length_fps = 20
        variables = {
            "prompt": prompt,
            "character_id": character_id,
            "model": "text-to-motion-bucmd",
            "foot_ik": foot_ik,
            "cfg_scale": cfg_scale,
            "motion_length": int(motion_length * motion_length_fps),
            "seed": None if seed == 0 else seed,
            "retargeting_ik": internal_ik,
        }
        return variables, character_id

    def _motion_url(
        self, character_id: str, motion_id: str, output_format: OutputFormat, fps: int, no_mesh: bool
    ) -> str:
        ext = output_format.lower()
        return (
            f"{self.base_url}/motion/file/motion_viewer/{character_id}/{motion_id}"
            f"/{ext}/{character_id}-{motion_id}.{ext}?fps={fps}&no_mesh={no_mesh}"
        )

    @staticmethod
    def _prepare_create_character(file_path: str, front_facing: bool) -> tuple[dict, str, str, str]:
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
        character: Character = DEFAULT_CHARACTER,
        output_format: OutputFormat = DEFAULT_OUTPUT_FORMAT,
        fps: int = DEFAULT_FPS,
        no_mesh: bool = DEFAULT_NO_MESH,
        foot_ik: bool = DEFAULT_FOOT_IK,
    ) -> MotionOutput:
        variables, character_id = self._prepare_text_to_motion_v1(prompt, character, foot_ik)
        data = self._graphql(_TEXT_TO_MOTION_V1_MUTATION, variables)
        motion_id = data["create_text_to_motion"]["motion"]["id"]
        url = self._motion_url(character_id, motion_id, output_format, fps, no_mesh)
        return MotionOutput(url=url)

    async def acreate_text_to_motion_v1(
        self,
        prompt: str,
        *,
        character: Character = DEFAULT_CHARACTER,
        output_format: OutputFormat = DEFAULT_OUTPUT_FORMAT,
        fps: int = DEFAULT_FPS,
        no_mesh: bool = DEFAULT_NO_MESH,
        foot_ik: bool = DEFAULT_FOOT_IK,
    ) -> MotionOutput:
        variables, character_id = self._prepare_text_to_motion_v1(prompt, character, foot_ik)
        data = await self._agraphql(_TEXT_TO_MOTION_V1_MUTATION, variables)
        motion_id = data["create_text_to_motion"]["motion"]["id"]
        url = self._motion_url(character_id, motion_id, output_format, fps, no_mesh)
        return MotionOutput(url=url)

    def create_text_to_motion_v2(
        self,
        prompt: str,
        *,
        character: Character = DEFAULT_CHARACTER,
        output_format: OutputFormat = DEFAULT_OUTPUT_FORMAT,
        fps: int = DEFAULT_FPS,
        no_mesh: bool = DEFAULT_NO_MESH,
        foot_ik: bool = DEFAULT_FOOT_IK,
        motion_length: float = DEFAULT_MOTION_LENGTH,
        cfg_scale: float = DEFAULT_CFG_SCALE,
        seed: int = DEFAULT_SEED,
        internal_ik: bool = DEFAULT_INTERNAL_IK,
    ) -> MotionOutput:
        variables, character_id = self._prepare_text_to_motion_v2(
            prompt,
            character,
            foot_ik,
            cfg_scale,
            motion_length,
            seed,
            internal_ik,
        )
        data = self._graphql(_TEXT_TO_MOTION_V2_MUTATION, variables)
        motion_id = data["create_text_to_motion"]["motion"]["id"]
        url = self._motion_url(character_id, motion_id, output_format, fps, no_mesh)
        return MotionOutput(url=url)

    async def acreate_text_to_motion_v2(
        self,
        prompt: str,
        *,
        character: Character = DEFAULT_CHARACTER,
        output_format: OutputFormat = DEFAULT_OUTPUT_FORMAT,
        fps: int = DEFAULT_FPS,
        no_mesh: bool = DEFAULT_NO_MESH,
        foot_ik: bool = DEFAULT_FOOT_IK,
        motion_length: float = DEFAULT_MOTION_LENGTH,
        cfg_scale: float = DEFAULT_CFG_SCALE,
        seed: int = DEFAULT_SEED,
        internal_ik: bool = DEFAULT_INTERNAL_IK,
    ) -> MotionOutput:
        variables, character_id = self._prepare_text_to_motion_v2(
            prompt,
            character,
            foot_ik,
            cfg_scale,
            motion_length,
            seed,
            internal_ik,
        )
        data = await self._agraphql(_TEXT_TO_MOTION_V2_MUTATION, variables)
        motion_id = data["create_text_to_motion"]["motion"]["id"]
        url = self._motion_url(character_id, motion_id, output_format, fps, no_mesh)
        return MotionOutput(url=url)

    def create_character(
        self,
        file_path: str,
        *,
        front_facing: bool = DEFAULT_FRONT_FACING,
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
        front_facing: bool = DEFAULT_FRONT_FACING,
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
        fps: int = DEFAULT_FPS,
        no_mesh: bool = DEFAULT_NO_MESH,
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
        fps: int = DEFAULT_FPS,
        no_mesh: bool = DEFAULT_NO_MESH,
    ) -> bytes:
        url = self._motion_url(character_id, motion_id, output_format, fps, no_mesh)
        response = await self.async_client.get(url)
        if not response.is_success:
            raise APIError(response.status_code, response.text)
        return response.content
