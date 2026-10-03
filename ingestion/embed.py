"""
Local embedding generation via sentence-transformers — no external API
key needed, runs on CPU fine for this scale of data.
"""
from functools import lru_cache
from sentence_transformers import SentenceTransformer
from config import settings
from ingestion.normalize import Posting


@lru_cache(maxsize=1)
def _get_model() -> SentenceTransformer:
    print(f"[embed] Loading model '{settings.EMBEDDING_MODEL}' (first call only)...")
    return SentenceTransformer(settings.EMBEDDING_MODEL)


def embed_postings(postings: list[Posting]) -> list[list[float]]:
    if not postings:
        return []
    model = _get_model()
    texts = [p.embedding_text() for p in postings]
    embeddings = model.encode(texts, show_progress_bar=False)
    return embeddings.tolist()


def embed_text(text: str) -> list[float]:
    """Embed a single arbitrary string — used later by the agent to embed
    the user's resume/query for similarity search."""
    model = _get_model()
    return model.encode([text], show_progress_bar=False)[0].tolist()
