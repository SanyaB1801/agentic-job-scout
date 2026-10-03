"""
Orchestrates one full ingestion cycle:

    fetch (JSearch + Adzuna) -> dedupe -> embed -> upsert into Chroma

Run directly for a one-off pull:
    python -m ingestion.pipeline --query "AI Engineer" --location "Delhi NCR"

Later, scheduler.py calls run_ingestion_cycle() on a timer for the
"real-time" behavior — this file doesn't need to change for that.
"""
import argparse
from config import settings
from ingestion.sources.jsearch import fetch_jsearch_postings
from ingestion.sources.adzuna import fetch_adzuna_postings
from ingestion.dedupe import filter_new_postings
from ingestion.embed import embed_postings
from vectorstore.chroma_client import JobVectorStore


def run_ingestion_cycle(query: str, location: str = "") -> int:
    """Runs one full cycle and returns the number of new postings added."""
    settings.validate_for_ingestion()
    store = JobVectorStore()

    raw_postings = []
    raw_postings += fetch_jsearch_postings(query, location)
    raw_postings += fetch_adzuna_postings(query, location)

    if not raw_postings:
        print("[pipeline] No postings fetched from any source this cycle.")
        return 0

    new_postings = filter_new_postings(raw_postings, store)
    if not new_postings:
        print("[pipeline] Nothing new this cycle — all postings already seen.")
        return 0

    embeddings = embed_postings(new_postings)
    store.upsert(new_postings, embeddings)

    print(
        f"[pipeline] Added {len(new_postings)} new postings. "
        f"Store now holds {store.count()} total."
    )
    return len(new_postings)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run one Career Copilot ingestion cycle.")
    parser.add_argument("--query", required=True, help='e.g. "AI Engineer"')
    parser.add_argument("--location", default="", help='e.g. "Delhi NCR" (optional)')
    args = parser.parse_args()

    run_ingestion_cycle(args.query, args.location)
