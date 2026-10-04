"""
One-time migration: copies every row from the old local data/matches.db
(SQLite) into the new Neon Postgres database, preserving your status and
notes. Safe to run more than once - uses the same ON CONFLICT upsert logic
as save_result, so re-running just overwrites with the same data.

Usage:
    python -m scripts.migrate_sqlite_to_postgres
"""
import os
import sqlite3

import psycopg2
import psycopg2.extras

from agent import settings
from agent.results_db import SCHEMA, NEW_COLUMNS

OLD_SQLITE_PATH = os.getenv("MATCHES_DB_PATH", "./data/matches.db")

COLUMNS = [
    "posting_id", "title", "company", "location", "source", "url",
    "score", "decision", "matched_skills", "missing_skills", "top_gap", "reasoning",
    "pitch", "suggested_bullets", "seniority", "tech_stack",
    "salary_min", "salary_max", "status", "notes", "status_updated_at", "scored_at",
]


def main():
    if not os.path.exists(OLD_SQLITE_PATH):
        print(f"No SQLite file found at {OLD_SQLITE_PATH} - nothing to migrate.")
        return
    if not settings.DATABASE_URL:
        print("DATABASE_URL is not set. Add your Neon pooled connection string to .env first.")
        return

    sconn = sqlite3.connect(OLD_SQLITE_PATH)
    sconn.row_factory = sqlite3.Row
    rows = sconn.execute("SELECT * FROM matches").fetchall()
    sconn.close()

    if not rows:
        print("SQLite matches table is empty - nothing to migrate.")
        return

    pconn = psycopg2.connect(settings.DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    with pconn, pconn.cursor() as cur:
        cur.execute(SCHEMA)
        for col, decl in NEW_COLUMNS.items():
            cur.execute(f"ALTER TABLE matches ADD COLUMN IF NOT EXISTS {col} {decl}")

        placeholders = ", ".join(["%s"] * len(COLUMNS))
        col_list = ", ".join(COLUMNS)
        update_list = ", ".join(f"{c}=EXCLUDED.{c}" for c in COLUMNS if c != "posting_id")

        migrated = 0
        for r in rows:
            values = [r[c] if c in r.keys() else None for c in COLUMNS]
            cur.execute(
                f"INSERT INTO matches ({col_list}) VALUES ({placeholders}) "
                f"ON CONFLICT (posting_id) DO UPDATE SET {update_list}",
                values,
            )
            migrated += 1

    pconn.close()
    print(f"Migrated {migrated} rows from {OLD_SQLITE_PATH} into Neon.")
    print("Your status and notes came along for the ride - nothing was lost.")


if __name__ == "__main__":
    main()