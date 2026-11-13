import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import engine
import app.db.models  # register SQLAlchemy metadata

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Dev convenience only. Production runs `alembic upgrade head` in the deploy command.
    if get_settings().environment == "development":
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(title="DataForge AI API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix=get_settings().api_v1_prefix)

HTTP_REQUESTS = Counter(
    "dataforge_http_requests_total",
    "HTTP requests served",
    ["method", "path", "status"],
)


@app.middleware("http")
async def record_request_metrics(request: Request, call_next):
    response = await call_next(request)
    # Use the route template (e.g. /api/v1/datasets/{dataset_id}) instead of the raw URL.
    route = request.scope.get("route")
    path = getattr(route, "path", request.url.path)
    HTTP_REQUESTS.labels(request.method, path, response.status_code).inc()
    return response


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "service": "dataforge-api"}


@app.get("/metrics", include_in_schema=False)
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)