"""Deterministic requirement extraction used locally and as a safe fallback.

An LLM-backed provider can replace this module without changing routes or jobs.
"""
import re
from app.schemas import ColumnSpec, DatasetSpecification

DEFAULT_COLUMNS = [
    ColumnSpec(name="id", data_type="integer", description="Unique record identifier"),
    ColumnSpec(name="text", data_type="string", description="Generated content"),
    ColumnSpec(name="label", data_type="string", description="Dataset label"),
]


def analyze_prompt(prompt: str) -> DatasetSpecification:
    text = prompt.lower()
    columns: list[ColumnSpec] = [ColumnSpec(name="id", data_type="integer", description="Unique record identifier")]
    dataset_type = "custom"
    if any(word in text for word in ("support", "conversation", "chat")):
        dataset_type = "customer_support"
        columns += [
            ColumnSpec(name="customer_query", description="Customer's request"),
            ColumnSpec(name="agent_response", description="Support agent response"),
            ColumnSpec(name="intent", description="Classified user intent"),
            ColumnSpec(name="sentiment", description="Customer sentiment", allowed_values=["positive", "neutral", "negative"]),
            ColumnSpec(name="resolution_status", description="Whether the issue was resolved", allowed_values=["resolved", "escalated", "pending"]),
        ]
    elif "sentiment" in text:
        dataset_type = "sentiment_classification"
        columns += [
            ColumnSpec(name="text", description="Text to classify"),
            ColumnSpec(name="sentiment", description="Sentiment label", allowed_values=["positive", "neutral", "negative"]),
        ]
    elif any(word in text for word in ("regression", "price", "forecast")):
        dataset_type = "regression"
        columns += [ColumnSpec(name="feature", data_type="number"), ColumnSpec(name="target", data_type="number")]
    else:
        columns += DEFAULT_COLUMNS[1:]

    languages = []
    for language in ("English", "Hindi", "Hinglish", "Spanish", "French", "German"):
        if language.lower() in text:
            languages.append(language)
    return DatasetSpecification(
        dataset_type=dataset_type,
        languages=languages or ["English"],
        columns=columns,
        constraints=["Every required field must be populated", "Records must be internally consistent"],
    )


def extract_requested_count(prompt: str, fallback: int) -> int:
    match = re.search(r"(?:generate|create|produce)\s+([\d,]+)", prompt.lower())
    return min(int(match.group(1).replace(",", "")), 100_000) if match else fallback

