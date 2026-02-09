from dataclasses import dataclass

import httpx


@dataclass
class MotionOutput:
    url: str
    session: httpx.Client | None = None

    def read(self) -> bytes:
        if self.session:
            response = self.session.get(self.url)
        else:
            response = httpx.get(self.url)
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
    session: httpx.Client | None = None

    def read(self) -> bytes:
        if self.session:
            response = self.session.get(self.url)
        else:
            response = httpx.get(self.url)
        response.raise_for_status()
        return response.content

    def save(self, path: str) -> None:
        with open(path, "wb") as f:
            f.write(self.read())
