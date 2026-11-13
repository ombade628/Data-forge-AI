from typing import Protocol
from app.schemas import DatasetSpecification


class DatasetAIProvider(Protocol):
    """Stable boundary around an AI vendor or deterministic local implementation."""

    name: str

    def analyze(self, prompt: str) -> DatasetSpecification: ...

    def generate(self, specification: DatasetSpecification, count: int, seed: int) -> list[dict]: ...

