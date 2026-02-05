from dataclasses import dataclass

import requests


@dataclass
class MotionOutput:
    url: str
    session: requests.Session | None = None

    def read(self) -> bytes:
        if self.session:
            response = self.session.get(self.url)
        else:
            response = requests.get(self.url)
        response.raise_for_status()
        return response.content

    def save(self, path: str) -> None:
        with open(path, "wb") as f:
            f.write(self.read())


@dataclass
class CharacterOutput:
    url: str
    character_id: str
    auto_rig_confidence: float | None = None
    session: requests.Session | None = None

    def read(self) -> bytes:
        if self.session:
            response = self.session.get(self.url)
        else:
            response = requests.get(self.url)
        response.raise_for_status()
        return response.content

    def save(self, path: str) -> None:
        with open(path, "wb") as f:
            f.write(self.read())
