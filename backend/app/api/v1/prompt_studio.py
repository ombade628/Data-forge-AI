from fastapi import APIRouter
from app.ai.analyzer import extract_requested_count
from app.ai.providers.factory import get_dataset_provider
from app.api.deps import CurrentUser
from app.schemas import PromptAnalyzeRequest

router = APIRouter(prefix="/prompts", tags=["prompt studio"])


@router.post("/analyze")
async def analyze(payload: PromptAnalyzeRequest, _: CurrentUser):
    provider = get_dataset_provider()
    specification = provider.analyze(payload.prompt)
    return {
        "specification": specification,
        "suggested_record_count": extract_requested_count(payload.prompt, payload.record_count),
        "clarification_questions": [],
        "provider": provider.name,
    }
