import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base


# Local docker-compose maps host 5433 → container 5432.
_DEFAULT_DATABASE_URL = (
    "postgresql://insightpilot:insightpilot@localhost:5433/insightpilot"
)

DATABASE_URL = os.getenv("DATABASE_URL", _DEFAULT_DATABASE_URL).strip() or (
    _DEFAULT_DATABASE_URL
)


def _normalize_database_url(url: str) -> str:
    """Prefer psycopg2 (in requirements) over psycopg3.

    Render connection strings may be postgres:// or postgresql+psycopg://.
    """
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql+psycopg://"):
        url = "postgresql+psycopg2://" + url[len("postgresql+psycopg://") :]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg2://" + url[len("postgresql://") :]
    return url


DATABASE_URL = _normalize_database_url(DATABASE_URL)


engine = create_engine(
    DATABASE_URL
)


SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


Base = declarative_base()
