import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.session import get_db
from app.main import app


@pytest_asyncio.fixture
async def test_engine(tmp_path):
    """A fresh SQLite file per test — fast, isolated, no Postgres/Redis needed."""
    db_path = tmp_path / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def client(test_engine, monkeypatch):
    Session = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)

    async def _get_db():
        async with Session() as session:
            yield session

    # run_generation_job uses SessionLocal directly, not get_db — patch it too.
    monkeypatch.setattr("app.domains.generation.service.SessionLocal", Session)

    app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def registered_user(client):
    payload = {"email": "alice@example.com", "password": "correct-horse-battery"}
    resp = await client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 201, resp.text
    tokens = resp.json()
    return {
        "email": payload["email"],
        "password": payload["password"],
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "headers": {"Authorization": f"Bearer {tokens['access_token']}"},
    }


@pytest_asyncio.fixture
async def other_user(client):
    payload = {"email": "bob@example.com", "password": "another-long-password"}
    resp = await client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 201, resp.text
    tokens = resp.json()
    return {
        "email": payload["email"],
        "password": payload["password"],
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "headers": {"Authorization": f"Bearer {tokens['access_token']}"},
    }