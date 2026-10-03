"""
Career Copilot dashboard - local web app over data/matches.db.

Run:
    uvicorn app:app --reload

Then open http://127.0.0.1:8000 in a browser.
"""
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from agent import results_db

app = FastAPI(title="Career Copilot Dashboard")


class StatusUpdate(BaseModel):
    status: str | None = None
    notes: str | None = None


@app.get("/api/matches")
def api_matches(
    min_score: int = 0,
    decision: str = "all",
    status: str = "all",
    seniority: str = "all",
    tech: str = "",
    salary_min: int | None = None,
    salary_max: int | None = None,
    search: str = "",
    order_by: str = "score",
    limit: int = 200,
):
    return {
        "counts": results_db.counts(),
        "matches": results_db.list_matches(
            min_score=min_score, decision=decision, status=status, seniority=seniority,
            tech=tech or None, salary_min=salary_min, salary_max=salary_max,
            search=search or None, order_by=order_by, limit=limit,
        ),
    }


@app.patch("/api/matches/{posting_id}")
def update_match(posting_id: str, body: StatusUpdate):
    results_db.set_status(posting_id, status=body.status, notes=body.notes)
    return {"ok": True}


@app.get("/", response_class=HTMLResponse)
def dashboard():
    return INDEX_HTML


INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Career Copilot Dashboard</title>
<style>
  :root {
    --bg: #0b0d12; --card: #151821; --card-hover: #1a1e29; --border: #262b36;
    --text: #e8eaed; --muted: #8b93a1; --muted-dim: #5c6472;
    --alert: #34d399; --review: #fbbf24; --discard: #6b7280;
    --accent: #60a5fa; --danger: #f87171;
    --applied: #60a5fa; --interviewing: #a78bfa; --offer: #34d399;
    --rejected: #f87171; --not_interested: #5c6472; --new: #8b93a1;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--bg); color: var(--text);
    font-family: -apple-system, Segoe UI, Roboto, sans-serif;
    padding: 24px 16px 60px; max-width: 1040px; margin-inline: auto;
  }
  h1 { font-size: 1.5rem; margin: 0 0 2px; }
  .sub { color: var(--muted); font-size: 0.85rem; margin-bottom: 20px; }

  .stats-row { display: flex; gap: 10px; margin-bottom: 10px; flex-wrap: wrap; }
  .stat {
    background: var(--card); border: 1px solid var(--border); border-radius: 10px;
    padding: 8px 14px; font-size: 0.78rem; cursor: pointer; user-select: none;
    transition: border-color 0.15s;
  }
  .stat:hover { border-color: var(--muted-dim); }
  .stat.active { border-color: var(--accent); }
  .stat b { font-size: 1.05rem; display: block; }

  .panel {
    background: var(--card); border: 1px solid var(--border); border-radius: 12px;
    padding: 14px 16px; margin: 16px 0 20px;
  }
  .panel-label { font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--muted-dim); margin-bottom: 8px; }
  .filters { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
  select, input, textarea {
    background: #0e1117; color: var(--text); border: 1px solid var(--border);
    border-radius: 8px; padding: 7px 10px; font-size: 0.82rem; font-family: inherit;
  }
  select:focus, input:focus, textarea:focus { outline: none; border-color: var(--accent); }
  input[type="text"].search { flex: 1; min-width: 160px; }
  input[type="number"] { width: 110px; }
  .salary-pair { display: flex; align-items: center; gap: 6px; }
  .salary-pair span { color: var(--muted-dim); font-size: 0.78rem; }
  .clear-btn {
    background: transparent; border: 1px solid var(--border); color: var(--muted);
    border-radius: 8px; padding: 7px 12px; font-size: 0.8rem; cursor: pointer;
  }
  .clear-btn:hover { color: var(--text); border-color: var(--muted-dim); }

  .count-line { color: var(--muted-dim); font-size: 0.8rem; margin-bottom: 10px; }

  .card {
    background: var(--card); border: 1px solid var(--border); border-radius: 12px;
    padding: 16px; margin-bottom: 12px; transition: border-color 0.15s;
  }
  .card:hover { border-color: #323846; }
  .row { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
  .title { font-weight: 600; font-size: 1rem; }
  .meta { color: var(--muted); font-size: 0.8rem; margin-top: 3px; }
  .meta b { color: var(--muted); }
  .badges { display: flex; gap: 6px; align-items: center; flex-shrink: 0; }
  .badge {
    font-size: 0.72rem; font-weight: 700; padding: 3px 10px; border-radius: 999px;
    white-space: nowrap; color: #0b0d12;
  }
  .badge.alert { background: var(--alert); }
  .badge.review { background: var(--review); }
  .badge.discard { background: var(--discard); color: var(--text); }
  .senior-tag {
    font-size: 0.7rem; color: var(--muted); border: 1px solid var(--border);
    border-radius: 6px; padding: 2px 8px;
  }

  .tags { margin-top: 10px; }
  .tag {
    display: inline-block; background: #1c212c; border: 1px solid var(--border);
    border-radius: 6px; padding: 2px 8px; margin: 2px 4px 0 0; font-size: 0.74rem;
  }
  .tag.missing { color: var(--danger); border-color: #4a2a2a; }
  .tag.matched { color: var(--alert); border-color: #1f4a3a; }
  .tag.tech { color: var(--accent); border-color: #1e3a5f; }

  .why { color: var(--muted); font-size: 0.82rem; margin-top: 10px; line-height: 1.4; }
  .pitch {
    margin-top: 10px; padding: 10px 12px; background: #0f1f17;
    border: 1px solid #1f5c43; border-radius: 8px; font-size: 0.85rem;
  }
  .pitch ul { margin: 6px 0 0 18px; padding: 0; }

  .footer-row {
    display: flex; justify-content: space-between; align-items: center;
    margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); gap: 10px; flex-wrap: wrap;
  }
  a.open-link { color: var(--accent); text-decoration: none; font-size: 0.8rem; white-space: nowrap; }
  a.open-link:hover { text-decoration: underline; }

  .status-select { font-size: 0.78rem; padding: 5px 8px; }
  .status-select.new { color: var(--new); }
  .status-select.applied { color: var(--applied); }
  .status-select.interviewing { color: var(--interviewing); }
  .status-select.offer { color: var(--offer); }
  .status-select.rejected { color: var(--rejected); }
  .status-select.not_interested { color: var(--not_interested); }

  .notes-wrap { width: 100%; margin-top: 10px; }
  .notes-wrap textarea {
    width: 100%; min-height: 36px; resize: vertical; font-size: 0.8rem;
  }
  .saved-flash { font-size: 0.7rem; color: var(--alert); opacity: 0; transition: opacity 0.3s; margin-left: 8px; }
  .saved-flash.show { opacity: 1; }

  .empty { color: var(--muted); text-align: center; padding: 50px 0; }
</style>
</head>
<body>

<h1>Career Copilot Dashboard</h1>
<div class="sub">Scored postings from your local Chroma + Gemini agent</div>

<div class="stats-row" id="statsRow"></div>

<div class="panel">
  <div class="panel-label">Filters</div>
  <div class="filters">
    <select id="decision">
      <option value="all">Any verdict</option>
      <option value="alert">Alert</option>
      <option value="review">Review</option>
      <option value="discard">Discarded (by agent)</option>
    </select>
    <select id="status">
      <option value="all">Any status</option>
      <option value="new">New</option>
      <option value="applied">Applied</option>
      <option value="interviewing">Interviewing</option>
      <option value="offer">Offer</option>
      <option value="rejected">Rejected</option>
      <option value="not_interested">Not interested (by me)</option>
    </select>
    <select id="seniority">
      <option value="all">Any seniority</option>
      <option value="Entry">Entry</option>
      <option value="Mid">Mid</option>
      <option value="Senior">Senior</option>
      <option value="Lead+">Lead+</option>
      <option value="Unknown">Unknown</option>
    </select>
    <select id="minScore">
      <option value="0">Any score</option>
      <option value="40">40+</option>
      <option value="60">60+</option>
      <option value="75">75+ (alert-level)</option>
    </select>
    <select id="orderBy">
      <option value="score">Sort: Score</option>
      <option value="salary">Sort: Salary</option>
    </select>
  </div>
  <div class="filters" style="margin-top:8px;">
    <div class="salary-pair">
      <span>Pay</span>
      <input type="number" id="salaryMin" placeholder="min">
      <span>&ndash;</span>
      <input type="number" id="salaryMax" placeholder="max">
    </div>
    <input type="text" id="tech" placeholder="Tech stack (e.g. LangChain)" style="width:200px;">
    <input type="text" id="search" class="search" placeholder="Search title or company...">
    <button class="clear-btn" onclick="clearFilters()">Clear filters</button>
  </div>
</div>

<div class="count-line" id="countLine"></div>
<div id="results"></div>

<script>
const STATUS_OPTIONS = ["new", "applied", "interviewing", "offer", "rejected", "not_interested"];
let activeStatChip = null;

function fmtMoney(n) {
  if (n == null) return null;
  return n >= 100000 ? (n / 100000).toFixed(1).replace(/\\.0$/, '') + 'L' : n.toLocaleString();
}

function salaryLabel(m) {
  if (m.salary_min == null && m.salary_max == null) return null;
  if (m.salary_min === m.salary_max) return fmtMoney(m.salary_min);
  return `${fmtMoney(m.salary_min)} - ${fmtMoney(m.salary_max)}`;
}

function buildParams() {
  return new URLSearchParams({
    decision: document.getElementById('decision').value,
    status: document.getElementById('status').value,
    seniority: document.getElementById('seniority').value,
    min_score: document.getElementById('minScore').value,
    order_by: document.getElementById('orderBy').value,
    tech: document.getElementById('tech').value,
    search: document.getElementById('search').value,
    ...(document.getElementById('salaryMin').value && { salary_min: document.getElementById('salaryMin').value }),
    ...(document.getElementById('salaryMax').value && { salary_max: document.getElementById('salaryMax').value }),
  });
}

function clearFilters() {
  document.getElementById('decision').value = 'all';
  document.getElementById('status').value = 'all';
  document.getElementById('seniority').value = 'all';
  document.getElementById('minScore').value = '0';
  document.getElementById('orderBy').value = 'score';
  document.getElementById('salaryMin').value = '';
  document.getElementById('salaryMax').value = '';
  document.getElementById('tech').value = '';
  document.getElementById('search').value = '';
  activeStatChip = null;
  load();
}

function setStatChip(kind, value) {
  const key = kind + ':' + value;
  if (activeStatChip === key) {
    document.getElementById(kind).value = 'all';
    activeStatChip = null;
  } else {
    document.getElementById(kind).value = value;
    activeStatChip = key;
  }
  load();
}

async function load() {
  const res = await fetch('/api/matches?' + buildParams().toString());
  const data = await res.json();
  renderStats(data.counts);
  renderResults(data.matches);
}

function renderStats(counts) {
  const d = counts.decision, s = counts.status;
  const chip = (label, kind, value, n, color) => `
    <div class="stat ${activeStatChip === kind + ':' + value ? 'active' : ''}" onclick="setStatChip('${kind}','${value}')">
      <b style="${color ? `color:${color}` : ''}">${n}</b>${label}
    </div>`;
  document.getElementById('statsRow').innerHTML =
    chip('Total', 'decision', 'all', d.total) +
    chip('Alert', 'decision', 'alert', d.alert, 'var(--alert)') +
    chip('Review', 'decision', 'review', d.review, 'var(--review)') +
    chip('Applied', 'status', 'applied', s.applied, 'var(--applied)') +
    chip('Interviewing', 'status', 'interviewing', s.interviewing, 'var(--interviewing)') +
    chip('Offer', 'status', 'offer', s.offer, 'var(--offer)');
}

function renderResults(matches) {
  document.getElementById('countLine').textContent = `${matches.length} posting${matches.length === 1 ? '' : 's'}`;
  const el = document.getElementById('results');
  if (matches.length === 0) {
    el.innerHTML = '<div class="empty">No postings match these filters.</div>';
    return;
  }

  el.innerHTML = matches.map(m => {
    const salary = salaryLabel(m);
    return `
    <div class="card" data-id="${m.posting_id}">
      <div class="row">
        <div>
          <div class="title">${escapeHtml(m.title)} @ ${escapeHtml(m.company || '-')}</div>
          <div class="meta">
            ${escapeHtml(m.location || '-')} &middot; ${escapeHtml(m.source)} &middot; score <b>${m.score}</b>
            ${salary ? ` &middot; <b>${salary}</b>` : ''}
          </div>
        </div>
        <div class="badges">
          <span class="senior-tag">${escapeHtml(m.seniority || 'Unknown')}</span>
          <span class="badge ${m.decision}">${m.decision.toUpperCase()}</span>
        </div>
      </div>

      <div class="tags">
        ${(m.tech_stack || []).map(t => `<span class="tag tech">${escapeHtml(t)}</span>`).join('')}
        ${m.matched_skills.map(s => `<span class="tag matched">${escapeHtml(s)}</span>`).join('')}
        ${m.missing_skills.map(s => `<span class="tag missing">${escapeHtml(s)}</span>`).join('')}
      </div>

      <div class="why">${escapeHtml(m.reasoning || '')}</div>

      ${m.pitch ? `
        <div class="pitch">
          <div>${escapeHtml(m.pitch)}</div>
          <ul>${m.suggested_bullets.map(b => `<li>${escapeHtml(b)}</li>`).join('')}</ul>
        </div>
      ` : ''}

      <div class="footer-row">
        <div>
          <select class="status-select ${m.status}" onchange="updateStatus('${m.posting_id}', this.value, this)">
            ${STATUS_OPTIONS.map(s => `<option value="${s}" ${s === m.status ? 'selected' : ''}>${s.replace('_', ' ')}</option>`).join('')}
          </select>
          <span class="saved-flash" id="flash-${m.posting_id}">saved</span>
        </div>
        <a class="open-link" href="${m.url}" target="_blank" rel="noopener">Open posting &rarr;</a>
      </div>

      <div class="notes-wrap">
        <textarea placeholder="Notes (follow-up date, referral, interview round...)"
          onchange="updateNotes('${m.posting_id}', this.value)">${escapeHtml(m.notes || '')}</textarea>
      </div>
    </div>
  `;
  }).join('');
}

async function patchMatch(id, body) {
  await fetch(`/api/matches/${id}`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
}

async function updateStatus(id, status, el) {
  el.className = `status-select ${status}`;
  await patchMatch(id, { status });
  flash(id);
  const data = await (await fetch('/api/matches?' + buildParams().toString())).json();
  renderStats(data.counts);
}

async function updateNotes(id, notes) {
  await patchMatch(id, { notes });
  flash(id);
}

function flash(id) {
  const el = document.getElementById(`flash-${id}`);
  if (!el) return;
  el.classList.add('show');
  setTimeout(() => el.classList.remove('show'), 1200);
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str ?? '';
  return div.innerHTML;
}

['decision', 'status', 'seniority', 'minScore', 'orderBy'].forEach(id =>
  document.getElementById(id).addEventListener('change', () => { activeStatChip = null; load(); })
);
['salaryMin', 'salaryMax'].forEach(id =>
  document.getElementById(id).addEventListener('change', load)
);
document.getElementById('tech').addEventListener('input', debounce(load, 300));
document.getElementById('search').addEventListener('input', debounce(load, 300));

function debounce(fn, ms) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}

load();
</script>

</body>
</html>
"""