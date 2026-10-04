"""
Postgres-backed store for scored postings (hosted on Neon, free tier).

This is a drop-in replacement for the original SQLite version: every public
function has the exact same name and signature, so app.py and
score_postings.py did not need to change at all.

Two kinds of fields live here:
  - AGENT fields (score, decision, seniority, tech_stack, ...) - overwritten
    every time a posting is (re)scored.
  - USER fields (status, notes) - your own application tracking. Rescoring
    NEVER touches these, so re-running the agent won't wipe out that you
    marked something "Applied".

Requires DATABASE_URL in .env - the POOLED connection string from your Neon
project (hostname contains "-pooler"), since serverless hosts open many
short-lived connections.
"""
import json
from contextlib import contextmanager
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras

from agent import settings
from agent.salary import parse_salary

SCHEMA = """
CREATE TABLE IF NOT EXISTS matches (
    posting_id TEXT PRIMARY KEY,
    title TEXT, company TEXT, location TEXT, source TEXT, url TEXT,
    score INTEGER, decision TEXT,
    matched_skills TEXT, missing_skills TEXT, top_gap TEXT, reasoning TEXT,
    pitch TEXT, suggested_bullets TEXT,
    seniority TEXT, tech_stack TEXT,
    salary_min INTEGER, salary_max INTEGER,
    status TEXT DEFAULT 'new', notes TEXT, status_updated_at TEXT,
    scored_at TEXT
)
"""

# Added via ALTER TABLE ADD COLUMN IF NOT EXISTS so an older matches table
# (from before these fields existed) upgrades in place with no data loss.
NEW_COLUMNS = {
    "seniority": "TEXT",
    "tech_stack": "TEXT",
    "salary_min": "INTEGER",
    "salary_max": "INTEGER",
    "status": "TEXT DEFAULT 'new'",
    "notes": "TEXT",
    "status_updated_at": "TEXT",
}

STATUSES = ["new", "applied", "interviewing", "offer", "rejected", "not_interested"]


@contextmanager
def _db():
    if not settings.DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set. Add your Neon pooled connection string to .env.")
    conn = psycopg2.connect(settings.DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        with conn.cursor() as cur:
            cur.execute(SCHEMA)
            for col, decl in NEW_COLUMNS.items():
                cur.execute(f"ALTER TABLE matches ADD COLUMN IF NOT EXISTS {col} {decl}")
        yield conn
        conn.commit()
    finally:
        conn.close()


def scored_ids() -> set[str]:
    with _db() as conn, conn.cursor() as cur:
        cur.execute("SELECT posting_id FROM matches")
        return {r["posting_id"] for r in cur.fetchall()}


def save_result(state: dict) -> None:
    """Writes agent-derived fields only. Never touches status/notes, so a
    rescore can't accidentally erase that you already applied."""
    p = state["posting"]
    a = state.get("assessment", {})
    smin, smax = parse_salary(p.get("salary"))

    with _db() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO matches (posting_id, title, company, location, source, url,
                                 score, decision, matched_skills, missing_skills,
                                 top_gap, reasoning, pitch, suggested_bullets,
                                 seniority, tech_stack, salary_min, salary_max, scored_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (posting_id) DO UPDATE SET
                score=EXCLUDED.score, decision=EXCLUDED.decision,
                matched_skills=EXCLUDED.matched_skills, missing_skills=EXCLUDED.missing_skills,
                top_gap=EXCLUDED.top_gap, reasoning=EXCLUDED.reasoning,
                pitch=EXCLUDED.pitch, suggested_bullets=EXCLUDED.suggested_bullets,
                seniority=EXCLUDED.seniority, tech_stack=EXCLUDED.tech_stack,
                salary_min=EXCLUDED.salary_min, salary_max=EXCLUDED.salary_max,
                scored_at=EXCLUDED.scored_at
            """,
            (
                p["posting_id"], p.get("title"), p.get("company"), p.get("location"),
                p.get("source"), p.get("url"),
                state.get("score"), state.get("decision"),
                json.dumps(a.get("matched_skills", [])), json.dumps(a.get("missing_skills", [])),
                a.get("top_gap"), a.get("reasoning"),
                state.get("pitch"), json.dumps(state.get("suggested_bullets", [])),
                a.get("seniority", "Unknown"), json.dumps(a.get("tech_stack", [])),
                smin, smax,
                datetime.now(timezone.utc).isoformat(),
            ),
        )


def set_status(posting_id: str, status: str | None = None, notes: str | None = None) -> None:
    if status is not None and status not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}, got {status!r}")
    with _db() as conn, conn.cursor() as cur:
        if status is not None:
            cur.execute(
                "UPDATE matches SET status=%s, status_updated_at=%s WHERE posting_id=%s",
                (status, datetime.now(timezone.utc).isoformat(), posting_id),
            )
        if notes is not None:
            cur.execute("UPDATE matches SET notes=%s WHERE posting_id=%s", (notes, posting_id))


def counts() -> dict:
    with _db() as conn, conn.cursor() as cur:
        cur.execute("SELECT decision, COUNT(*) AS n FROM matches GROUP BY decision")
        decision_rows = cur.fetchall()
        cur.execute("SELECT COALESCE(status, 'new') AS status, COUNT(*) AS n FROM matches GROUP BY status")
        status_rows = cur.fetchall()

    decision_out = {"alert": 0, "review": 0, "discard": 0, "total": 0}
    for r in decision_rows:
        decision_out[r["decision"]] = r["n"]
        decision_out["total"] += r["n"]

    status_out = {s: 0 for s in STATUSES}
    for r in status_rows:
        status_out[r["status"]] = r["n"]

    return {"decision": decision_out, "status": status_out}


def list_matches(
    min_score: int = 0,
    limit: int = 100,
    decision: str | None = None,
    status: str | None = None,
    seniority: str | None = None,
    tech: str | None = None,
    salary_min: int | None = None,
    salary_max: int | None = None,
    search: str | None = None,
    order_by: str = "score",
) -> list[dict]:
    query = "SELECT * FROM matches WHERE score >= %s"
    params: list = [min_score]

    if decision and decision != "all":
        query += " AND decision = %s"
        params.append(decision)

    if status and status != "all":
        query += " AND COALESCE(status, 'new') = %s"
        params.append(status)

    if seniority and seniority != "all":
        query += " AND seniority = %s"
        params.append(seniority)

    if tech:
        query += " AND tech_stack ILIKE %s"
        params.append(f"%{tech}%")

    if salary_min is not None:
        query += " AND (salary_max IS NULL OR salary_max >= %s)"
        params.append(salary_min)

    if salary_max is not None:
        query += " AND (salary_min IS NULL OR salary_min <= %s)"
        params.append(salary_max)

    if search:
        query += " AND (title ILIKE %s OR company ILIKE %s)"
        like = f"%{search}%"
        params += [like, like]

    order_col = "salary_max DESC NULLS LAST" if order_by == "salary" else "score DESC"
    query += f" ORDER BY {order_col} LIMIT %s"
    params.append(limit)

    with _db() as conn, conn.cursor() as cur:
        cur.execute(query, params)
        rows = cur.fetchall()

    out = []
    for r in rows:
        d = dict(r)
        for k in ("matched_skills", "missing_skills", "suggested_bullets", "tech_stack"):
            d[k] = json.loads(d[k] or "[]")
        d["status"] = d["status"] or "new"
        out.append(d)
    return out