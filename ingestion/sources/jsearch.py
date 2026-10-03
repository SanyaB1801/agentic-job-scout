"""
Fetches live job postings from JSearch (RapidAPI), which aggregates
Google for Jobs results — including LinkedIn, Naukri, and Indeed listings.

Free tier: 200 requests/month, 1000/hour. Docs:
https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch
"""
import requests
from config import settings
from ingestion.normalize import normalize_jsearch, Posting

BASE_URL = f"https://{settings.JSEARCH_API_HOST}/search"


def fetch_jsearch_postings(query: str, location: str = "", num_pages: int = 1) -> list[Posting]:
    """Query JSearch and return normalized Posting objects.

    `query` and `location` are combined the way JSearch expects, e.g.
    fetch_jsearch_postings("AI Engineer", "Delhi NCR") sends
    "AI Engineer in Delhi NCR" as the search string.
    """
    if not settings.JSEARCH_API_KEY:
        print("[jsearch] Skipped — JSEARCH_API_KEY not set.")
        return []

    search_query = f"{query} in {location}" if location else query
    headers = {
        "x-rapidapi-key": settings.JSEARCH_API_KEY,
        "x-rapidapi-host": settings.JSEARCH_API_HOST,
    }
    params = {
        "query": search_query,
        "page": "1",
        "num_pages": str(num_pages),
        "date_posted": "week",  # keeps results fresh — this is the "real-time" lever
    }

    try:
        resp = requests.get(BASE_URL, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[jsearch] Request failed: {e}")
        return []

    data = resp.json().get("data", [])
    postings = [normalize_jsearch(item) for item in data]
    print(f"[jsearch] Fetched {len(postings)} postings for '{search_query}'.")
    return postings
