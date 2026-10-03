"""
Embeds your resume chunks into their own Chroma collection ('resume_chunks')
so the agent can retrieve the parts of your resume most relevant to a posting.

Run whenever you edit data/resume.txt:
    python -m agent.resume_index
"""
from pathlib import Path
from agent import settings
from agent.resume_chunks import chunk_resume
from ingestion.embed import embed_text
from vectorstore.chroma_client import JobVectorStore


def index_resume(path: str | None = None) -> int:
    resume_path = Path(path or settings.RESUME_PATH)
    if not resume_path.exists():
        raise FileNotFoundError(f"Resume file not found: {resume_path}")

    chunks = chunk_resume(resume_path.read_text(encoding="utf-8"))
    if not chunks:
        raise ValueError("No chunks found. Check the '## ' / '### ' format in resume.txt.")

    client = JobVectorStore().client
    try:
        client.delete_collection(settings.RESUME_COLLECTION)  # rebuild so it never goes stale
    except Exception:
        pass
    collection = client.get_or_create_collection(
        name=settings.RESUME_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )

    collection.add(
        ids=[c["id"] for c in chunks],
        embeddings=[embed_text(c["text"]) for c in chunks],
        documents=[c["text"] for c in chunks],
        metadatas=[{"section": c["section"], "title": c["title"]} for c in chunks],
    )
    return len(chunks)


if __name__ == "__main__":
    n = index_resume()
    print(f"[resume] Indexed {n} resume chunks into '{settings.RESUME_COLLECTION}'.")
