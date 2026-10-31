"""Database engine, session management, and lifecycle.

Supports SQLite by default for zero-configuration local execution,
with full PostgreSQL compatibility via DATABASE_URL environment variable.
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

logger = logging.getLogger("enervision.db")


class Base(DeclarativeBase):
    pass


def get_default_db_url(repo_root: Path | None = None) -> str:
    if repo_root is None:
        repo_root = Path(__file__).resolve().parent.parent.parent
    data_dir = repo_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "enervision.db"
    return f"sqlite:///{db_path.as_posix()}"


class Database:
    def __init__(self, db_url: str | None = None, repo_root: Path | None = None) -> None:
        url = db_url or os.getenv("DATABASE_URL") or get_default_db_url(repo_root)
        self.url = url
        is_sqlite = url.startswith("sqlite")
        connect_args = {"check_same_thread": False} if is_sqlite else {}
        self.engine = create_engine(
            url,
            connect_args=connect_args,
            pool_pre_ping=True,
            echo=False,
        )
        self.session_factory = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine,
        )

    def create_tables(self) -> None:
        """Create all tables defined on Base."""
        from backend.db import models  # noqa: F401
        Base.metadata.create_all(bind=self.engine)
        logger.info("Database tables initialized on %s", self.url)

    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """Provide a transactional scope around a series of operations."""
        sess: Session = self.session_factory()
        try:
            yield sess
            sess.commit()
        except Exception:
            sess.rollback()
            raise
        finally:
            sess.close()
