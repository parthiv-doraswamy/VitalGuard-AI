import os
import pytest
from sqlalchemy import create_engine, text
from app.storage import dispose_engines

# PostgreSQL tests run only when a disposable test database is provided, e.g.
# VITALGUARD_TEST_POSTGRES_URL=postgresql+psycopg://user@127.0.0.1:5432/vitalguard_test
# The schema of that database is dropped and recreated before each test.
POSTGRES_TEST_URL = os.getenv("VITALGUARD_TEST_POSTGRES_URL", "").strip()


@pytest.fixture(autouse=True)
def _isolate_engines():
    # Cached pools are keyed by URL; dispose them so tests never share connections.
    dispose_engines()
    yield
    dispose_engines()


def reset_postgres_schema(url: str) -> None:
    engine = create_engine(url)
    try:
        with engine.begin() as connection:
            connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            connection.execute(text("CREATE SCHEMA public"))
    finally:
        engine.dispose()


@pytest.fixture(params=["sqlite", "postgresql"])
def database(request, tmp_path, monkeypatch):
    """Point the app at an empty SQLite file or an empty PostgreSQL schema; yields the backend name."""
    if request.param == "postgresql":
        if not POSTGRES_TEST_URL:
            if os.getenv("VITALGUARD_TEST_REQUIRE_POSTGRES", "").lower() == "true":
                pytest.fail("VITALGUARD_TEST_REQUIRE_POSTGRES is set but VITALGUARD_TEST_POSTGRES_URL is missing")
            pytest.skip("VITALGUARD_TEST_POSTGRES_URL not set")
        reset_postgres_schema(POSTGRES_TEST_URL)
        monkeypatch.setenv("DATABASE_URL", POSTGRES_TEST_URL)
    else:
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setenv("VITALGUARD_DB_PATH", str(tmp_path / "persistence.sqlite3"))
    yield request.param
