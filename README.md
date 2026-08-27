# AI HR

AI-powered Applicant Tracking System (ATS) built on top of Frappe HR.

`ai_hr` **extends** HRMS — it does not replace or modify it. No file under
`apps/frappe/` or `apps/hrms/` is edited, so `bench update` cannot clobber this
app and this app cannot break stock HRMS behaviour. Everything it adds to core
DocTypes is a Custom Field owned by this app.

---

## Requirements

| | |
|---|---|
| Frappe / ERPNext / HRMS | v17 (`develop`) |
| Python | 3.14 |
| Python packages | `anthropic`, `python-docx` (PDF handled by `pdfplumber` / `pypdf`, already in Frappe) |

## Installation

```bash
cd ~/frappe/my-bench
bench get-app ai_hr /path/to/ai_hr      # or: bench new-app ai_hr
./env/bin/pip install anthropic python-docx
bench --site your-site.localhost install-app ai_hr
bench --site your-site.localhost migrate
bench build --app ai_hr
```

## Configuration

Open **AI HR Settings** (single doctype) and set:

- **AI Provider** — `Anthropic Claude` (default), `OpenAI`, `Google Gemini`, or `Ollama`
- **API Key** — stored encrypted, never sent to the browser
- **Model** — blank uses the provider default (Claude: `claude-opus-5`)
- **Reasoning Effort** — blank uses the provider default
- **Max Tokens** — caps reasoning *plus* answer; raise if responses truncate
- **Feature toggles** — parsing, matching, interview assistant, JD generation

> There is deliberately **no temperature setting**. Claude Opus 4.7+ rejects
> `temperature` / `top_p` / `top_k` with a 400, so exposing it would silently
> break the default provider. Reasoning Effort is the supported control.

`Ollama` needs no API key — set **Base URL** if the daemon is not on
`http://127.0.0.1:11434`.

---

## Features

| Proposal § | Feature | Where |
|---|---|---|
| §2 | CV parsing (PDF, DOCX) | *Parse Resume with AI* on Job Applicant |
| §3 | Job description generation | *Generate Description* on Job Opening |
| §4 | Candidate/opening match scoring | *Score All Applicants* on Job Opening |
| §5 | Candidate ranking | **Candidate Ranking** report |
| §6 | Interview question generation | *Generate Questions* on AI Interview |
| §7 | Post-interview evaluation | *Evaluate Interview* on AI Interview |
| §8 | Recruiter chat assistant | **AI Recruiter Assistant** page (`/app/ai-recruiter`) |
| §9 | ATS pipeline | `ats_stage` field on Job Applicant |

### The ATS pipeline

Stock `Job Applicant.status` is a fixed six-value Select owned by HRMS. Widening
it would mean editing core, so the twelve-stage pipeline from §9 lives in an
app-owned `ats_stage` field, and `ai_hr.setup.sync_status_from_stage` keeps the
stock field in step on every save:

| ATS stage | → stock status |
|---|---|
| Applied, CV Screening, AI Screening | Open |
| Shortlisted, Phone / Technical / Final Interview | Shortlisted |
| Offer, Hired | Accepted |
| Rejected, Withdrawn | Rejected |
| On Hold | Hold |

Existing HRMS reports and workflows keep working untouched.

---

## Architecture

```
ai_hr/
├── ai/
│   ├── base.py          AIProvider ABC, AIConfig, AIResult
│   ├── registry.py      settings -> configured provider
│   ├── schemas.py       JSON Schemas (strict-mode compatible)
│   ├── prompts.py       system prompts + user-turn builders
│   └── providers/       anthropic | openai | gemini | ollama
├── api/
│   ├── resume.py        CV parsing pipeline
│   ├── matching.py      scoring + batch scoring
│   ├── jd.py            job description generation
│   ├── interview.py     question generation + evaluation
│   └── assistant.py     recruiter chat
├── utils/extract.py     PDF/DOCX text extraction
└── setup.py             custom fields + stage/status sync
```

**Adding a provider** is one subclass of `AIProvider` plus one entry in
`ai_hr.ai.registry.PROVIDERS`. Nothing outside `ai/providers/` imports a vendor
SDK.

### DocTypes

| DocType | Purpose |
|---|---|
| AI HR Settings | Provider configuration (single) |
| AI Resume Analysis | Structured profile extracted from a CV |
| AI Resume Skill | Child — one row per extracted skill |
| AI Candidate Score | Advisory fit score for one candidate/opening pair |
| AI Job Skill | Child — required skills on a Job Opening |
| AI Interview | Interview prep and evaluation |
| AI Interview Question | Child — editable question list |

### Custom fields added to core

- **Job Applicant** — `ats_stage`, `ai_match_score`, `ai_resume_analysis`, `ai_parsing_status`
- **Job Opening** — `ai_required_skills`, `ai_min_experience`, `ai_education_requirement`

---

## Design decisions

**AI advises, it never decides.** Per §4 and §7, nothing in this app auto-rejects
or auto-hires. Scores and recommendations are advisory fields; stage changes are
always a human action.

**Fairness guard.** Every prompt forbids inferring or acting on age, gender,
ethnicity, nationality, religion, marital status, disability, photographs, or
candidate names. Recruitment is regulated; a score influenced by a protected
characteristic is a legal problem, not just a quality one.

**No SQL reaches the model.** The recruiter assistant runs in two steps: the
model translates the question into constrained parameters (`ASSISTANT_QUERY_SCHEMA`),
then this app runs a permission-checked ORM query. A prompt injection hidden in a
CV cannot widen data access — the worst it can do is request a different filter,
which still runs under the reading user's permissions.

**Caching.** CV text is fingerprinted with SHA-256; identical text is never sent
to a provider twice. Scores fingerprint *both* the candidate profile and the job
requirements, so a score is reused only while neither has changed (§17). Both are
bypassable with `force=1`.

**Background jobs.** Parsing and scoring run in the `long` queue with
deduplicated job IDs, so uploading a CV never blocks the form (§16). Text
extraction runs synchronously so an unreadable file is reported immediately
rather than failing later in a worker.

**Failures are recorded, not swallowed.** Every worker writes `Failed` plus the
reason onto its document, so a recruiter can see what went wrong.

---

## Security

- API keys are `Password` fields — encrypted at rest, never serialised to a client
- Every AI call is server-side; no key or provider detail reaches JavaScript
- All whitelisted methods check `frappe.has_permission` before doing work
- The assistant additionally requires `read` on Job Applicant and returns at most
  25 records per answer
- Model output is HTML-escaped before rendering (a CV can contain anything)

---

## Testing

Provider adapters are stubbed in tests, so the suite runs with no API key and
makes no network calls. Verified behaviours include CV extraction from PDF and
DOCX, skill de-duplication, cache hit/invalidation, score clamping of malformed
model output, stage/status synchronisation, preservation of recruiter-authored
interview questions, and assistant filtering including an injection probe.

## Known limitations

- Scanned (image-only) PDFs are rejected — they need OCR first
- Legacy `.doc` is not supported; use `.docx` or PDF
- The assistant answers from AI-scored candidates, so an opening must be scored first
