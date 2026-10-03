"""
Fetches job postings from Adzuna's official API — used as a secondary
source alongside JSearch for broader Indian job-board coverage.

Free registration: https://developer.adzuna.com/signup
"""
import requests
from config import settings
from ingestion.normalize import normalize_adzuna, Posting

BASE_URL = "https://api.adzuna.com/v1/api/jobs"


def fetch_adzuna_postings(query: str, location: str = "", results_per_page: int = 20) -> list[Posting]:
    """Query Adzuna's search endpoint and return normalized Posting objects."""
    if not (settings.ADZUNA_APP_ID and settings.ADZUNA_APP_KEY):
        print("[adzuna] Skipped — ADZUNA_APP_ID/ADZUNA_APP_KEY not set.")
        return []

    url = f"{BASE_URL}/{settings.ADZUNA_COUNTRY}/search/1"
    params = {
        "app_id": settings.ADZUNA_APP_ID,
        "app_key": settings.ADZUNA_APP_KEY,
        "results_per_page": results_per_page,
        "what": query,
        "where": location,
        "content-type": "application/json",
    }

    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[adzuna] Request failed: {e}")
        return []

    results = resp.json().get("results", [])
    postings = [normalize_adzuna(item) for item in results]
    print(f"[adzuna] Fetched {len(postings)} postings for '{query}' in '{location or 'any location'}'.")
    return postings
