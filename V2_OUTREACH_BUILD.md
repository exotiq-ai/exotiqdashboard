# Outreach Sequence Engine -- Phase 1 Build Task

## Context
You're extending the Exotiq Lead Intelligence Pipeline (already built). Read these first:
- `SPEC_CONCEPT_B.md` -- original spec
- `docs/OUTREACH_ENGINE_PHASE1.md` -- data model and UI design for this phase
- `db/schema.sql` -- existing SQLite schema
- `src/App.jsx` + `src/components/` -- existing React dashboard

## Project State
- 123 leads in SQLite at `db/exotiq.db`
- React dashboard on Netlify: exotiqdashboard.netlify.app
- GHL integration live (17+ leads pushed)
- Resend verified for `hello.exotiq.ai`

## Configuration
- Sending domain: hello.exotiq.ai
- From name: Gregory Ringler (or Gregory @ Exotiq)
- Reply-to: hello@exotiq.ai
- Sending windows: emails 9am-6pm local, DMs anytime, skip weekends for cold first touches
- Approval mode: approve-every-touch for Phase 1 (Gregory will flip switch to auto later)

## Your Tasks (build everything, ship nothing flaky)

### 1. Database Migration
Add to `db/schema.sql` and create `db/migrations/002_outreach_engine.sql`:
- `sequences` table (campaign definitions)
- `sequence_steps` table (ordered steps per sequence)
- `lead_sequences` table (which leads are in which campaigns)
- `outreach_queue` table (drafted outbound touches)
- `content_templates` table (reusable content blocks)

Full schema in `docs/OUTREACH_ENGINE_PHASE1.md`.

Run the migration against the existing `db/exotiq.db`.

### 2. Python Skill: Sequence Engine
Create `skills/sequence_engine.py`:
- `enroll_lead(lead_id, sequence_id)` -- add lead to sequence
- `process_due_touches()` -- find all leads with due touches, generate drafts, add to outreach_queue
- `draft_touch(lead_id, step_id)` -- use template + lead context to generate personalized content
- `skip_if_responded(lead_id)` -- check if lead responded since last touch, stop sequence if yes
- Integrate with existing `dashboard_sync.py` to export queue data

### 3. Seed Data
Populate 3 starter sequences and their steps:

**Sequence A: "New Operator 14-Day"** (default for Score 3-4)
- Day 0: IG DM (Template D / Peer angle)
- Day 3: Email (Jay Denver case study)
- Day 7: IG DM (Different angle / Event hook)
- Day 10: Email (Proof + soft CTA)
- Day 14: SMS (Final touch / "still worth 15 min?")

**Sequence B: "Score 5 Personal"** (default for Score 5)
- Day 0: IG DM (Template B / FOMO)
- Day 3: Gregory personal call (task for Gregory, not auto-sent)
- Day 7: Email (Jay quote + demo ask)

**Sequence C: "F1 Miami Event"** (manual trigger, Miami leads only, late April)
- Day 0: IG DM (event hook)
- Day 3: Email (event-specific value drop)
- Day 7: IG DM (close with event urgency)

Use these content templates (add to content_templates table):
- All V3 DM templates (B, D, E, F) from `DM_Strategy_V3.md`
- 3 Jay quotes from Gregory:
  1. "After 10 years in the exotic rental business, we finally have a system that gets what we need. Exotiq just works." -- Jay, Denver
  2. "I'm a fan. Exotiq saves me time in the office and out on the lot. That lets me focus on my customers, and that's what actually matters." -- Jay, Denver
  3. "Gregory pushed a custom update for me in 7 minutes. This software is a game-changer for the exotic rental business." -- Jay, Denver
- "Gregory picks up the phone" quote (strong differentiator)
- Punchy lines and longer case study pulls from `outreach_content_v2.md` (create this from the pulls Gregory sent)

### 4. React UI -- New "Sequences" Tab
Add a new tab between "Pipeline Funnel" and "Activity Feed":
- Sub-tabs: Campaigns | Active Enrollments | Queue Preview
- Campaigns: list of sequences with name, description, # active leads, # steps. Toggle active/paused. Create New button.
- Active Enrollments: table of lead_sequences with lead, sequence, current step, next touch due, status.
- Queue Preview: upcoming drafts grouped by day. Click into any draft to approve/edit/hold/skip.

### 5. Expanded Approval Queue
Current tab only shows initial DM drafts. Expand to show ALL outbound across all channels:
- Channel filter tabs: All / IG / FB / Email / SMS
- Each row: lead company, channel icon, scheduled time, preview, Approve / Edit / Hold / Skip buttons
- Preserve existing DM approval behavior for backwards compatibility

### 6. Lead Card: Sequence Panel
On expanded lead card, add new section "Sequences":
- Current active sequence(s)
- Full timeline of sends for this lead (channel, date, status)
- "Enroll in Sequence" button → opens modal with campaign picker

### 7. Netlify Function: Draft Approval
Create `netlify/functions/outreach-action.js`:
- POST endpoint accepting {queue_id, action: 'approve'|'edit'|'hold'|'skip', edited_content?}
- Writes pending action to `/tmp/outreach_actions.json` for Saul to process

### 8. Dashboard Sync Updates
`skills/dashboard_sync.py` should now export:
- `sequences.json` -- campaign definitions
- `outreach_queue.json` -- pending drafts
- `lead_sequences.json` -- enrollments
- Update `leads.json` to include each lead's active sequences

### 9. Tests
Pytest tests for:
- Sequence enrollment logic
- Due touch detection
- Skip-if-responded logic
- Content template rendering with lead context

### 10. Commit & Push
Commit messages should be clear. Push to origin main when done. Netlify will auto-deploy.

## Guardrails
- Do NOT send anything in Phase 1. Just queue drafts for approval.
- Do NOT overwrite existing lead data. Only add new tables and columns where noted.
- V3 compliance: reject drafts containing "18-35%", "$40K quarterly", "15+ hours saved" as generic claims. Jay's specific quote "7 minutes" etc. are OK.
- No em-dashes in any content. Use "--" or periods.
- Mobile-responsive UI, matches existing dark mode (#0A0A0F bg, #00D4AA accent).

## Report Back
When done, write `docs/PHASE1_OUTREACH_COMPLETE.md` with:
- What was built (file list)
- How to test each feature
- Known issues / follow-ups
- Screenshots if possible (describe UI state)
