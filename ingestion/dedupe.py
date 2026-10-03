"""
Dedup layer: filters out postings whose posting_id already exists in the
vector store, so scheduled re-runs only ever embed genuinely new listings.
This is what makes repeated polling cheap instead of re-processing
everything every cycle.
"""
from ingestion.normalize import Posting
from vectorstore.chroma_client import JobVectorStore


def filter_new_postings(postings: list[Posting], store: JobVectorStore) -> list[Posting]:
    seen_ids = store.existing_ids()
    new_postings = [p for p in postings if p.posting_id not in seen_ids]

    # also dedupe within this batch itself (JSearch + Adzuna can return the same job)
    unique = {}
    for p in new_postings:
        unique[p.posting_id] = p

    skipped = len(postings) - len(unique)
    if skipped:
        print(f"[dedupe] Skipped {skipped} already-seen or duplicate postings.")
    return list(unique.values())
