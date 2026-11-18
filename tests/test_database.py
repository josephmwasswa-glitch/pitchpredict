import importlib
import os
import sys


def load_database_module(monkeypatch, database_url):
    if database_url is None:
        monkeypatch.delenv("DATABASE_URL", raising=False)
    else:
        monkeypatch.setenv("DATABASE_URL", database_url)

    sys.modules.pop("app.database", None)
    return importlib.import_module("app.database")


def test_legacy_postgres_url_is_normalized(monkeypatch):
    module = load_database_module(
        monkeypatch,
        "postgres://user:password@localhost:5432/database",
    )

    assert module.DATABASE_URL == (
        "postgresql://user:password@localhost:5432/database"
    )
    assert module.engine.url.drivername == "postgresql"


def test_postgresql_url_is_unchanged(monkeypatch):
    database_url = "postgresql://user:password@localhost:5432/database"
    module = load_database_module(monkeypatch, database_url)

    assert module.DATABASE_URL == database_url
    assert module.engine.url.drivername == "postgresql"


def test_missing_database_url_is_rejected(monkeypatch):
    try:
        load_database_module(monkeypatch, None)
    except RuntimeError as error:
        assert str(error) == "DATABASE_URL environment variable is not configured"
    else:
        raise AssertionError("Expected RuntimeError for missing DATABASE_URL")
