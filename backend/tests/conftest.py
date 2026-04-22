from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401
from app.db.base import Base


@pytest.fixture
def db_session() -> Session:
    database_url = os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://osemosys:osemosys@db:5432/osemosys",
    )
    schema_name = f"test_{uuid.uuid4().hex}"
    engine = create_engine(
        database_url,
        execution_options={
            "schema_translate_map": {"core": schema_name, "osemosys": schema_name}
        },
    )
    try:
        with engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))
        Base.metadata.create_all(engine)

        SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()
            Base.metadata.drop_all(engine)
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE'))
        engine.dispose()
