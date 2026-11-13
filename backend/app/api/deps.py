from typing import Annotated
from uuid import UUID
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import get_settings
from app.db.models import User
from app.db.session import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
DbSession = Annotated[AsyncSession, Depends(get_db)]


async def current_user(token: Annotated[str, Depends(oauth2_scheme)], db: DbSession) -> User:
    try:
        payload = jwt.decode(token, get_settings().jwt_secret_key, algorithms=[get_settings().jwt_algorithm])
        if payload.get("type") != "access":
            raise ValueError("not an access token")
        user = await db.get(User, UUID(payload["sub"]))
    except (jwt.PyJWTError, ValueError, KeyError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired credentials")
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive account")
    return user


CurrentUser = Annotated[User, Depends(current_user)]

