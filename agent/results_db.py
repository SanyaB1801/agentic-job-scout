"""
SQLite store for scored postings. Two kinds of fields live here:

  - AGENT fields (score, decision, seniority, tech_stack, ...) - overwritten
    every time a posting is (re)scored.
  - USER fields (status, notes) - your own application tracking. Rescoring
    NEVER touches these, so re-running the agent won't wipe out that you
    marked something "Applied".
"""
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from agent import settings
from agent.salary import parse_salary

SCHEMA = """
CREATE TABLE IF NOT EXISTS matches (
    posting_id TEXT PRIMARY KEY,
    title TEXT, company TEXT, location TEXT, source TEXT, url TEXT,
    score INTEGER, decision TEXT,
    matched_skills TEXT, missing_skills TEXT, top_gap TEXT, reasoning TEXT,
    pitch TEXT, suggested_bullets TEXT,
    scored_at TEXT
)
"""

# Columns added after the original schema. Each is added via ALTER TABLE if
# missing, so existing matches.db files upgrade in place with no data loss.
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
    path = os.path.abspath(settings.MATCHES_DB_PATH)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(SCHEMA)
        existing = {row[1] for row in conn.execute("PRAGMA table_info(matches)")}
        for col, decl in NEW_COLUMNS.items():
            if col not in existing:
                conn.execute(f"ALTER TABLE matches ADD COLUMN {col} {decl}")
        yield conn
        conn.commit()
    finally:
        conn.close()


def scored_ids() -> set[str]:
    with _db() as conn:
        return {r["posting_id"] for r in conn.execute("SELECT posting_id FROM matches")}


def save_result(state: dict) -> None:
    """Writes agent-derived fields only. Never touches status/notes, so a
    rescore can't accidentally erase that you already applied."""
    p = state["posting"]
    a = state.get("assessment", {})
    smin, smax = parse_salary(p.get("salary"))

    with _db() as conn:
        conn.execute(
            """
            INSERT INTO matches (posting_id, title, company, location, source, url,
                                 score, decision, matched_skills, missing_skills,
                                 top_gap, reasoning, pitch, suggested_bullets,
                                 seniority, tech_stack, salary_min, salary_max, scored_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(posting_id) DO UPDATE SET
                score=excluded.score, decision=excluded.decision,
                matched_skills=excluded.matched_skills, missing_skills=excluded.missing_skills,
                top_gap=excluded.top_gap, reasoning=excluded.reasoning,
                pitch=excluded.pitch, suggested_bullets=excluded.suggested_bullets,
                seniority=excluded.seniority, tech_stack=excluded.tech_stack,
                salary_min=excluded.salary_min, salary_max=excluded.salary_max,
                scored_at=excluded.scored_at
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
    with _db() as conn:
        if status is not None:
            conn.execute(
                "UPDATE matches SET status=?, status_updated_at=? WHERE posting_id=?",
                (status, datetime.now(timezone.utc).isoformat(), posting_id),
            )
        if notes is not None:
            conn.execute("UPDATE matches SET notes=? WHERE posting_id=?", (notes, posting_id))


def counts() -> dict:
    with _db() as conn:
        decision_rows = conn.execute(
            "SELECT decision, COUNT(*) AS n FROM matches GROUP BY decision"
        ).fetchall()
        status_rows = conn.execute(
            "SELECT COALESCE(status, 'new') AS status, COUNT(*) AS n FROM matches GROUP BY status"
        ).fetchall()

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
    query = "SELECT * FROM matches WHERE score >= ?"
    params: list = [min_score]

    if decision and decision != "all":
        query += " AND decision = ?"
        params.append(decision)

    if status and status != "all":
        query += " AND COALESCE(status, 'new') = ?"
        params.append(status)

    if seniority and seniority != "all":
        query += " AND seniority = ?"
        params.append(seniority)

    if tech:
        query += " AND tech_stack LIKE ?"
        params.append(f"%{tech}%")

    if salary_min is not None:
        # posting's upper band must at least reach what you're asking for
        query += " AND (salary_max IS NULL OR salary_max >= ?)"
        params.append(salary_min)

    if salary_max is not None:
        # posting's lower band must not exceed your ceiling
        query += " AND (salary_min IS NULL OR salary_min <= ?)"
        params.append(salary_max)

    if search:
        query += " AND (title LIKE ? OR company LIKE ?)"
        like = f"%{search}%"
        params += [like, like]

    order_col = "salary_max DESC" if order_by == "salary" else "score DESC"
    query += f" ORDER BY {order_col} LIMIT ?"
    params.append(limit)

    with _db() as conn:
        rows = conn.execute(query, params).fetchall()

    out = []
    for r in rows:
        d = dict(r)
        for k in ("matched_skills", "missing_skills", "suggested_bullets", "tech_stack"):
            d[k] = json.loads(d[k] or "[]")
        d["status"] = d["status"] or "new"
        out.append(d)
    return out