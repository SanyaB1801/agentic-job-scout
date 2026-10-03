"""
Central configuration for Career Copilot.
Loads settings from .env so no keys ever live in code.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # JSearch
    JSEARCH_API_KEY = os.getenv("JSEARCH_API_KEY", "")
    JSEARCH_API_HOST = os.getenv("JSEARCH_API_HOST", "jsearch.p.rapidapi.com")

    # Adzuna
    ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID", "")
    ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY", "")
    ADZUNA_COUNTRY = os.getenv("ADZUNA_COUNTRY", "in")

    # Chroma
    CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./data/chroma")
    CHROMA_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME", "job_postings")

    # Embeddings
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

    def validate_for_ingestion(self):
        """Fail loudly and early if required keys are missing."""
        missing = []
        if not self.JSEARCH_API_KEY:
            missing.append("JSEARCH_API_KEY")
        if not (self.ADZUNA_APP_ID and self.ADZUNA_APP_KEY):
            missing.append("ADZUNA_APP_ID / ADZUNA_APP_KEY")
        if missing:
            print(
                f"[config] Warning: missing {', '.join(missing)}. "
                "The pipeline will skip sources it can't authenticate."
            )


settings = Settings()
