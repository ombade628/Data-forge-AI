import jwt
from uuid import UUID
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from app.api.deps import CurrentUser, DbSession
from app.core.config import get_settings
from app.core.security import create_access_token, create_refresh_token, hash_password, verify_password
from app.db.models import User
from app.schemas import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse, UserRead

router = APIRouter(prefix="/auth", tags=["authentication"])


def tokens_for(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: DbSession):
    if await db.scalar(select(User).where(User.email == payload.email.lower())):
        raise HTTPException(status_code=409, detail="Email is already registered")
    user = User(email=payload.email.lower(), password_hash=hash_password(payload.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return tokens_for(user)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: DbSession):
    user = await db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return tokens_for(user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshRequest, db: DbSession):
    try:
        claims = jwt.decode(
            payload.refresh_token,
            get_settings().jwt_secret_key,
            algorithms=[get_settings().jwt_algorithm],
        )
        if claims.get("type") != "refresh":
            raise ValueError("not a refresh token")
        user = await db.get(User, UUID(claims["sub"]))
    except (jwt.PyJWTError, ValueError, KeyError):
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    return tokens_for(user)


@router.get("/me", response_model=UserRead)
async def me(user: CurrentUser):
    return user