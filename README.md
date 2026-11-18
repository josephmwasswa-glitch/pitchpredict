# PitchPredict

AI-powered worldwide football fixtures and predictions API.

PitchPredict is being built to collect fixtures, generate match probabilities, and publish daily football predictions for markets such as:

- 1X2 (home win, draw, away win)
- Both Teams To Score (BTTS)
- Over/Under 2.5 goals
- Double chance

## Project status

This repository currently contains a FastAPI backend foundation. Fixture ingestion, prediction generation, scheduling, frontend pages, and production integrations are still being developed. Do not treat the platform as production-ready until those features and deployment checks are complete.

## Run locally

Requirements: Python 3.12+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

On Windows, activate the environment with `.venv\\Scripts\\activate`.

Open the API documentation at `http://127.0.0.1:8000/docs` and health check at `http://127.0.0.1:8000/health`.

Without `DATABASE_URL`, local development uses a SQLite database file in the project directory. For PostgreSQL, set `DATABASE_URL` to a complete PostgreSQL connection URL. The application supports Render-style `postgres://` and `postgresql://` URLs and normalizes them for psycopg.

## Database migrations

Schema changes are managed with Alembic:

```bash
alembic upgrade head
```

The migration in this branch adopts the existing schema, preserves fixture rows, ensures `fixtures.external_id` exists, and creates a unique index for that column. It stops with an explicit error if duplicate non-null external IDs prevent the unique index from being created.

## GitHub Actions checks

The Tests workflow runs the automated test suite against a temporary PostgreSQL 16 service on pushes and pull requests.

A separate manual workflow validates the migration against the Render staging database. It requires these GitHub Actions repository secrets:

- `RENDER_API_KEY`: a Render API key with permission to update the staging PostgreSQL IP allowlist.
- `RENDER_EXTERNAL_DATABASE_URL`: the complete External Database URL copied from the Render PostgreSQL resource. Do not enter only the database name. Do not commit or share this URL.

The manual workflow validates the URL format before opening database access. During validation it temporarily allows only the GitHub runner's single public IP, applies the Alembic migration, checks the expected tables and unique index, and then attempts to restore the empty IP allowlist.

The Render staging migration is **not yet verified**. Keep the Alembic pull request in draft and do not merge it until the manual Render workflow succeeds and its schema checks pass.

## Important safety notes

- Never commit database URLs, passwords, API keys, or other secrets.
- Use a separate staging database for migration validation.
- Back up important data before applying schema changes to production.
- A passing CI test against its temporary PostgreSQL service does not prove the Render staging database migration has passed.
