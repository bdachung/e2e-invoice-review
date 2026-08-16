"""SQLite engine and session construction."""

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

SQLITE_BUSY_TIMEOUT_SECONDS = 10


class Base(DeclarativeBase):
    pass


def build_database(database_url: str) -> tuple[Engine, sessionmaker]:
    connect_args = (
        {"check_same_thread": False, "timeout": SQLITE_BUSY_TIMEOUT_SECONDS}
        if database_url.startswith("sqlite")
        else {}
    )
    engine = create_engine(database_url, connect_args=connect_args)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)
