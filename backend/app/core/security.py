from datetime import UTC, datetime, timedelta
import jwt
from pwdlib import PasswordHash
from app.core.config import get_settings

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, stored_hash: str) -> bool:
    return password_hash.verify(password, stored_hash)


def create_token(subject: str, token_type: str, expires_delta: timedelta) -> str:
    settings = get_settings()
    payload = {"sub": subject, "type": token_type, "exp": datetime.now(UTC) + expires_delta}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(subject: str) -> str:
    return create_token(subject, "access", timedelta(minutes=get_settings().access_token_expire_minutes))


def create_refresh_token(subject: str) -> str:
    return create_token(subject, "refresh", timedelta(days=get_settings().refresh_token_expire_days))

