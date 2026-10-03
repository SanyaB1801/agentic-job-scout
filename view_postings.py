"""
Quick inspection script — prints every posting currently stored in Chroma.
Not part of the pipeline; just a debugging/sanity-check tool.

Usage:
    python view_postings.py
    python view_postings.py --limit 5
"""
import argparse
from vectorstore.chroma_client import JobVectorStore


def view_all(limit: int = None):
    store = JobVectorStore()
    total = store.count()
    print(f"Total postings in store: {total}\n")

    result = store.collection.get(
        limit=limit,
        include=["metadatas", "documents"],
    )

    ids = result.get("ids", [])
    metadatas = result.get("metadatas", [])

    for i, (pid, meta) in enumerate(zip(ids, metadatas), start=1):
        print(f"{i}. {meta.get('title', '(no title)')}")
        print(f"   Company:  {meta.get('company', '-')}")
        print(f"   Location: {meta.get('location', '-')}")
        print(f"   Source:   {meta.get('source', '-')}")
        print(f"   Salary:   {meta.get('salary') or '-'}")
        print(f"   Posted:   {meta.get('posted_date') or '-'}")
        print(f"   URL:      {meta.get('url', '-')}")
        print(f"   ID:       {pid}")
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="View postings stored in Chroma.")
    parser.add_argument("--limit", type=int, default=None, help="Max postings to show (default: all)")
    args = parser.parse_args()

    view_all(args.limit)
