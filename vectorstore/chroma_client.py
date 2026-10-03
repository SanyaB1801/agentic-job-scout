"""
Thin wrapper around Chroma: persistent local vector store, keyed by
posting_id so upserts are naturally idempotent.
"""
import chromadb
from config import settings
from ingestion.normalize import Posting


class JobVectorStore:
    def __init__(self):
        self.client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
        self.collection = self.client.get_or_create_collection(
            name=settings.CHROMA_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def existing_ids(self) -> set[str]:
        """All posting_ids already stored — used by the dedupe layer."""
        try:
            result = self.collection.get(include=[])  # ids are always returned
            return set(result.get("ids", []))
        except Exception:
            return set()

    def upsert(self, postings: list[Posting], embeddings: list[list[float]]):
        if not postings:
            return
        self.collection.upsert(
            ids=[p.posting_id for p in postings],
            embeddings=embeddings,
            documents=[p.embedding_text() for p in postings],
            metadatas=[
                {
                    "source": p.source,
                    "title": p.title,
                    "company": p.company or "",
                    "location": p.location or "",
                    "url": p.url,
                    "posted_date": p.posted_date or "",
                    "salary": p.salary or "",
                    "scraped_at": p.scraped_at,
                }
                for p in postings
            ],
        )

    def count(self) -> int:
        return self.collection.count()

    def query(self, query_embedding: list[float], n_results: int = 5):
        return self.collection.query(query_embeddings=[query_embedding], n_results=n_results)
