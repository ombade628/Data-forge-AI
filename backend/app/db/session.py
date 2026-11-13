from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.core.config import get_settings


def _prepare_async_url(database_url: str) -> tuple[str, dict]:
    """Rewrite the URL for asyncpg and return (url, connect_args).

    asyncpg rejects ``sslmode`` and ``channel_binding`` as connect kwargs,
    so we strip them from the URL and configure SSL via connect_args.
    """
    if database_url.startswith("postgres://"):
        database_url = "postgresql+asyncpg://" + database_url.removeprefix("postgres://")
    elif database_url.startswith("postgresql://"):
        database_url = "postgresql+asyncpg://" + database_url.removeprefix("postgresql://")

    parsed = urlparse(database_url)
    connect_args: dict = {}

    if parsed.query:
        params = parse_qs(parsed.query)
        # Strip everything asyncpg does not accept as a kwarg.
        params.pop("sslmode", None)
        params.pop("channel_binding", None)

        # Determine SSL from the original query before stripping.
        raw_query = parsed.query
        needs_ssl = "sslmode=require" in raw_query or "ssl=require" in raw_query or "neon.tech" in database_url

        new_query = urlencode({k: v[0] for k, v in params.items()})
        parsed = parsed._replace(query=new_query)
        database_url = urlunparse(parsed)

        if needs_ssl:
            connect_args["ssl"] = "require"

    return database_url, connect_args


_url, _connect_args = _prepare_async_url(get_settings().database_url)

engine = create_async_engine(
    _url,
    pool_pre_ping=True,
    connect_args=_connect_args,
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db():
    async with SessionLocal() as session:
        yield session