import random
from app.schemas import ColumnSpec, DatasetSpecification

TEXT_SAMPLES = [
    "I need help with my account access.",
    "Please explain the latest transaction on my statement.",
    "The service was quick and helpful today.",
    "I would like to update my contact details.",
]
INTENTS = ["account_access", "transaction_query", "card_issue", "profile_update"]


def _value(column: ColumnSpec, index: int, rng: random.Random):
    if column.name == "id":
        return index + 1
    if column.allowed_values:
        return rng.choice(column.allowed_values)
    if column.name == "intent":
        return rng.choice(INTENTS)
    if "response" in column.name:
        return "Thanks for contacting us. I can help you with that request."
    if "query" in column.name or column.name in {"text", "content"}:
        return rng.choice(TEXT_SAMPLES)
    if column.data_type == "integer":
        return rng.randint(1, 1000)
    if column.data_type == "number":
        return round(rng.uniform(0, 1000), 2)
    if column.data_type == "boolean":
        return bool(rng.randint(0, 1))
    return f"{column.name}_{index + 1}"


def generate_records(specification: DatasetSpecification, count: int, seed: int = 42) -> list[dict]:
    """Local deterministic generator; replace behind the provider interface for real LLM calls."""
    rng = random.Random(seed)
    return [{column.name: _value(column, index, rng) for column in specification.columns} for index in range(count)]

