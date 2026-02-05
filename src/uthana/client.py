import json
import os
from typing import Literal

import requests

from .exceptions import APIError
from .models import CharacterOutput, MotionOutput


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


class Client:
    def __init__(self, api_key: str, *, staging: bool = False):
        domain = "tony.uthana.dev" if staging else "uthana.com"
        self.base_url = f"https://{domain}"
        self.graphql_url = f"{self.base_url}/graphql"
        self.session = requests.Session()
        self.session.auth = (api_key, "")

    def _graphql(self, query: str, variables: dict | None = None) -> dict:
        response = self.session.post(
            self.graphql_url,
            json={"query": query, "variables": variables or {}},
        )
        if not response.ok:
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
            files = {
                "operations": (None, operations, "application/json"),
                "map": (None, map_data, "application/json"),
                "0": (file_path, f, "application/octet-stream"),
            }
            response = self.session.post(self.graphql_url, files=files)

        if not response.ok:
            raise APIError(response.status_code, response.text)
        result = response.json()
        if "errors" in result:
            raise APIError(400, f"GraphQL errors: {result['errors']}")
        return result["data"]

    def text_to_motion_v1(
        self,
        prompt: str,
        *,
        character: Character = "Tar",
        output_format: OutputFormat = "GLB",
        fps: int = 24,
        no_mesh: bool = True,
        foot_ik: bool = True,
    ) -> MotionOutput:
        mutation = """
        mutation TextToMotion($prompt: String!, $character_id: String!, $model: String!, $foot_ik: Boolean!) {
            create_text_to_motion(prompt: $prompt, character_id: $character_id, model: $model, foot_ik: $foot_ik) {
                motion {
                    id
                    name
                }
            }
        }
        """

        character_id = CHARACTER_IDS[character]
        variables = {
            "prompt": prompt,
            "character_id": character_id,
            "model": "text-to-motion",
            "foot_ik": foot_ik,
        }

        data = self._graphql(mutation, variables)
        motion_id = data["create_text_to_motion"]["motion"]["id"]

        ext = output_format.lower()
        url = (
            f"{self.base_url}/motion/file/motion_viewer/{character_id}/{motion_id}"
            f"/{ext}/{character_id}-{motion_id}.{ext}?fps={fps}&no_mesh={no_mesh}"
        )

        return MotionOutput(url=url, session=self.session)

    def text_to_motion_v2(
        self,
        prompt: str,
        *,
        character: Character = "Tar",
        output_format: OutputFormat = "GLB",
        fps: int = 24,
        no_mesh: bool = True,
        foot_ik: bool = True,
        motion_length: float = 0.5,
        cfg_scale: float = 1.0,
        seed: int = 0,
        internal_ik: bool = True,
    ) -> MotionOutput:
        mutation = """
        mutation CreateTextToMotion($prompt: String!, $character_id: String!, $model: String!, $foot_ik: Boolean!, $cfg_scale: Float, $motion_length: Int, $seed: Int, $retargeting_ik: Boolean) {
            create_text_to_motion(prompt: $prompt, character_id: $character_id, model: $model, foot_ik: $foot_ik, cfg_scale: $cfg_scale, motion_length: $motion_length, seed: $seed, retargeting_ik: $retargeting_ik) {
                motion {
                    id
                    name
                }
            }
        }
        """

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

        data = self._graphql(mutation, variables)
        motion_id = data["create_text_to_motion"]["motion"]["id"]

        ext = output_format.lower()
        url = (
            f"{self.base_url}/motion/file/motion_viewer/{character_id}/{motion_id}"
            f"/{ext}/{character_id}-{motion_id}.{ext}?fps={fps}&no_mesh={no_mesh}"
        )

        return MotionOutput(url=url, session=self.session)

    def auto_rig_v1(
        self,
        file_path: str,
        *,
        front_facing: bool = True,
    ) -> CharacterOutput:
        mutation = """
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

        operations = json.dumps({"query": mutation, "variables": variables})
        map_data = json.dumps({"0": ["variables.file"]})

        with open(file_path, "rb") as f:
            files = {
                "operations": (None, operations, "application/json"),
                "map": (None, map_data, "application/json"),
                "0": (f"{name}.{ext}", f, "application/octet-stream"),
            }
            response = self.session.post(self.graphql_url, files=files)

        if not response.ok:
            raise APIError(response.status_code, response.text)
        result = response.json()
        if "errors" in result:
            raise APIError(400, f"GraphQL errors: {result['errors']}")

        character = result["data"]["create_character"]["character"]
        character_id = character["id"]
        auto_rig_confidence = result["data"]["create_character"]["auto_rig_confidence"]

        url = f"{self.base_url}/motion/bundle/{character_id}/character.{ext}"
        return CharacterOutput(
            url=url,
            character_id=character_id,
            auto_rig_confidence=auto_rig_confidence,
            session=self.session,
        )
