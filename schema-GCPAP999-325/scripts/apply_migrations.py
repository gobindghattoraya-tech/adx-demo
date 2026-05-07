#!/usr/bin/env python3
"""
apply_migrations.py
-------------------
Applies all V00X SQL migration scripts in order to the adx_exchange database
via the Cloud SQL Auth Proxy (running on 127.0.0.1:15432).

Usage:
    # Start the proxy first:
    ./cloud-sql-proxy sbx-ag-build-adx-7i0q-1:europe-west2:ag-adx-postgres \
        --private-ip --port 15432 \
        --credentials-file /path/to/key.json &

    # Then run this script:
    export DB_PASSWORD=<postgres_password>
    python3 scripts/apply_migrations.py

Follows SRP: each function does exactly one thing.
DRY: connection logic is centralised in one factory function.
"""

import os
import sys
import logging
from pathlib import Path

import pg8000.native

# ── Configuration ────────────────────────────────────────────────────────────

PROXY_HOST   = "127.0.0.1"
PROXY_PORT   = 15432
DB_USER      = "postgres"
DB_PASSWORD  = os.environ.get("DB_PASSWORD", "")
TARGET_DB    = "adx_exchange"
MIGRATIONS_DIR = Path(__file__).parent.parent / "migrations"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ── Connection factory (DRY) ─────────────────────────────────────────────────

def make_connection(db: str = "postgres") -> pg8000.native.Connection:
    """Return a pg8000 native connection to the Cloud SQL Auth Proxy."""
    return pg8000.native.Connection(
        user=DB_USER,
        password=DB_PASSWORD,
        host=PROXY_HOST,
        port=PROXY_PORT,
        database=db,
        ssl_context=False,
    )


# ── Database bootstrap ────────────────────────────────────────────────────────

def create_database_if_not_exists() -> None:
    """Create the adx_exchange database if it does not already exist."""
    conn = make_connection("postgres")
    try:
        rows = conn.run(
            "SELECT 1 FROM pg_database WHERE datname = :db", db=TARGET_DB
        )
        if rows:
            log.info("Database '%s' already exists — skipping creation.", TARGET_DB)
        else:
            # autocommit required for CREATE DATABASE
            conn.autocommit = True
            conn.run(f'CREATE DATABASE "{TARGET_DB}"')
            log.info("✅ Database '%s' created.", TARGET_DB)
    finally:
        conn.close()


def enable_pgcrypto() -> None:
    """Ensure pgcrypto extension is available (required for gen_random_uuid())."""
    conn = make_connection(TARGET_DB)
    try:
        conn.run('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
        log.info("✅ pgcrypto extension enabled.")
    finally:
        conn.close()


# ── Migration runner ──────────────────────────────────────────────────────────

def get_migration_files() -> list[Path]:
    """Return all V00X migration files, sorted by version number."""
    files = sorted(MIGRATIONS_DIR.glob("V*.sql"))
    if not files:
        log.error("No migration files found in %s", MIGRATIONS_DIR)
        sys.exit(1)
    return files


def apply_migrations() -> None:
    """Apply each migration script in order. Idempotent via IF NOT EXISTS guards."""
    conn = make_connection(TARGET_DB)
    try:
        for migration_path in get_migration_files():
            sql = migration_path.read_text()
            log.info("Applying: %s ...", migration_path.name)
            try:
                conn.run(sql)
                log.info("✅ Applied: %s", migration_path.name)
            except Exception as exc:
                log.error("❌ Failed on %s: %s", migration_path.name, exc)
                raise
    finally:
        conn.close()


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    if not DB_PASSWORD:
        log.error("DB_PASSWORD environment variable is not set.")
        sys.exit(1)

    log.info("=== adx_exchange Schema Migration ===")
    log.info("Proxy : %s:%s", PROXY_HOST, PROXY_PORT)
    log.info("Target DB: %s", TARGET_DB)

    create_database_if_not_exists()
    enable_pgcrypto()
    apply_migrations()

    log.info("\n🎉 All migrations applied successfully to '%s'!", TARGET_DB)


if __name__ == "__main__":
    main()
