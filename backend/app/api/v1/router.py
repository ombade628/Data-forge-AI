from fastapi import APIRouter
from app.api.v1 import analytics, auth, datasets, exports, generation, prompt_studio

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(prompt_studio.router)
api_router.include_router(datasets.router)
api_router.include_router(generation.router)
api_router.include_router(exports.router)
api_router.include_router(analytics.router)
