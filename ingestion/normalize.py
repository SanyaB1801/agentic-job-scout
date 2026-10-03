"""
A single, common schema for job postings, plus functions that map each
source's raw JSON into it. This is the layer that lets the rest of the
pipeline (dedupe, embed, store) not care which API a posting came from.
"""
import hashlib
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel


class Posting(BaseModel):
    source: str                      # "jsearch" | "adzuna"
    posting_id: str                  # stable hash, used as the dedupe key
    title: str
    company: Optional[str] = ""
    location: Optional[str] = ""
    description: str = ""
    url: str = ""
    posted_date: Optional[str] = None
    salary: Optional[str] = None
    scraped_at: str = ""

    def embedding_text(self) -> str:
        """What actually gets embedded — title + company + description,
        truncated so we don't blow the embedding model's context."""
        parts = [self.title, self.company or "", self.description or ""]
        return " | ".join(p for p in parts if p)[:2000]


def _stable_id(url: str, title: str, company: str) -> str:
    """Hash-based ID so the same posting always maps to the same ID,
    across runs and across sources that might list the same job."""
    key = f"{url}|{title}|{company}".lower().strip()
    return hashlib.sha256(key.encode()).hexdigest()[:24]


def normalize_jsearch(raw: dict) -> Posting:
    title = raw.get("job_title", "")
    company = raw.get("employer_name", "")
    url = raw.get("job_apply_link") or raw.get("job_google_link") or ""
    location_parts = [raw.get("job_city"), raw.get("job_state"), raw.get("job_country")]
    location = ", ".join(p for p in location_parts if p)

    salary = None
    if raw.get("job_min_salary") and raw.get("job_max_salary"):
        salary = f"{raw['job_min_salary']}-{raw['job_max_salary']} {raw.get('job_salary_currency', '')}".strip()

    return Posting(
        source="jsearch",
        posting_id=_stable_id(url, title, company),
        title=title,
        company=company,
        location=location,
        description=raw.get("job_description", "") or "",
        url=url,
        posted_date=raw.get("job_posted_at_datetime_utc"),
        salary=salary,
        scraped_at=datetime.now(timezone.utc).isoformat(),
    )


def normalize_adzuna(raw: dict) -> Posting:
    title = raw.get("title", "")
    company = (raw.get("company") or {}).get("display_name", "")
    url = raw.get("redirect_url", "")
    location = (raw.get("location") or {}).get("display_name", "")

    salary = None
    if raw.get("salary_min") and raw.get("salary_max"):
        salary = f"{raw['salary_min']}-{raw['salary_max']}"

    return Posting(
        source="adzuna",
        posting_id=_stable_id(url, title, company),
        title=title,
        company=company,
        location=location,
        description=raw.get("description", "") or "",
        url=url,
        posted_date=raw.get("created"),
        salary=salary,
        scraped_at=datetime.now(timezone.utc).isoformat(),
    )
