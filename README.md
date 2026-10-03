# Career Copilot - the Agentic Job Scout

A LangGraph + Chroma powered agent that continuously ingests job postings,
scores them against your resume, and proactively alerts you on strong fits.

## Architecture

```
JSearch API --+
              +--> Ingestion pipeline --> Chroma (job postings) --+
Adzuna API ---+    (dedupe, embed)                                |
                                                                  v
 data/resume.txt --> Chroma (resume chunks) --> LangGraph agent: retrieve -> score -> branch
                                                   |-- score >= 75 : draft pitch -> ALERT
                                                   |-- 40 - 74     : flag for review
                                                   |-- < 40        : discard
                                                          |
                                                          v
                                                   SQLite (data/matches.db)
```

## Project status

- [x] Ingestion pipeline (JSearch + Adzuna -> dedupe -> embed -> Chroma)
- [x] LangGraph agent (retrieve resume evidence -> score fit -> branch)
- [ ] Scheduler for continuous ingestion + scoring
- [ ] Alert pipeline (Telegram)
- [ ] FastAPI serving layer
- [ ] Streamlit dashboard
- [ ] Metadata extraction (seniority, tech stack) for filtering

## Folder structure

```
career-copilot/
|-- config.py                  # ingestion settings
|-- requirements.txt
|-- .env.example               # copy to .env and fill in keys
|-- view_postings.py           # print postings stored in Chroma
|-- score_postings.py          # run the agent over stored postings / show results
|-- data/
|   |-- resume.txt             # YOUR resume as structured text (agent ground truth)
|   |-- chroma/                # vector DB (created on first run)
|   `-- matches.db             # scored results (created on first score)
|-- ingestion/
|   |-- sources/jsearch.py, adzuna.py
|   |-- normalize.py, dedupe.py, embed.py
|   `-- pipeline.py
|-- vectorstore/chroma_client.py
`-- agent/
    |-- settings.py            # LLM key, thresholds, paths
    |-- resume_chunks.py       # splits resume.txt into chunks
    |-- resume_index.py        # embeds chunks into Chroma
    |-- routing.py             # score -> next node
    |-- nodes.py               # retrieve_evidence, score_fit, draft_pitch, ...
    |-- graph.py               # LangGraph wiring
    `-- results_db.py          # SQLite storage
```

## Setup

```bash
python -m venv venv
venv\Scripts\activate             # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
copy .env.example .env            # macOS/Linux: cp .env.example .env
```

Keys needed in `.env`: JSearch (RapidAPI), Adzuna, and a Gemini key
(free at https://aistudio.google.com/apikey).

## Run

```bash
# 1. Ingest postings
python -m ingestion.pipeline --query "AI Engineer" --location "Delhi NCR"
python view_postings.py

# 2. Index your resume (re-run whenever data/resume.txt changes)
python -m agent.resume_index

# 3. Score postings with the agent
python score_postings.py --limit 5
python score_postings.py --show
```

## How the agent decides

1. **retrieve_evidence** - embeds the posting, pulls the most relevant resume
   chunks from Chroma (plus your skills sections).
2. **score_fit** - Gemini scores 0-100 using only that evidence and lists
   matched vs. missing skills.
3. **Branch** - high score drafts a tailored pitch (real facts only) and marks
   the posting `alert`; mid score marks `review`; low score is `discard`ed.
