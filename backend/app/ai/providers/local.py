from app.ai.analyzer import analyze_prompt
from app.ai.generator import generate_records
from app.schemas import DatasetSpecification


class LocalDatasetProvider:
    """Offline implementation for demos, tests, and low-risk local development."""

    name = "local"

    def analyze(self, prompt: str) -> DatasetSpecification:
        return analyze_prompt(prompt)

    def generate(self, specification: DatasetSpecification, count: int, seed: int) -> list[dict]:
        return generate_records(specification, count, seed)

