import pytest


@pytest.mark.asyncio
async def test_register_returns_tokens(client):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "new@example.com", "password": "long-enough-password"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]


@pytest.mark.asyncio
async def test_register_rejects_duplicate_email(client, registered_user):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": registered_user["email"], "password": "another-long-password"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_register_rejects_short_password(client):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "shortpw@example.com", "password": "short"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_rejects_invalid_email(client):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "password": "long-enough-password"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_login_succeeds_with_correct_credentials(client, registered_user):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": registered_user["email"], "password": registered_user["password"]},
    )
    assert resp.status_code == 200
    assert resp.json()["access_token"]


@pytest.mark.asyncio
async def test_login_rejects_wrong_password(client, registered_user):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": registered_user["email"], "password": "wrong-password-here"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_rejects_unknown_email(client):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "ghost@example.com", "password": "whatever-long-password"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_issues_new_tokens(client, registered_user):
    resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": registered_user["refresh_token"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["refresh_token"]


@pytest.mark.asyncio
async def test_refresh_rejects_access_token_passed_as_refresh(client, registered_user):
    """The 'type' claim must be 'refresh'; an access token must be rejected."""
    resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": registered_user["access_token"]},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_rejects_tampered_token(client):
    resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "not.a.jwt"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_does_not_leak_through_query_string(client, registered_user):
    """Original bug: refresh accepted the token as ?refresh_token=... — it must not."""
    resp = await client.post(
        f"/api/v1/auth/refresh?refresh_token={registered_user['refresh_token']}",
    )
    # FastAPI's Pydantic body validation rejects the missing body with 422.
    assert resp.status_code in (401, 422)


@pytest.mark.asyncio
async def test_refresh_rejects_inactive_user(client, test_engine, registered_user):
    from sqlalchemy import update

    from app.db.models import User
    from sqlalchemy.ext.asyncio import async_sessionmaker

    Session = async_sessionmaker(test_engine, expire_on_commit=False)
    async with Session() as db:
        await db.execute(
            update(User).where(User.email == registered_user["email"]).values(is_active=False)
        )
        await db.commit()

    resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": registered_user["refresh_token"]},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_user_for_valid_token(client, registered_user):
    resp = await client.get("/api/v1/auth/me", headers=registered_user["headers"])
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == registered_user["email"]
    assert body["role"] == "user"
    assert "id" in body


@pytest.mark.asyncio
async def test_me_rejects_missing_token(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_rejects_invalid_token(client):
    resp = await client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not.a.jwt"}
    )
    assert resp.status_code == 401