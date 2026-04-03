# Exotiq Phase 1 + Phase 2: Data Layer + Core Skills Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the SQLite data layer and five core Python skills (discovery, enrichment, scoring, DM drafting, dashboard sync) for the Exotiq Lead Intelligence Pipeline.

**Architecture:** Flat SQLite database (`db/exotiq.db`) stores all lead data with provenance columns; a `skills/` package provides discrete callable modules that read/write via `skills/db_utils.py`; `skills/dashboard_sync.py` exports JSON to `public/data/` for the React dashboard.

**Tech Stack:** Python 3.10+, SQLite3 (stdlib), openpyxl, requests, flask (future use), pytest

---

## File Map

| File | Responsibility |
|------|---------------|
| `requirements.txt` | Python dependencies |
| `db/schema.sql` | All table DDL |
| `db/init_db.py` | Create db from schema |
| `db/migrate_xlsx.py` | Import xlsx leads into SQLite |
| `skills/__init__.py` | Package marker |
| `skills/db_utils.py` | get_db, log_activity, get_lead, update_lead |
| `skills/lead_discovery.py` | discover_leads(market, max_results) |
| `skills/lead_enrichment.py` | enrich_lead(lead_id) |
| `skills/lead_scoring.py` | score_lead(lead_id) |
| `skills/dm_drafting.py` | draft_dm(lead_id) |
| `skills/dashboard_sync.py` | sync_dashboard(output_dir) |
| `tests/test_db_utils.py` | Unit tests for db_utils |
| `tests/test_lead_scoring.py` | Unit tests for scoring rubric |
| `tests/test_dm_drafting.py` | Unit tests for template selection |
| `tests/test_dashboard_sync.py` | Unit tests for JSON export shapes |

---

### Task 1: requirements.txt + project skeleton

**Files:**
- Create: `requirements.txt`
- Create: `skills/__init__.py`
- Create: `tests/__init__.py`

- [ ] Write requirements.txt
- [ ] Create package markers
- [ ] Commit: `chore: add requirements and project skeleton`

---

### Task 2: db/schema.sql

**Files:**
- Create: `db/schema.sql`

- [ ] Write all four table DDL blocks (leads, activity_log, dm_drafts, ghl_sync_log)
- [ ] Verify every column from SPEC_QA_SCHEMA.md SQLite Column List is present
- [ ] Commit: `feat: add SQLite schema`

---

### Task 3: db/init_db.py

**Files:**
- Create: `db/init_db.py`

- [ ] Write init script that opens db/exotiq.db and executes schema.sql
- [ ] Run it: `python db/init_db.py`
- [ ] Commit: `feat: add database init script`

---

### Task 4: skills/db_utils.py + tests

**Files:**
- Create: `skills/db_utils.py`
- Create: `tests/test_db_utils.py`

- [ ] Write failing tests for get_db, log_activity, get_lead, update_lead
- [ ] Run tests: `pytest tests/test_db_utils.py -v` -- expect FAIL
- [ ] Implement db_utils.py
- [ ] Run tests: `pytest tests/test_db_utils.py -v` -- expect PASS
- [ ] Commit: `feat: add db_utils shared utilities`

---

### Task 5: db/migrate_xlsx.py

**Files:**
- Create: `db/migrate_xlsx.py`

- [ ] Write migration script with column mapping, phone detection, ID generation
- [ ] Handle: skip Export Summary, import metadata tabs, parse Enrichment Notes
- [ ] Output migration report to stdout
- [ ] Commit: `feat: add xlsx migration script`

---

### Task 6: skills/lead_discovery.py + tests

**Files:**
- Create: `skills/lead_discovery.py`
- Create: `tests/test_lead_discovery.py`

- [ ] Write failing test for dedup logic
- [ ] Implement discover_leads with web search stubs + dedup + activity logging
- [ ] Run tests: PASS
- [ ] Commit: `feat: add lead_discovery skill`

---

### Task 7: skills/lead_enrichment.py + tests

**Files:**
- Create: `skills/lead_enrichment.py`

- [ ] Implement enrich_lead with Apollo stub, web search stub, IG stub
- [ ] Field-level provenance tagging on every updated field
- [ ] Logs to activity_log and enrichment_history
- [ ] Commit: `feat: add lead_enrichment skill`

---

### Task 8: skills/lead_scoring.py + tests

**Files:**
- Create: `skills/lead_scoring.py`
- Create: `tests/test_lead_scoring.py`

- [ ] Write failing tests for scoring rubric (fleet 40%, IG 20%, web 15%, market 15%, depth 10%)
- [ ] Implement score_lead with previous_score preservation
- [ ] Run tests: PASS
- [ ] Commit: `feat: add lead_scoring skill`

---

### Task 9: skills/dm_drafting.py + tests

**Files:**
- Create: `skills/dm_drafting.py`
- Create: `tests/test_dm_drafting.py`

- [ ] Write failing tests for template selection logic
- [ ] Implement draft_dm with V2 templates, 150-word limit, no em-dashes
- [ ] Sets approval_status=PENDING, saves to dm_drafts
- [ ] Run tests: PASS
- [ ] Commit: `feat: add dm_drafting skill`

---

### Task 10: skills/dashboard_sync.py + tests

**Files:**
- Create: `skills/dashboard_sync.py`
- Create: `tests/test_dashboard_sync.py`

- [ ] Write failing tests for JSON output shapes
- [ ] Implement sync_dashboard: leads.json, activity.json, stats.json, ghl_sync_status.json, pipeline_metrics.json
- [ ] Run tests: PASS
- [ ] Commit: `feat: add dashboard_sync skill`

---

### Task 11: Smoke test end-to-end

- [ ] `python db/init_db.py` -- confirm db created
- [ ] `python -c "from skills.dashboard_sync import sync_dashboard; sync_dashboard()"` -- confirm JSON files written
- [ ] `python -c "import skills.lead_discovery, skills.lead_enrichment, skills.lead_scoring, skills.dm_drafting"` -- confirm all imports
- [ ] Commit: `chore: verify phase 1+2 smoke tests pass`
