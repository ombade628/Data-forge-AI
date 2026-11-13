from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.core.config import get_settings


def async_database_url(database_url: str) -> str:
    """Accept Render's and Neon's standard Postgres URLs while using asyncpg.

    Two rewrites happen here:
    1. ``postgres://`` / ``postgresql://`` → ``postgresql+asyncpg://`` so SQLAlchemy
       picks the async driver.
    2. ``?sslmode=...`` → ``?ssl=...`` because asyncpg rejects ``sslmode`` (that is a
       libpq/psycopg keyword). Neon requires TLS, so the parameter must survive in a
       form asyncpg understands.
    """
    if database_url.startswith("postgres://"):
        database_url = "postgresql+asyncpg://" + database_url.removeprefix("postgres://")
    elif database_url.startswith("postgresql://"):
        database_url = "postgresql+asyncpg://" + database_url.removeprefix("postgresql://")

    parsed = urlparse(database_url)
    if parsed.query:
        params = parse_qs(parsed.query)
        if "sslmode" in params:
            sslmode = params.pop("sslmode")[0]
            # asyncpg accepts: true / false / require / verify-ca / verify-full.
            params["ssl"] = "true" if sslmode in {"disable", "allow", "prefer"} else sslmode
        new_query = urlencode({k: v[0] for k, v in params.items()})
        parsed = parsed._replace(query=new_query)
        database_url = urlunparse(parsed)
    return database_url


engine = create_async_engine(
    async_database_url(get_settings().database_url), pool_pre_ping=True
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db():
    async with SessionLocal() as session:
        yield session