from app.ai.providers.base import DatasetAIProvider
from app.ai.providers.local import LocalDatasetProvider
from app.core.config import get_settings


def get_dataset_provider() -> DatasetAIProvider:
    """Select a provider in one place; vendor adapters implement DatasetAIProvider."""
    provider = get_settings().llm_provider.lower()
    if provider == "local":
        return LocalDatasetProvider()
    raise RuntimeError(f"LLM provider '{provider}' is not configured. Set LLM_PROVIDER=local or install a provider adapter.")

