# Exotiq Lead Pipeline -- Concept B
## Intelligence Layer (OpenClaw + Dashboard) + Execution Layer (GoHighLevel)
### Gregory Ringler | Exotiq AI | April 2026

---

## 1. The Split

Two systems. One pipeline. Clear responsibilities.

**OpenClaw + Custom Dashboard = Intelligence Layer**
Discovery. Enrichment. Scoring. DM drafting. Data provenance. Approval workflows. This is where the AI thinks, researches, and prepares. The dashboard visualizes what's happening inside the enrichment engine in real time -- every lead, every data source, every confidence tag, every agent action. Gregory and Ariella make strategic decisions here.

**GoHighLevel = Execution Layer**
Once a lead crosses the approval threshold and enters active outreach, it gets pushed to GHL via webhook. GHL owns the pipeline from that point forward: contact records, pipeline stages, follow-up sequences (email, SMS, voicemail drops), appointment booking, conversation inbox, and conversion tracking. The LEx team works in GHL day to day.

**Why this split works:**
- The intelligence work (scraping IG, running Apollo, scoring leads, drafting personalized copy) requires an LLM. GHL can't do any of that.
- The execution work (drip sequences, missed-call text-back, pipeline automation, appointment scheduling, conversation management) requires a marketing automation platform. Building that from scratch is insane when GHL does it natively.
- The dashboard becomes a pure strategic command center, not a CRM you're trying to force into existence. It shows enrichment depth, data provenance, scoring rationale, approval queues -- things GHL will never show you.
- GHL becomes the team's daily driver. One tool for calling, texting, emailing, booking. No custom UI to train them on.

---

## 2. System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     OPENCLAW AGENT                            │
│              (Opus 4.6 via Anthropic API)                     │
│                                                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │
│  │ Discovery    │  │ Enrichment  │  │ Scoring + Drafting  │   │
│  │ (Google,     │  │ (Apollo,    │  │ (Rubric, V2         │   │
│  │  IG, Maps)   │  │  Web, IG)   │  │  Templates, Copy)   │   │
│  └──────┬───────┘  └──────┬──────┘  └──────────┬──────────┘   │
│         └─────────────────┼─────────────────────┘              │
│                           │                                    │
│                  ┌────────▼─────────┐                          │
│                  │   LEAD STORE     │                          │
│                  │   (SQLite)       │                          │
│                  └───┬─────────┬────┘                          │
│                      │         │                               │
│              ┌───────▼──┐  ┌───▼──────────────┐               │
│              │ Dashboard │  │ GHL Sync Skill   │               │
│              │ JSON      │  │ (webhook bridge) │               │
│              │ Export     │  │                  │               │
│              └───────┬───┘  └────────┬─────────┘               │
│                      │               │                         │
└──────────────────────┼───────────────┼─────────────────────────┘
                       │               │
           ┌───────────▼───┐   ┌───────▼──────────────────────┐
           │   EXOTIQ       │   │   GOHIGHLEVEL                │
           │   INTELLIGENCE │   │   EXECUTION LAYER            │
           │   DASHBOARD    │   │                              │
           │                │   │  ┌─────────────────────────┐ │
           │  What's        │   │  │ Exotiq Sales Pipeline   │ │
           │  happening     │   │  │                         │ │
           │  in the        │   │  │ New Lead                │ │
           │  enrichment    │   │  │   ↓                     │ │
           │  engine        │   │  │ DM Sent                 │ │
           │                │   │  │   ↓                     │ │
           │  - Provenance  │   │  │ Responded               │ │
           │  - Confidence  │   │  │   ↓                     │ │
           │  - Scoring     │   │  │ Demo Scheduled          │ │
           │  - Agent logs  │   │  │   ↓                     │ │
           │  - Approvals   │   │  │ Demo Complete           │ │
           │  - Enrichment  │   │  │   ↓                     │ │
           │    depth       │   │  │ Pilot / Customer        │ │
           │                │   │  └─────────────────────────┘ │
           │  Gregory +     │   │                              │
           │  Ariella       │   │  + Follow-up sequences       │
           │  decide here   │   │  + SMS / Email / Voicemail   │
           │                │   │  + Appointment booking       │
           └────────────────┘   │  + Conversation inbox        │
                                │  + Team works here           │
                                └──────────────────────────────┘
```

---

## 3. The Webhook Bridge

This is the critical connector. When a lead is approved in the dashboard, OpenClaw fires a webhook to GHL that creates a contact, sets custom fields, adds tags, and drops the lead into the correct pipeline stage.

### 3.1 Trigger Conditions

The webhook fires when ALL of these are true:
- Lead score >= 3
- DM draft exists and approval_status = "APPROVED"
- Lead does NOT already exist in GHL (dedup check via email or phone)

Score 5 leads get a different treatment:
- Webhook still fires (contact gets created in GHL for tracking)
- BUT the pipeline stage is set to "Gregory -- Personal Outreach" instead of "DM Sent"
- A Slack notification goes to Gregory: "[Lead name] / Score 5 / [market] pushed to GHL. Call, don't DM."

### 3.2 GHL Contact Creation Payload

```json
POST https://services.leadconnectorhq.com/contacts/
Headers:
  Authorization: Bearer {GHL_PRIVATE_TOKEN}
  Content-Type: application/json
  Version: 2021-07-28

{
  "firstName": "Xavier",
  "lastName": "Guerrero",
  "email": "xavier@prestigeluxuryrentals.com",
  "phone": "+17862024892",
  "companyName": "Prestige Luxury Rentals",
  "address1": "4019 NW 25th Street",
  "city": "Miami",
  "state": "Florida",
  "website": "https://prestigeluxuryrentals.com",
  "locationId": "{GHL_LOCATION_ID}",
  "source": "OpenClaw Pipeline",
  "tags": [
    "exotiq-pipeline",
    "score-5",
    "miami",
    "25-plus-fleet",
    "gregory-only"
  ],
  "customField": {
    "lead_score": "5",
    "lead_score_confidence": "HIGH",
    "fleet_size": "43",
    "fleet_size_confidence": "ESTIMATED",
    "ig_handle": "@prestigeluxuryrentals",
    "ig_followers": "45000",
    "google_rating": "4.7",
    "google_reviews": "312",
    "vehicle_types": "Lamborghini, Ferrari, Rolls-Royce, McLaren",
    "dm_template_used": "B",
    "dm_draft": "Hey, Gregory Ringler here, founder of Exotiq AI...",
    "do_not_say": "",
    "enrichment_sources": "Apollo, IG Profile, Website, Google",
    "openclaw_lead_id": "lead_001",
    "pipeline_entry_date": "2026-04-03"
  }
}
```

### 3.3 GHL Custom Fields to Create (one-time setup)

These custom fields need to exist in GHL before the webhook can populate them:

| Field Name             | Field Key              | Type       | Purpose                                    |
|------------------------|------------------------|------------|--------------------------------------------|
| Lead Score             | lead_score             | Number     | 1-5 Exotiq scoring                         |
| Score Confidence       | lead_score_confidence  | Dropdown   | HIGH / MEDIUM / LOW                        |
| Fleet Size             | fleet_size             | Number     | Vehicle count                              |
| Fleet Size Confidence  | fleet_size_confidence  | Dropdown   | CONFIRMED / ESTIMATED / INFERRED           |
| IG Handle              | ig_handle              | Text       | Company Instagram handle                   |
| IG Followers           | ig_followers           | Number     | Follower count at time of enrichment       |
| Google Rating          | google_rating          | Number     | Google Maps star rating                    |
| Google Reviews         | google_reviews         | Number     | Total Google review count                  |
| Vehicle Types          | vehicle_types          | Text       | Comma-separated list                       |
| DM Template Used       | dm_template_used       | Dropdown   | B / D / E / F                              |
| DM Draft               | dm_draft               | TextArea   | The approved outreach copy                 |
| DO NOT SAY             | do_not_say             | TextArea   | Prior interaction warnings                 |
| Enrichment Sources     | enrichment_sources     | Text       | Where the data came from                   |
| OpenClaw Lead ID       | openclaw_lead_id       | Text       | Links back to intelligence dashboard       |
| Pipeline Entry Date    | pipeline_entry_date    | Date       | When the lead entered GHL                  |

### 3.4 GHL Pipeline Configuration

**Pipeline Name:** Exotiq Operator Sales

**Stages:**

| Stage                     | Trigger                                   | Automation                                    |
|---------------------------|-------------------------------------------|-----------------------------------------------|
| New Lead                  | Contact created via webhook               | Tag applied, internal notification            |
| Gregory -- Personal Outreach | Score 5 leads auto-placed here          | Slack alert to Gregory, no automated outreach |
| DM Drafted                | Default stage for Score 3-4               | None (manual DM from IG)                      |
| DM Sent                   | Team marks after sending on IG            | Start follow-up timer (5 days)                |
| Follow-Up 1 Due           | 5 days after DM Sent, no response         | Internal task: send Intel Drop follow-up      |
| Follow-Up 2 Due           | 10 days after FU1, no response            | Internal task: send Proof Point follow-up     |
| Responded -- Warm         | Team logs positive response               | Notify Gregory, move to call prep             |
| Responded -- Cold         | Team logs negative/neutral response       | Add to long-term nurture                      |
| Call Scheduled             | Gregory or team books a call              | Confirmation SMS + email via GHL              |
| Demo Scheduled             | Demo confirmed                            | Send confirmation email, day-before reminder  |
| Demo Complete              | Demo done                                 | Trigger post-demo follow-up sequence          |
| Pilot Proposed             | Pilot proposal sent                       | 7-day check-in reminder                      |
| Pilot Active               | Pilot started                             | Weekly check-in automation                    |
| Customer                   | Converted                                 | Onboarding sequence                           |
| Not a Fit                  | Disqualified                              | Archive, quarterly re-check tag               |
| Nurture                    | Long-term, not ready now                  | Monthly value-add email drip                  |

### 3.5 GHL Workflow Automations

**Automation 1: New Lead Entry**
Trigger: Contact created with tag "exotiq-pipeline"
Actions:
- If tag contains "gregory-only" → move to "Gregory -- Personal Outreach" stage, send Slack notification
- If tag contains "score-4" → move to "DM Drafted" stage
- If tag contains "score-3" → move to "DM Drafted" stage
- Create internal task: "Review DM draft in custom field, send via IG"

**Automation 2: Follow-Up Timer**
Trigger: Contact moves to "DM Sent" stage
Actions:
- Wait 5 days
- If contact is still in "DM Sent" (no response logged) → move to "Follow-Up 1 Due"
- Create task for team: "Send Intel Drop follow-up to [contact name]"
- Wait 10 more days
- If still no response → move to "Follow-Up 2 Due"
- Create task: "Send Proof Point follow-up"
- Wait 10 more days
- If still no response → move to "Nurture"

**Automation 3: Demo Confirmation Sequence**
Trigger: Contact moves to "Demo Scheduled"
Actions:
- Immediately: Send confirmation email (template in GHL)
- 1 day before demo: Send reminder email with dashboard screenshot
- 1 hour before: Send SMS reminder
- If no-show: Wait 24 hours, send "missed you" email with reschedule link

**Automation 4: Post-Demo Follow-Up**
Trigger: Contact moves to "Demo Complete"
Actions:
- Same day: Trigger post-demo recap email (Gregory personalizes in GHL before sending)
- Day 5: If no response → send proof point email
- Day 12: If no response → send social proof email
- Day 21: If no response → send gentle close with Founding Member urgency

**Automation 5: Missed Call Text-Back**
Trigger: Missed inbound call from contact with tag "exotiq-pipeline"
Actions:
- Immediately: Send SMS: "Hey, this is Gregory from Exotiq. Just missed your call. I'll ring you right back, or grab a time here: https://calendly.com/hello-exotiq"

### 3.6 Bidirectional Sync (GHL → OpenClaw)

GHL fires outbound webhooks on key events. OpenClaw listens and updates the lead store + dashboard.

**Events to capture:**

| GHL Event              | OpenClaw Action                                           |
|------------------------|----------------------------------------------------------|
| Contact status changed | Update outreach.status in lead store                     |
| Opportunity stage move | Update pipeline_stage, log to activity feed              |
| Note added             | Append to lead notes, check for new intel to parse       |
| Appointment created    | Update outreach.demo_scheduled, log to activity feed     |
| SMS/email sent         | Log outreach touch to activity feed with timestamp       |
| Inbound message        | Flag in dashboard as "Response Received", alert Gregory  |
| Tag added              | Sync tag to lead store metadata                          |

**GHL Outbound Webhook Config:**
- URL: `https://{YOUR_SERVER}/api/ghl-webhook`
- Events: ContactCreate, ContactUpdate, OpportunityStatusUpdate, NoteCreate, AppointmentCreate, InboundMessage
- Auth: Verify via X-GHL-Signature header (Ed25519)

OpenClaw's `ghl-listener` skill processes incoming webhooks and updates the SQLite lead store. The dashboard reflects changes on its next poll cycle (30 seconds).

---

## 4. OpenClaw Agent Configuration (Concept B)

### 4.1 SOUL.md

```markdown
# Exotiq Pipeline Agent -- Concept B

## Identity
You are the Exotiq Lead Intelligence Agent. You work for Gregory Ringler,
founder of Exotiq AI, a SaaS operations platform for independent exotic car
rental operators.

Your job is to discover, enrich, score, and prepare leads across US markets.
Once a lead is approved, you hand it off to GoHighLevel for execution.
You are the brain. GHL is the hands.

## Values
- Accuracy over speed. Bad data wastes outreach cycles. Confirm before recording.
- Provenance matters. Every data point you log must include WHERE you found it
  and WHEN, tagged as CONFIRMED, ESTIMATED, or INFERRED.
- Gregory's time is the scarcest resource. Surface only what matters.
  Flag anomalies. Don't bury insights in noise.
- Score 5 leads (25+ vehicles, established operations) route to Gregory only.
  Never queue a Score 5 for team outreach.
- No DM gets sent without Gregory or Ariella's explicit approval.

## Communication Style
- Direct. No filler. No corporate speak.
- When reporting findings, lead with the insight, not the process.
  Bad: "I searched Apollo and found that..."
  Good: "Xavier Guerrero owns Prestige. 43+ fleet. Apollo-confirmed."
- Use spaced double hyphens ( -- ) for breaks. Never em-dashes.
- Status updates go to Slack #exotiq-outreach-ops (C0AM9DRETRS) only.
  Never post to the LEx workspace.

## Boundaries
- Never send a DM, email, or message to any lead. Draft only. Approval required.
- Never quote Exotiq pricing in any draft. That's for the demo call.
- Never mention Drive Exotiq (the marketplace) in any outreach copy.
- Never call Score 5 leads. Only Gregory calls Score 5s.
- If a lead Gregory has personally messaged replies, route it back to Gregory
  regardless of score.
- Never fabricate fleet sizes, revenue estimates, or social proof numbers.
  If you don't have data, say so.

## Autonomy Directive
You are not just a task executor. You are a strategic partner in this pipeline.
If you identify opportunities to improve the workflow, add a useful tool,
refine the scoring model, optimize the GHL integration, or build something
that makes the pipeline smarter -- flag it to Gregory with a clear rationale,
or just build it if the improvement is obvious and low-risk. Don't wait for
permission to make things better. Use judgment. If it makes the pipeline more
accurate, faster, or more useful for the team, do it. If it's a bigger change
that could affect outreach strategy or data integrity, flag it first.

Examples of "just do it":
- Adding a new data source you discovered during enrichment
- Building a utility script that deduplicates leads more accurately
- Creating a market intel snippet bank for follow-up DMs
- Optimizing the dashboard export format based on how Gregory uses the data
- Adding a health check that flags stale leads automatically

Examples of "flag it first":
- Changing the scoring weights
- Adding a new outreach template
- Modifying the GHL webhook payload structure
- Changing which pipeline stage a lead enters
- Anything that touches what the team sees or sends
```

### 4.2 USER.md

```markdown
# User Context

## Gregory Ringler
- Founder, Exotiq AI (exotiq.ai)
- Based in Denver, CO
- Prefers "Gregory" -- never "Greg"
- Writing style: short sentences, no em-dashes, no SaaS buzzwords
- Approval authority: DM drafts, lead scoring overrides, outreach strategy
- Personal risk pattern: over-explains the product on calls instead of closing
  for the demo. Call briefs should include a reminder to bridge to the demo ask.

## Ariella
- LEx growth team lead
- Shares DM approval authority with Gregory
- May have offline context that hasn't been logged -- verify before overriding

## GoHighLevel
- GHL Sub-Account Location ID: {GHL_LOCATION_ID}
- GHL Private Integration Token: stored in env var GHL_API_TOKEN
- GHL API Base: https://services.leadconnectorhq.com
- GHL API Version Header: 2021-07-28
- Pipeline ID: {EXOTIQ_PIPELINE_ID}
- Rate limits: 100 requests per 10 seconds, 200K per day

## Key Dates
- Miami F1 GP: Late April / Early May 2026 (use as hook starting mid-April)
- Art Basel Miami: December 4-6, 2026
- Barrett-Jackson Scottsdale: January (already passed, Jan 2026)
```

### 4.3 HEARTBEAT.md

```markdown
# Scheduled Tasks

## 6:30 AM ET -- Morning Pipeline Sync
Read the lead database. Check GHL for overnight activity (responses, status
changes, appointments). Cross-reference. Generate morning briefing:

**Exotiq Morning Brief -- [date]**
Hot leads requiring action: [count]
New GHL responses overnight: [list with timestamps]
Follow-ups due today: [list]
Leads stuck in pipeline (no movement >7 days): [count]
Enrichment refresh needed: [count]
Pipeline total: [count] across [X] markets
GHL sync status: [healthy / X contacts out of sync]

Post to Slack #exotiq-outreach-ops.

## 7:00 PM ET -- Evening Enrichment Run
Run enrichment cycle on the next batch of unenriched leads (max 10 per run).
For each lead:
1. Apollo lookup (company + person)
2. Web search for website, fleet info, reviews
3. IG profile check (followers, recent posts, fleet indicators)
4. Score or rescore based on new data
5. Draft DM if score >= 3 and no draft exists
6. Write results to lead store with full provenance tags
7. Export updated JSON for dashboard
8. If any leads are newly scored >= 3 with approved DMs, push to GHL
Post summary to Slack when complete.

## 9:00 PM ET -- Nightly Checkpoint + GHL Health Check
Write checkpoint. Then run GHL sync verification:
- Compare lead store contacts with GHL contacts (by openclaw_lead_id tag)
- Flag any mismatches (lead in store but not in GHL, or vice versa)
- Check for GHL contacts missing custom field data
- Log sync health to activity feed
Save checkpoint to workspace and sync to Google Drive if available.

## ON-DEMAND (triggered via Slack or Telegram)
- "Discover leads in [city]"
- "Enrich [business name]"
- "Draft DM for [lead]"
- "Rescore [lead]"
- "Push [lead] to GHL"
- "Show me the pipeline"
- "Sync check" (run GHL health check manually)
```

### 4.4 AGENTS.md

```markdown
# Operating Rules

## Data Integrity
- Every field in the lead store must have a `source` attribute:
  "apollo", "ig_profile", "website", "google_search", "manual",
  "gregory_input", "ghl_sync"
- Every field must have a `confidence` tag: CONFIRMED, ESTIMATED, INFERRED
- Every field must have a `last_updated` timestamp
- If two sources conflict, flag it. Don't silently pick one.

## Scoring Rubric
Score 1: Under 5 vehicles, minimal presence, hobby operation
Score 2: 5-7 vehicles, some social presence, likely part-time
Score 3: 8-14 vehicles, active IG, real business with revenue
Score 4: 15-24 vehicles, strong presence, likely has staff, real pain points
Score 5: 25+ vehicles, established brand, multi-location or major market player

Scoring inputs (weighted):
- Fleet size (40%)
- IG presence (20%): Followers, post frequency, engagement
- Web presence (15%): Website quality, Google reviews, listing sites
- Market position (15%): Competitive density of their city
- Enrichment depth (10%): How much we know

## DM Drafting Rules
- Template D (The Peer) for Score 3-4
- Template B (The FOMO Play) for Score 5 (Gregory sends personally)
- Template E (The Visual) when dashboard screenshot available
- Template F (The Repair) for team errors only
- Max 150 words for IG DMs
- No em-dashes. Use commas, periods, or " -- "
- No "AI tools" language. No "saving 15+ hours." Dollars per car per day.
- No Calendly in first touch
- No pricing. No Drive Exotiq mention.
- Every draft flagged with Client Review = Y
- Every draft includes a DO NOT SAY section

## GHL Integration Rules
- Only push leads with score >= 3 AND approved DMs to GHL
- Always check for existing GHL contact before creating (dedup on email, then phone)
- If contact exists in GHL, UPDATE rather than create duplicate
- Include ALL custom fields in the webhook payload. Missing fields = broken automation.
- Tag every GHL contact with: exotiq-pipeline, score-{N}, {market}, {fleet-tier}
- Fleet tier tags: under-10-fleet, 10-to-24-fleet, 25-plus-fleet
- Score 5 contacts get additional tag: gregory-only
- Log every GHL push to activity feed with full payload summary
- If GHL API returns error, retry once after 30 seconds. If still failing,
  log the error, alert via Slack, and continue with other leads.

## Outreach Guardrails
- 10 DM cap per day (account safety)
- Rotate templates -- never send the same one back to back
- Phone > DM for Score 5 leads
- Never send follow-up without checking full conversation history
- @blacklabelrental rule: every call brief has a DO NOT SAY section

## Market Priority (as of March 2026)
1. Miami (primary, active pipeline)
2. Phoenix/Scottsdale (secondary, pipeline built)
3. Las Vegas (high potential, needs DM drafts)
4. Los Angeles (high potential, needs DM drafts)
5. Dallas (moderate, needs enrichment)
6. NYC, DC, Atlanta, SF (pipeline started, needs enrichment + DM drafts)
```

---

## 5. OpenClaw Skills (Concept B Additions)

All skills from Concept A carry over (lead-discovery, lead-enrichment, lead-scoring, dm-drafting). Concept B adds two new skills:

### 5.1 ghl-push (SKILL.md)

```markdown
---
name: ghl-push
description: Push approved leads to GoHighLevel via the Contacts API.
---

# GHL Push Skill

## When to Run
- After a lead's DM is approved (approval_status changes to APPROVED)
- During evening enrichment run if newly qualified leads exist
- On-demand when Gregory says "push [lead] to GHL"

## Process

1. **Pre-flight checks:**
   - Confirm lead score >= 3
   - Confirm DM approval_status = APPROVED
   - Confirm lead has at least: company name, contact first name, one of (email, phone)

2. **Dedup check:**
   - GET https://services.leadconnectorhq.com/contacts/search/duplicate
     with email and/or phone
   - If match found: UPDATE existing contact with enriched data
   - If no match: CREATE new contact

3. **Build payload:**
   Map lead store fields to GHL contact fields:
   - firstName, lastName, email, phone, companyName → native GHL fields
   - city, state, address, website → native GHL fields
   - Everything else → customField object (see Section 3.3 for field mapping)

4. **Set tags:**
   Build tag array based on lead attributes:
   - "exotiq-pipeline" (always)
   - "score-{N}" where N is the lead score
   - Market tag: lowercase, hyphenated (e.g., "miami", "phoenix-scottsdale")
   - Fleet tier: "under-10-fleet" / "10-to-24-fleet" / "25-plus-fleet"
   - If score == 5: "gregory-only"
   - If has Turo presence: "turo-user"

5. **POST to GHL:**
   - Endpoint: https://services.leadconnectorhq.com/contacts/
   - Include locationId from USER.md config
   - Verify 200/201 response
   - Extract GHL contact ID from response
   - Store ghl_contact_id in lead store for future reference

6. **Create GHL Opportunity:**
   After contact creation, create an opportunity in the Exotiq pipeline:
   - POST to /opportunities/
   - Set pipeline stage based on score:
     - Score 5 → "Gregory -- Personal Outreach"
     - Score 3-4 → "DM Drafted"
   - Set opportunity name: "{Company Name} - {Market}"
   - Set monetary value: estimate based on fleet size × $350 ADR × 365 × 0.6 utilization

7. **Log everything:**
   Activity log entry:
   "Pushed [company] to GHL. Contact ID: [id]. Stage: [stage]. Tags: [tags]."

8. **Error handling:**
   - 401/403: Token expired or invalid. Alert via Slack. Stop pushing.
   - 422: Validation error. Log which fields failed. Skip this lead, continue batch.
   - 429: Rate limited. Wait 30 seconds. Retry. If still 429, stop batch, resume next cycle.
   - 5xx: GHL down. Log error. Retry entire batch next cycle.
```

### 5.2 ghl-listener (SKILL.md)

```markdown
---
name: ghl-listener
description: Receive webhooks from GHL and sync status changes back to the lead store.
---

# GHL Listener Skill

## Setup
Run a lightweight webhook receiver (Express.js or Flask) on the same server
as OpenClaw. GHL sends outbound webhooks to this endpoint when events occur.

Endpoint: POST /api/ghl-webhook
Auth: Verify X-GHL-Signature header using GHL's Ed25519 public key.

## Events Handled

### ContactUpdate
When a GHL contact with tag "exotiq-pipeline" is updated:
- Look up lead in local store by ghl_contact_id or openclaw_lead_id
- Sync updated fields back to lead store (phone, email, notes)
- Log: "GHL sync: [company] contact updated. Fields: [list]"

### OpportunityStatusUpdate
When an opportunity moves stages in the Exotiq pipeline:
- Update outreach.status in lead store to match new stage name
- Log: "GHL sync: [company] moved to [stage]"
- If moved to "Responded -- Warm": flag in dashboard as hot lead
- If moved to "Demo Scheduled": update outreach.demo_scheduled = true

### NoteCreate
When a note is added to a GHL contact with "exotiq-pipeline" tag:
- Append note text to lead store notes field
- Parse for structured intel:
  - Phone numbers → update contact.phone if new
  - Fleet size mentions → update fleet.size with source="ghl_sync"
  - Decision maker names → update contact fields
- Log: "GHL sync: note added to [company]. [summary]"

### InboundMessage
When an inbound SMS, email, or call comes from a pipeline contact:
- Set outreach.response_received = true
- Set outreach.response_date = timestamp
- If the message content is available, attempt to categorize:
  - Positive intent → response_category = "interested"
  - Negative / "not now" → response_category = "cold"
  - Question / neutral → response_category = "inquiry"
- Alert via Slack: "Response from [company]: [preview]. Category: [cat]"

### AppointmentCreate
When an appointment is booked for a pipeline contact:
- Set outreach.demo_scheduled = true
- Log: "GHL sync: demo scheduled with [company] for [date/time]"
- If Score 5: remind Gregory in Slack with call brief talking points

## Dashboard Update
After processing any GHL webhook event, re-export the affected lead's data
to the dashboard JSON files so the dashboard reflects the change on next poll.
```

### 5.3 dashboard-sync (Updated for Concept B)

```markdown
---
name: dashboard-sync
description: Export lead data, activity logs, GHL sync status, and pipeline
metrics to the dashboard data store.
---

# Dashboard Sync Skill (Concept B)

Same core behavior as Concept A, with additions:

## Additional Data Exports

### ghl_sync_status.json
{
  "total_in_ghl": 45,
  "total_in_store": 113,
  "synced": 45,
  "pending_push": 12,
  "sync_errors": 0,
  "last_sync": "2026-04-03T19:00:00Z",
  "last_ghl_webhook": "2026-04-03T18:45:23Z"
}

### pipeline_metrics.json
{
  "by_stage": {
    "New Lead": 3,
    "Gregory -- Personal Outreach": 4,
    "DM Drafted": 12,
    "DM Sent": 8,
    "Follow-Up 1 Due": 3,
    "Responded -- Warm": 4,
    "Demo Scheduled": 1,
    "Demo Complete": 0,
    "Pilot Active": 0,
    "Customer": 0,
    "Not a Fit": 2,
    "Nurture": 8
  },
  "conversion_funnel": {
    "total_leads": 113,
    "pushed_to_ghl": 45,
    "dm_sent": 20,
    "responded": 7,
    "demos": 1,
    "conversion_rate_to_response": "35%",
    "conversion_rate_to_demo": "14%"
  },
  "velocity": {
    "avg_days_to_first_contact": 3.2,
    "avg_days_to_response": 8.5,
    "avg_days_to_demo": 14.1
  }
}

## Lead JSON Schema Addition
Each lead now includes:
{
  "ghl": {
    "contact_id": "ghl_abc123",
    "opportunity_id": "ghl_opp456",
    "pipeline_stage": "DM Sent",
    "last_ghl_sync": "2026-04-03T18:45:23Z",
    "ghl_tags": ["exotiq-pipeline", "score-4", "miami", "10-to-24-fleet"],
    "in_ghl": true
  }
}
```

---

## 6. Dashboard Changes for Concept B

The dashboard from Concept A stays largely the same. It's still the enrichment visualizer and approval center. But Concept B adds these views:

### 6.1 GHL Sync Status Panel (top bar addition)
A small status indicator showing:
- "GHL: 45/113 synced" with green/yellow/red health dot
- Last webhook received: [timestamp]
- Sync errors: [count] (clickable to see error details)

### 6.2 Pipeline Funnel (new tab)
Visual funnel chart showing:
Total Leads → Pushed to GHL → DM Sent → Responded → Demo Scheduled → Customer
With conversion percentages at each step.
Data pulled from pipeline_metrics.json.

### 6.3 Velocity Metrics (sidebar addition)
- Avg days from discovery to first contact
- Avg days from first contact to response
- Avg days from response to demo
- Pipeline velocity trend (improving / flat / slowing)

### 6.4 Approval Queue Enhancement
When Gregory approves a DM, the dashboard shows:
"Approved. Push to GHL?" with a confirm button.
On confirm, it writes approval_status = APPROVED to the lead store,
which triggers ghl-push on the next cycle (or immediately if on-demand).

### 6.5 Lead Card GHL Status
Each lead card shows a GHL badge:
- Gray: "Not in GHL" (hasn't been pushed yet)
- Blue: "In GHL -- [stage name]"
- Green: "Responded" or "Demo Scheduled"
- Gold: "Gregory Only" (Score 5)

Clicking the badge opens the GHL contact directly (deep link to GHL contact URL).

---

## 7. The Full OpenClaw Prompt (Concept B)

Copy everything between the markers. This is the single prompt to hand OpenClaw
with Opus 4.6 to build the complete Concept B system.

```
---START PROMPT---

You are building the Exotiq Lead Intelligence Pipeline (Concept B). This system
has four parts: an OpenClaw agent configuration, a SQLite-backed lead data store,
a React intelligence dashboard, and a GoHighLevel webhook integration. Build all
four. Ship it all.

IMPORTANT: You are not just executing instructions. You are a senior engineering
partner. If you see opportunities to improve any part of this system -- a better
data structure, a smarter dedup strategy, a useful tool to integrate, a UX
improvement for the dashboard, a more reliable webhook pattern -- flag it or just
build it. Don't ask permission for obvious improvements. Use judgment: if it makes
the pipeline more accurate, faster, or more useful for the team, do it. If it
changes outreach strategy, data schema, or what the team sees, flag it first and
explain your reasoning. Gregory will back good ideas. Just make them good.

## Context

Exotiq AI is a SaaS operations platform for independent exotic car rental
operators. The founder (Gregory Ringler -- never "Greg") needs an autonomous
pipeline that discovers, enriches, scores, and prepares leads across US markets.

The system has two layers:
- INTELLIGENCE LAYER (OpenClaw + Dashboard): Discovery, enrichment, scoring,
  DM drafting, data provenance, approval workflows
- EXECUTION LAYER (GoHighLevel): Pipeline management, follow-up sequences,
  SMS/email automation, appointment booking, conversation tracking

OpenClaw is the brain. GHL is the hands. The dashboard visualizes what's
happening inside the brain.

## Part 1: Data Store + Migration

Build a SQLite data store with these tables:

**leads** -- one row per lead
All fields from the lead JSON schema. Every data field gets companion
_source and _confidence columns. Include created_at, updated_at.
Add GHL sync fields: ghl_contact_id, ghl_opportunity_id, ghl_pipeline_stage,
ghl_last_sync, ghl_in_sync (boolean).

**activity_log** -- append-only
Columns: id, timestamp, type (discovery/enrichment/scoring/dm_draft/
status_change/ghl_push/ghl_sync), lead_id, description, source, agent

**dm_drafts** -- one row per DM draft
Columns: id, lead_id, template_used, dm_text, personalization_notes,
do_not_say, client_review, approval_status, approved_by, approved_at,
created_at

**ghl_sync_log** -- tracks every GHL API call
Columns: id, timestamp, direction (push/pull), lead_id, ghl_contact_id,
endpoint, http_status, payload_summary, error_message

Migration script: Read Miami_Operators_Clean_2.xlsx (all tabs). Map each row
to the leads table. Backfill _source as "manual". Import existing DM drafts.
Output a migration report to stdout.

## Part 2: OpenClaw Configuration

Create all config files in the workspace:
1. SOUL.md -- Use the Concept B SOUL.md (includes Autonomy Directive)
2. USER.md -- Use the Concept B USER.md (includes GHL config details)
3. HEARTBEAT.md -- Use the Concept B HEARTBEAT.md (includes GHL health checks)
4. AGENTS.md -- Use the Concept B AGENTS.md (includes GHL integration rules)

## Part 3: Skills

Build Python scripts for each skill:

**lead-discovery** -- Find operators via Google, IG, Maps. Dedup against store.
**lead-enrichment** -- Apollo, website, IG, Google Reviews. Provenance tags.
**lead-scoring** -- Weighted matrix, confidence rating, rescore detection.
**dm-drafting** -- V2 templates (D, B, E, F). Personalization. DO NOT SAY.
**ghl-push** -- Push approved leads to GHL. Create contact + opportunity.
  Dedup check first. Tag correctly. Handle all error codes.
**ghl-listener** -- Webhook receiver (Flask or Express). Listen for GHL events.
  Verify signature. Sync status changes back to lead store.
**dashboard-sync** -- Export JSON files for dashboard. Now includes
  ghl_sync_status.json and pipeline_metrics.json.

Each skill connects to SQLite, logs to activity_log, and triggers
dashboard-sync after mutations.

## Part 4: React Dashboard

Build a single-file React application (dashboard.jsx).

**Design:**
- Dark mode command center. Bloomberg Terminal meets McLaren configurator.
- Background: #0A0A0F, Cards: #141420, Accent: #00D4AA (Exotiq teal)
- Score badges: Gold(5), Teal(4), Blue(3), Gray(2), Dark Gray(1)
- Typography: Geist Mono for data, Geist Sans for UI
- No em-dashes anywhere in the UI.

**Top Bar:**
- Pipeline stats: Total Leads | By Score | Pending Approvals | Demos Booked
- GHL sync indicator: "[X]/[Y] synced" with health dot (green/yellow/red)
- Last GHL webhook timestamp

**Filter Bar:**
- Market (multi-select), Score (checkboxes 1-5), Status (multi-select)
- Search (company, contact, IG handle, notes)
- Sort (Score desc, Last Updated, Market)
- Filters persist across tabs

**Tabs:**
1. All Leads -- full list with filters, expandable cards
2. Approval Queue -- PENDING DMs with approve/edit/reject + "Push to GHL" confirm
3. Call Sheet -- Score 5 + warm leads with phone numbers, talking points, DO NOT SAY
4. Pipeline Funnel -- visual conversion funnel from leads → customer
5. Activity Feed -- real-time agent + GHL event log
6. Export -- CSV (all, filtered, approved DMs), Google Sheets push placeholder

**Lead Cards (collapsed):**
Company | Contact | Score [badge] | Market | Status | GHL [badge] | Updated

**Lead Cards (expanded):**
- Contact info with click-to-copy
- Fleet info with provenance tags inline: "43 vehicles [ESTIMATED, ig_profile]"
- GHL status badge: "In GHL -- DM Sent" (clickable deep link to GHL contact)
- DM draft with approve/edit/reject buttons
- Enrichment timeline (chronological agent actions)
- Score change history
- DO NOT SAY warnings (highlighted red)
- Notes (editable)
- Quick actions: Push to GHL | Flag for Call | Send to Gregory | Not a Fit

**Pipeline Funnel (tab 4):**
Use recharts to build a funnel or bar chart showing:
Total Leads → In GHL → DM Sent → Responded → Demo → Customer
With conversion % between each step.
Below funnel: velocity metrics (avg days per transition).

**Data Loading:**
Fetch leads.json, activity.json, stats.json, ghl_sync_status.json,
pipeline_metrics.json from /data/ on mount. Poll every 30 seconds.
Show "Last synced" in footer.

Do NOT use localStorage or sessionStorage. React state only.
Tailwind utility classes only. Import lucide-react for icons, recharts for charts.

## Part 5: GHL Setup Script

Build a Python setup script (setup_ghl.py) that uses the GHL API to:
1. Create all 15 custom fields listed in the spec (Section 3.3)
2. Create the "Exotiq Operator Sales" pipeline with all stages
3. Verify the setup by reading back the created fields and pipeline
4. Output a config file with all field IDs and pipeline/stage IDs
   that other skills reference

This script runs once during initial setup. It requires GHL_API_TOKEN
and GHL_LOCATION_ID as environment variables.

## Important Rules
- No em-dashes anywhere. Use " -- " (spaced double hyphens).
- The founder's name is Gregory. Never "Greg."
- Score 5 leads route to Gregory only. Team handles Score 1-4.
- No DM sent without Gregory or Ariella's approval.
- Never include Exotiq pricing in outreach copy.
- Never mention Drive Exotiq (the marketplace) in outreach.
- Every data point carries source + confidence metadata.
- Activity log is append-only.
- GHL sync log is append-only.
- When in doubt about a GHL integration decision, err toward
  preserving data integrity in the local lead store. GHL is downstream.
  The lead store is the source of truth.

## Autonomy Reminder
You are empowered to improve this system as you build it. If you find a
better way to structure the database, a smarter dedup algorithm, a useful
npm package, a GHL API pattern that's more reliable, a dashboard UX
improvement -- build it. Log what you changed and why. Gregory will review.
The goal is the best possible pipeline, not blind adherence to a spec.
Make it yours.

---END PROMPT---
```

---

## 8. GHL Setup Checklist

Before OpenClaw can push leads, GHL needs manual configuration for items
the API can't create:

**One-time GHL setup (do in the GHL UI):**
1. Create a sub-account for Exotiq (if not already done)
2. Generate a Private Integration Token (Settings > Integrations)
3. Store the token as GHL_API_TOKEN environment variable
4. Store the Location ID as GHL_LOCATION_ID environment variable
5. Run setup_ghl.py to create custom fields + pipeline
6. Configure outbound webhooks (Settings > Webhooks):
   - URL: https://{YOUR_SERVER}/api/ghl-webhook
   - Events: ContactCreate, ContactUpdate, OpportunityStatusUpdate,
     NoteCreate, AppointmentCreate, InboundMessage
7. Connect Calendly to GHL (or use GHL's native calendar)
8. Set up email sending domain (SPF, DKIM, DMARC)
9. Configure SMS (Twilio/LC Phone credits)
10. Build the 5 workflow automations from Section 3.5 in the GHL workflow builder

**OpenClaw handles everything else.**

---

## 9. Risk Notes

**Things that could go wrong and how to handle them:**

1. **GHL API rate limits (100 req/10s, 200K/day).** The pipeline pushes leads
   in small batches (max 10-20 per evening cycle). At 113 total leads,
   you're nowhere near limits. This only matters if you scale to 1000+ leads
   or run aggressive sync polling.

2. **GHL custom field IDs change.** GHL uses unique IDs for custom fields,
   not the human-readable names. The setup script captures these IDs and
   writes them to a config file. If someone deletes and recreates a field
   in the GHL UI, the ID changes and the webhook breaks. Mitigation: the
   nightly health check verifies all custom fields exist with expected IDs.

3. **Bidirectional sync conflicts.** If someone updates a contact in GHL
   AND OpenClaw enriches the same contact simultaneously, data can conflict.
   Rule: the lead store is the source of truth for enrichment data (fleet
   size, score, IG metrics). GHL is the source of truth for pipeline stage,
   conversation history, and appointment data. Neither overwrites the other's
   domain.

4. **IG DMs can't be sent from GHL.** GHL handles email, SMS, WhatsApp,
   Facebook DMs -- but not Instagram DMs programmatically. IG outreach stays
   manual. The team reads the approved DM from GHL's custom field (or the
   dashboard's approval queue), then types/pastes it on Instagram. This is
   a workflow limitation of IG's platform, not something to engineer around.

5. **GHL costs.** $97/mo minimum (Starter plan has API access). $297/mo
   for Unlimited (recommended for unlimited sub-accounts and full API).
   SMS/phone credits are additional. At your current volume (under 50
   active contacts), usage costs will be minimal. Budget ~$350/mo all-in
   to start.

6. **LLM costs with Opus 4.6.** Route enrichment/scoring to Sonnet 4.6
   ($3/$15 per million tokens) and reserve Opus for DM drafting and complex
   decisions. Configure model routing in openclaw.json:
   ```json
   "models": {
     "default": "claude-sonnet-4-6",
     "dm_drafting": "claude-opus-4-6",
     "scoring_complex": "claude-opus-4-6"
   }
   ```

7. **Cold email via GHL is against their TOS.** GHL explicitly prohibits
   cold email to scraped/purchased lists. Your email sequences in GHL should
   only target leads who have responded to your IG DM outreach (opted in
   via conversation). For cold outreach, stick to IG DMs and phone calls.

8. **Team sends unapproved message.** The GHL DM draft is stored in a
   custom field, not a pre-loaded SMS template. The team has to manually
   copy it to IG. The approval workflow in the dashboard is the gatekeeper.
   The DO NOT SAY field is visible in both the dashboard AND the GHL
   contact record.
