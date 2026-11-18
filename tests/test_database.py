import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from app.database import normalize_database_url

ROOT = Path(__file__).resolve().parents[1]


def run_migrations(database_url: str):
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(ROOT / "alembic.ini"), "upgrade", "head"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_missing_database_url_uses_absolute_sqlite_path():
    url = normalize_database_url(None)
    assert url.startswith("sqlite:///")
    assert Path(url.removeprefix("sqlite:///")).is_absolute()


def test_blank_database_url_uses_absolute_sqlite_path():
    url = normalize_database_url("   ")
    assert url.startswith("sqlite:///")
    assert Path(url.removeprefix("sqlite:///")).is_absolute()


def test_postgresql_url_normalization():
    assert normalize_database_url("postgres://user:pass@host/db") == (
        "postgresql+psycopg://user:pass@host/db"
    )
    assert normalize_database_url("postgresql://user:pass@host/db") == (
        "postgresql+psycopg://user:pass@host/db"
    )


def test_migration_creates_missing_tables_and_unique_index(tmp_path):
    db_path = tmp_path / "fresh.sqlite"
    result = run_migrations(f"sqlite:///{db_path}")
    assert result.returncode == 0, result.stderr

    with sqlite3.connect(db_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert {"fixtures", "predictions", "alembic_version"} <= tables
        indexes = connection.execute(
            "PRAGMA index_list('fixtures')"
        ).fetchall()
        assert any(row[1] == "ix_fixtures_external_id" and row[2] == 1 for row in indexes)


def test_migration_adds_missing_column_to_existing_fixtures_table(tmp_path):
    db_path = tmp_path / "legacy.sqlite"
    with sqlite3.connect(db_path) as connection:
        connection.execute("""
            CREATE TABLE fixtures (
                id INTEGER PRIMARY KEY,
                home_team VARCHAR(150) NOT NULL,
                away_team VARCHAR(150) NOT NULL,
                league VARCHAR(150),
                country VARCHAR(100),
                kickoff DATETIME NOT NULL,
                status VARCHAR(50)
            )
        """)

    result = run_migrations(f"sqlite:///{db_path}")
    assert result.returncode == 0, result.stderr

    with sqlite3.connect(db_path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info('fixtures')")}
        assert "external_id" in columns


def test_migration_rejects_duplicate_external_ids(tmp_path):
    db_path = tmp_path / "duplicates.sqlite"
    with sqlite3.connect(db_path) as connection:
        connection.execute("""
            CREATE TABLE fixtures (
                id INTEGER PRIMARY KEY,
                external_id INTEGER,
                home_team VARCHAR(150) NOT NULL,
                away_team VARCHAR(150) NOT NULL,
                league VARCHAR(150),
                country VARCHAR(100),
                kickoff DATETIME NOT NULL,
                status VARCHAR(50)
            )
        """)
        connection.execute(
            "INSERT INTO fixtures (external_id, home_team, away_team, kickoff) VALUES (7, 'A', 'B', '2026-01-01')"
        )
        connection.execute(
            "INSERT INTO fixtures (external_id, home_team, away_team, kickoff) VALUES (7, 'C', 'D', '2026-01-02')"
        )

    result = run_migrations(f"sqlite:///{db_path}")
    assert result.returncode != 0
    assert "duplicate external_id value" in result.stderr

def test_migration_runs_on_postgresql_when_configured():
    database_url = os.getenv("POSTGRES_TEST_DATABASE_URL")
    if not database_url:
        return

    result = run_migrations(database_url)
    assert result.returncode == 0, result.stderr

    from sqlalchemy import create_engine, inspect

    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        assert inspector.has_table("fixtures")
        assert inspector.has_table("predictions")
        indexes = inspector.get_indexes("fixtures")
        assert any(
            index["name"] == "ix_fixtures_external_id" and index.get("unique")
            for index in indexes
        )
    finally:
        engine.dispose()
