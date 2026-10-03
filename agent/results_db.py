"""
SQLite store for scored postings. The alert pipeline, FastAPI layer and
dashboard will all read from here later (see the `notified` column).
"""
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from agent import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS matches (
    posting_id TEXT PRIMARY KEY,
    title TEXT, company TEXT, location TEXT, source TEXT, url TEXT,
    score INTEGER, decision TEXT,
    matched_skills TEXT, missing_skills TEXT, top_gap TEXT, reasoning TEXT,
    pitch TEXT, suggested_bullets TEXT,
    notified INTEGER DEFAULT 0,
    scored_at TEXT
)
"""


@contextmanager
def _db():
    path = os.path.abspath(settings.MATCHES_DB_PATH)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def scored_ids() -> set[str]:
    with _db() as conn:
        return {r["posting_id"] for r in conn.execute("SELECT posting_id FROM matches")}


def save_result(state: dict) -> None:
    p = state["posting"]
    a = state.get("assessment", {})
    with _db() as conn:
        conn.execute(
            """
            INSERT INTO matches (posting_id, title, company, location, source, url,
                                 score, decision, matched_skills, missing_skills,
                                 top_gap, reasoning, pitch, suggested_bullets, scored_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(posting_id) DO UPDATE SET
                score=excluded.score, decision=excluded.decision,
                matched_skills=excluded.matched_skills, missing_skills=excluded.missing_skills,
                top_gap=excluded.top_gap, reasoning=excluded.reasoning,
                pitch=excluded.pitch, suggested_bullets=excluded.suggested_bullets,
                scored_at=excluded.scored_at
            """,
            (
                p["posting_id"], p.get("title"), p.get("company"), p.get("location"),
                p.get("source"), p.get("url"),
                state.get("score"), state.get("decision"),
                json.dumps(a.get("matched_skills", [])), json.dumps(a.get("missing_skills", [])),
                a.get("top_gap"), a.get("reasoning"),
                state.get("pitch"), json.dumps(state.get("suggested_bullets", [])),
                datetime.now(timezone.utc).isoformat(),
            ),
        )


def list_matches(min_score: int = 0, limit: int = 50) -> list[dict]:
    with _db() as conn:
        rows = conn.execute(
            "SELECT * FROM matches WHERE score >= ? ORDER BY score DESC LIMIT ?",
            (min_score, limit),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        for k in ("matched_skills", "missing_skills", "suggested_bullets"):
            d[k] = json.loads(d[k] or "[]")
        out.append(d)
    return out
