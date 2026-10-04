#!/usr/bin/env python3
"""
Diagnostic script to trace the entire pipeline:
  - Check Chroma connection and count postings
  - Check Neon connection and count existing results
  - Attempt to score a single posting
  - Verify it gets written to Neon

Run locally or in GitHub Actions to debug where the bottleneck is.
"""
import sys
from agent import results_db, settings
from vectorstore.chroma_client import JobVectorStore

def diagnose():
    print("=" * 70)
    print("DIAGNOSTIC: Checking pipeline connections and data flow")
    print("=" * 70)

    # 1. Check settings
    print("\n[1] Environment Variables:")
    print(f"  - DATABASE_URL set: {'✓' if settings.DATABASE_URL else '✗ MISSING'}")
    print(f"  - GOOGLE_API_KEY set: {'✓' if settings.GOOGLE_API_KEY else '✗ MISSING'}")
    print(f"  - CHROMA_HOST env: {os.getenv('CHROMA_HOST', 'not set')}")
    print(f"  - CHROMA_PORT env: {os.getenv('CHROMA_PORT', 'not set')}")

    # 2. Check Neon connection
    print("\n[2] Testing Neon (Postgres) Connection:")
    try:
        scored_before = results_db.scored_ids()
        print(f"  ✓ Connected to Neon")
        print(f"  ✓ Postings already scored in Neon: {len(scored_before)}")
    except Exception as e:
        print(f"  ✗ Failed to connect to Neon: {type(e).__name__}: {str(e)[:100]}")
        return

    # 3. Check Chroma connection
    print("\n[3] Testing Chroma Connection:")
    try:
        store = JobVectorStore()
        all_in_chroma = store.collection.get(include=[])
        chroma_count = len(all_in_chroma.get("ids", []))
        print(f"  ✓ Connected to Chroma")
        print(f"  ✓ Total postings in Chroma: {chroma_count}")
    except Exception as e:
        print(f"  ✗ Failed to connect to Chroma: {type(e).__name__}: {str(e)[:100]}")
        return

    # 4. Check which postings need scoring
    print("\n[4] Analyzing Scoring Gap:")
    try:
        postings = store.collection.get(include=["metadatas"])
        posting_ids = postings.get("ids", [])
        unscored = [pid for pid in posting_ids if pid not in scored_before]
        print(f"  - Postings in Chroma: {len(posting_ids)}")
        print(f"  - Postings scored in Neon: {len(scored_before)}")
        print(f"  - Postings awaiting scoring: {len(unscored)}")
        
        if unscored:
            print(f"\n  First 3 unscored posting IDs:")
            for pid in unscored[:3]:
                print(f"    - {pid}")
    except Exception as e:
        print(f"  ✗ Error analyzing gap: {type(e).__name__}: {str(e)[:100]}")
        return

    # 5. Attempt a test write to Neon
    print("\n[5] Testing Neon Write:")
    test_state = {
        "posting": {
            "posting_id": f"test-diagnostic-{os.urandom(4).hex()}",
            "title": "Diagnostic Test Posting",
            "company": "Test Corp",
            "location": "Test Location",
            "source": "diagnostic",
            "url": "https://example.com/test",
            "salary": None,
        },
        "score": 99,
        "decision": "alert",
        "assessment": {
            "matched_skills": ["Python", "Testing"],
            "missing_skills": [],
            "top_gap": "None",
            "reasoning": "Diagnostic test only",
            "seniority": "Any",
            "tech_stack": ["Python"],
        },
        "pitch": "This is a test.",
        "suggested_bullets": ["Test entry"],
    }
    
    try:
        results_db.save_result(test_state)
        # Verify it was written
        if test_state["posting"]["posting_id"] in results_db.scored_ids():
            print(f"  ✓ Successfully wrote test record to Neon and verified it exists")
        else:
            print(f"  ⚠ Wrote test record but verification query didn't find it")
    except Exception as e:
        print(f"  ✗ Failed to write to Neon: {type(e).__name__}: {str(e)[:100]}")

    print("\n" + "=" * 70)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    import os
    diagnose()
