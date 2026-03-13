"""SQLAlchemy engine and session factory helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from .models import Base


def create_engine_from_config(db_config: Dict):
    """Create a SQLAlchemy engine based on the app's database config.

    Expected config shape:
        {
            "type": "sqlite" | "postgres",
            "path": "data/trading_data.db",  # for sqlite
            "url": "postgresql+psycopg2://user:pass@host:5432/dbname"  # for postgres
        }
    """
    db_type = (db_config or {}).get("type", "sqlite")

    if db_type == "sqlite":
        db_path = db_config.get("path", "data/trading_data.db")
        # Ensure directory exists for SQLite
        db_file = Path(db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)
        # Use absolute path for SQLite
        url = f"sqlite:///{db_file.resolve()}"
    elif db_type in {"postgres", "postgresql"}:
        url = db_config.get("url")
        if not url:
            raise ValueError("database.url must be set in config for PostgreSQL")
    else:
        raise ValueError(f"Unsupported database type: {db_type}")

    engine = create_engine(url, future=True)
    # Create tables if they don't exist
    Base.metadata.create_all(bind=engine)
    return engine


def get_sessionmaker(engine) -> sessionmaker:
    """Return a configured sessionmaker for the given engine."""
    return sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=Session)


