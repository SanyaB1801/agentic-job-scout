"""
Settings for the agent stage. Reads the same .env file as config.py.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# --- LLM (Gemini, free tier works fine for this scale) ---
# Free key: https://aistudio.google.com/apikey
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# --- Routing thresholds (score is 0-100) ---
ALERT_THRESHOLD = int(os.getenv("ALERT_THRESHOLD", "75"))    # >= this: draft pitch + alert
REVIEW_THRESHOLD = int(os.getenv("REVIEW_THRESHOLD", "40"))  # >= this: keep for manual review

# --- Files ---
RESUME_PATH = os.getenv("RESUME_PATH", "./data/resume.txt")
MATCHES_DB_PATH = os.getenv("MATCHES_DB_PATH", "./data/matches.db")  # legacy SQLite path, used only by the migration script

# --- Hosted database (Neon Postgres) ---
# Use the POOLED connection string from your Neon project (hostname contains "-pooler"),
# since serverless hosts (Vercel) open many short-lived connections.
DATABASE_URL = os.getenv("DATABASE_URL", "")

# --- Retrieval ---
RESUME_COLLECTION = "resume_chunks"
EVIDENCE_K = int(os.getenv("EVIDENCE_K", "5"))  # resume chunks retrieved per posting