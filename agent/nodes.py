"""
The nodes of the LangGraph agent. Each takes the state dict and returns a
partial update.

    retrieve_evidence -> score_fit -> [draft_pitch -> mark_alert | flag_review | discard]
"""
import time
from functools import lru_cache
from pydantic import BaseModel, Field

from agent import settings
from ingestion.embed import embed_text
from vectorstore.chroma_client import JobVectorStore


# ---------- structured outputs the LLM must return ----------

class FitAssessment(BaseModel):
    score: int = Field(description="Overall fit from 0 to 100")
    matched_skills: list[str] = Field(
        description="Skills/tools the posting asks for that the resume evidence clearly shows"
    )
    missing_skills: list[str] = Field(
        description="Skills/tools the posting asks for that the resume evidence does NOT show"
    )
    top_gap: str = Field(description="The single most important gap, or 'None'")
    reasoning: str = Field(description="At most 60 words explaining the score")
    seniority: str = Field(
        description="Seniority the POSTING is written for: one of Entry, Mid, Senior, Lead+, Unknown"
    )
    tech_stack: list[str] = Field(
        description="Concrete tools/technologies/languages the posting explicitly names (not soft skills)"
    )


class PitchDraft(BaseModel):
    pitch: str = Field(description="2-3 sentence first-person opener for a recruiter message")
    suggested_bullets: list[str] = Field(
        description="2-3 resume bullets reworded from REAL bullets to fit this posting"
    )


# ---------- LLM helpers ----------

@lru_cache(maxsize=1)
def _llm():
    if not settings.GOOGLE_API_KEY:
        raise RuntimeError(
            "GOOGLE_API_KEY is not set. Add it to .env (free key: https://aistudio.google.com/apikey)."
        )
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=0,
    )


def _invoke_structured(schema, messages, tries: int = 4):
    """Call the LLM with structured output; back off and retry on rate limits."""
    chain = _llm().with_structured_output(schema)
    for attempt in range(tries):
        try:
            result = chain.invoke(messages)
            if result is None:
                raise ValueError("Model returned no structured output")
            return result
        except Exception as e:
            if attempt == tries - 1:
                raise
            wait = 10 * (2 ** attempt)
            print(f"    [llm] {type(e).__name__}; retrying in {wait}s ({attempt + 1}/{tries - 1})")
            time.sleep(wait)


@lru_cache(maxsize=1)
def _resume_collection():
    try:
        return JobVectorStore().client.get_collection(settings.RESUME_COLLECTION)
    except Exception:
        raise RuntimeError("Resume not indexed yet. Run: python -m agent.resume_index")


# ---------- prompts ----------

SCORING_SYSTEM = """You are a strict but fair technical recruiter judging how well a candidate fits a job posting.

Rules:
- Use ONLY the resume evidence provided. Never assume a skill that is not shown there.
- Candidate context: 2026 B.Tech (AI & ML) graduate with about one year of internships. Best suited to entry-level up to ~2 years of experience. Penalize postings that require 4+ years or are unrelated to AI/ML, data or automation engineering.
- Score guide: 85-100 excellent fit, 70-84 good fit, 40-69 partial fit, below 40 poor fit.
- matched_skills / missing_skills: only list things the posting actually asks for.
- seniority: classify the POSTING (not the candidate) as Entry, Mid, Senior, Lead+, or Unknown.
- tech_stack: list concrete tools/technologies/languages the posting explicitly names. Nothing inferred.
- Keep reasoning under 60 words."""

PITCH_SYSTEM = """You write short, honest application pitches for a candidate.

Rules:
- Use ONLY facts in the resume evidence. Never invent tools, employers, numbers or years of experience.
- Do NOT claim any skill listed in missing_skills.
- pitch: 2-3 sentences, first person, specific, no buzzword filler.
- suggested_bullets: 2-3 bullets reworded from REAL resume bullets (action + task + result), emphasizing relevance to this posting. Keep the original metrics exactly as written."""


def _posting_block(p: dict) -> str:
    return (
        f"Title: {p.get('title', '')}\n"
        f"Company: {p.get('company', '')}\n"
        f"Location: {p.get('location', '')}\n"
        f"Salary: {p.get('salary') or 'not listed'}\n"
        f"Description:\n{p.get('description', '')}"
    )


# ---------- graph nodes ----------

def retrieve_evidence(state: dict) -> dict:
    """RAG step: pull the resume chunks most relevant to this posting."""
    p = state["posting"]
    query = " | ".join(x for x in [p.get("title"), p.get("company"), p.get("description")] if x)[:2000]

    collection = _resume_collection()
    res = collection.query(query_embeddings=[embed_text(query)], n_results=settings.EVIDENCE_K)
    evidence = list(res["documents"][0])

    # Always include the skills chunks so the scorer can see the full tech stack.
    skills = collection.get(where={"section": "SKILLS"}, include=["documents"])
    for doc in skills.get("documents", []):
        if doc not in evidence:
            evidence.append(doc)

    return {"evidence": evidence}


def score_fit(state: dict) -> dict:
    """LLM scores the posting against the retrieved resume evidence."""
    human = (
        "JOB POSTING\n" + _posting_block(state["posting"]) +
        "\n\nRESUME EVIDENCE\n" + "\n\n".join(state["evidence"])
    )
    a = _invoke_structured(FitAssessment, [("system", SCORING_SYSTEM), ("human", human)])
    score = max(0, min(100, int(a.score)))
    return {"assessment": a.model_dump(), "score": score}


def draft_pitch(state: dict) -> dict:
    """Only runs for high-fit postings (see routing.py)."""
    a = state["assessment"]
    human = (
        "JOB POSTING\n" + _posting_block(state["posting"]) +
        "\n\nRESUME EVIDENCE\n" + "\n\n".join(state["evidence"]) +
        f"\n\nmatched_skills: {a['matched_skills']}\nmissing_skills: {a['missing_skills']}"
    )
    d = _invoke_structured(PitchDraft, [("system", PITCH_SYSTEM), ("human", human)])
    return {"pitch": d.pitch, "suggested_bullets": d.suggested_bullets}


def mark_alert(state: dict) -> dict:
    return {"decision": "alert"}


def flag_review(state: dict) -> dict:
    return {"decision": "review"}


def discard(state: dict) -> dict:
    return {"decision": "discard"}