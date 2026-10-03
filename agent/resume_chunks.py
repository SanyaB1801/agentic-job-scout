"""
Splits data/resume.txt into chunks, one per "### " entry, each tagged with
its "## " section. Pure Python on purpose so it's easy to test.

Format:
    ## SECTION
    ### Entry title
    bullet lines / text...
"""
import re


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40]


def chunk_resume(text: str) -> list[dict]:
    chunks: list[dict] = []
    section = ""
    entry = ""
    body: list[str] = []

    def flush():
        if body:
            title = entry or section
            content = "\n".join(body).strip()
            chunks.append(
                {
                    "id": f"resume-{len(chunks):02d}-{_slug(title)}",
                    "section": section,
                    "title": title,
                    "text": f"[{section}] {title}\n{content}",
                }
            )
        body.clear()

    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("## "):
            flush()
            section, entry = line[3:].strip(), ""
        elif line.startswith("### "):
            flush()
            entry = line[4:].strip()
        elif line.startswith("# "):
            continue  # comment / document title
        elif line.strip():
            body.append(line.strip())
    flush()
    return chunks
