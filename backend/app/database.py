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
# Render and some hosts still issue postgres:// URLs.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://") :]


engine = create_engine(
    DATABASE_URL
)


SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


Base = declarative_base()
