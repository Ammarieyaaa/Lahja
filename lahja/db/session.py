"""Engine/session setup. Swapping SQLite for Postgres is a change of LAHJA_DB_URL."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from lahja.db.models import Base


def make_session_factory(db_url: str) -> sessionmaker[Session]:
    engine = create_engine(db_url)
    # MVP: create tables on startup. A schema change later means adding Alembic.
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)
