"""
Runs the LangGraph agent over postings stored in Chroma and saves results.

    python score_postings.py                  # score up to 10 unscored postings
    python score_postings.py --limit 20       # score more
    python score_postings.py --rescore        # re-score already-scored postings too
    python score_postings.py --show           # just print stored results, no LLM calls
    python score_postings.py --show --min-score 60
"""
import argparse
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows consoles choke on odd characters

from agent import results_db, settings
from vectorstore.chroma_client import JobVectorStore


def load_postings(store: JobVectorStore) -> list[dict]:
    res = store.collection.get(include=["metadatas", "documents"])
    postings = []
    for pid, meta, doc in zip(res["ids"], res["metadatas"], res["documents"]):
        postings.append(
            {
                "posting_id": pid,
                "title": meta.get("title", ""),
                "company": meta.get("company", ""),
                "location": meta.get("location", ""),
                "source": meta.get("source", ""),
                "url": meta.get("url", ""),
                "salary": meta.get("salary", ""),
                "description": doc,
            }
        )
    return postings


def preflight(store: JobVectorStore) -> bool:
    if not settings.GOOGLE_API_KEY:
        print("GOOGLE_API_KEY is missing. Add it to .env (free key: https://aistudio.google.com/apikey).")
        return False
    try:
        store.client.get_collection(settings.RESUME_COLLECTION)
    except Exception:
        print("Resume not indexed yet. Run first:  python -m agent.resume_index")
        return False
    return True


def run(limit: int, delay: float, rescore: bool) -> None:
    store = JobVectorStore()
    if not preflight(store):
        return

    from agent.graph import build_graph  # imported late so --show works without LLM deps

    postings = load_postings(store)
    done = set() if rescore else results_db.scored_ids()
    todo = [p for p in postings if p["posting_id"] not in done][:limit]

    print(f"{len(postings)} postings in store, {len(todo)} to score now (model: {settings.GEMINI_MODEL}).\n")
    if not todo:
        print("Nothing to score. Use --rescore to redo, or run the ingestion pipeline for new postings.")
        return

    graph = build_graph()
    failures_in_a_row = 0
    for i, p in enumerate(todo, start=1):
        try:
            result = graph.invoke({"posting": p})
        except Exception as e:
            failures_in_a_row += 1
            print(f"[{i}/{len(todo)}] FAILED  {p['title']} @ {p['company']}: {type(e).__name__}: {str(e)[:150]}")
            if failures_in_a_row >= 3:
                print("\nThree failures in a row - stopping. Likely a rate limit or bad key/model name.")
                break
            continue

        failures_in_a_row = 0
        results_db.save_result(result)
        print(f"[{i}/{len(todo)}] {result['decision'].upper():7} {result['score']:3}  {p['title']} @ {p['company']}")
        if i < len(todo):
            time.sleep(delay)  # stay under the free-tier requests-per-minute limit

    print("\nDone. See details with:  python score_postings.py --show")


def show(min_score: int) -> None:
    rows = results_db.list_matches(min_score=min_score)
    if not rows:
        print("No stored results yet. Run: python score_postings.py")
        return
    for r in rows:
        print(f"[{r['decision'].upper()} {r['score']}] {r['title']} @ {r['company']} ({r['location']})")
        print(f"   Matched: {', '.join(r['matched_skills']) or '-'}")
        print(f"   Missing: {', '.join(r['missing_skills']) or '-'}")
        print(f"   Top gap: {r['top_gap']}")
        print(f"   Why:     {r['reasoning']}")
        if r["pitch"]:
            print(f"   Pitch:   {r['pitch']}")
            for b in r["suggested_bullets"]:
                print(f"     - {b}")
        print(f"   URL:     {r['url']}\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Score stored postings with the LangGraph agent.")
    ap.add_argument("--limit", type=int, default=10, help="max postings to score this run (default 10)")
    ap.add_argument("--delay", type=float, default=7.0, help="seconds between postings (default 7)")
    ap.add_argument("--rescore", action="store_true", help="re-score postings that already have results")
    ap.add_argument("--show", action="store_true", help="print stored results and exit")
    ap.add_argument("--min-score", type=int, default=0, help="with --show, only results >= this score")
    args = ap.parse_args()

    if args.show:
        show(args.min_score)
    else:
        run(args.limit, args.delay, args.rescore)
