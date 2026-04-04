# Exotiq Pipeline -- Data Flow

## The Simple Version

```
                    ┌─────────────┐
                    │  DISCOVERY   │
                    │  Google, IG, │
                    │  Apollo      │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   SQLITE    │  ← Single source of truth
                    │   Lead DB   │    Everything writes here first
                    └──┬──────┬───┘
                       │      │
              ┌────────▼┐  ┌──▼──────────┐
              │ JSON     │  │ GHL Push    │
              │ Export   │  │ (one-way)   │
              └────┬─────┘  └──────┬──────┘
                   │               │
            ┌──────▼──────┐  ┌─────▼──────────┐
            │  DASHBOARD  │  │  GOHIGHLEVEL   │
            │  (read-only │  │  (execution)   │
            │   view)     │  │                │
            └─────────────┘  └────────┬───────┘
                                      │
                              ┌───────▼───────┐
                              │ GHL Webhooks  │
                              │ (events back) │
                              └───────┬───────┘
                                      │
                              ┌───────▼───────┐
                              │   SQLITE      │  ← Circle completes
                              │   (updated)   │
                              └───────────────┘
```

## Enrichment Night Run -- Step by Step

Here's exactly what happens when Saul runs enrichment:

```
Step 1: Saul picks unenriched leads from SQLite
        ┌──────────┐
        │ SQLite   │──→ "Alpha Exotic has no phone, no email, 
        │ Lead DB  │     no fleet size. Let me fix that."
        └──────────┘

Step 2: Saul researches (Apollo, IG, web, Google Maps)
        ┌──────────┐
        │ Apollo   │──→ Found: jaime@alphaexoticsrental.com
        │ IG API   │──→ Found: 14.6K followers, active posts
        │ Google   │──→ Found: 4.2 stars, 47 reviews
        │ Web      │──→ Found: ~12 vehicles from website
        └──────────┘

Step 3: Saul writes ENRICHED data to SQLite (with provenance)
        ┌──────────────────────────────────────────────┐
        │ UPDATE leads SET                             │
        │   contact_email = 'jaime@alphaexotics...'    │
        │   contact_email_source = 'apollo'            │
        │   contact_email_confidence = 'CONFIRMED'     │
        │   fleet_size = 12                            │
        │   fleet_size_source = 'website'              │
        │   fleet_size_confidence = 'ESTIMATED'        │
        │   company_google_rating = 4.2                │
        │   ...                                        │
        │ WHERE id = 'lead_mia_046'                    │
        └──────────────────────────────────────────────┘

Step 4: Saul re-scores based on new data
        Score jumps from 5 (estimated) to 5 (confirmed)
        Fleet size: 12 → Professional tier → $4,788/yr

Step 5: Saul drafts a DM (if score >= 3 and no draft exists)
        Template B (Score 5) with personalized details
        approval_status = PENDING

Step 6: Saul runs dashboard_sync
        SQLite → JSON files → Dashboard updates on next poll (30s)

Step 7: Dashboard shows the enriched lead
        ✓ Email now visible (click to copy)
        ✓ Phone now visible
        ✓ Fleet size: 12 vehicles [ESTIMATED, website]
        ✓ Google: ★ 4.2 (47 reviews)
        ✓ New DM draft in Approval Queue
        ✓ "Push to GHL" button now active (has email!)
```

## What Happens When Gregory Approves + Pushes

```
Step 1: Gregory clicks "Approve" on the dashboard
        → approval_status = APPROVED (local + Netlify Function queue)

Step 2: Gregory clicks "Push to GHL"
        → Dashboard calls Netlify Function (push-to-ghl.js)
        → Function calls GHL API:
          - POST /contacts/ (creates contact with all custom fields)
          - POST /opportunities/ (creates pipeline opportunity)
        → Dashboard shows success alert

Step 3: Lead appears in GHL
        ┌─────────────────────────────────────────┐
        │ GHL Contact: Jaime Andres Lopez          │
        │ Company: Alpha Exotic Rentals            │
        │ Email: jaime@alphaexoticsrental.com      │
        │ Phone: (from enrichment)                 │
        │ Stage: Gregory -- Personal Outreach      │
        │ Value: $4,788/yr                         │
        │ Tags: exotiq-pipeline, score-5, miami,   │
        │       gregory-only                       │
        │ Custom Fields:                           │
        │   Lead Score: 5                          │
        │   Fleet Size: 12                         │
        │   IG Handle: @alphaexoticsrental         │
        │   DM Draft: [full approved copy]         │
        │   OpenClaw Lead ID: lead_mia_046         │
        └─────────────────────────────────────────┘
```

## What Does NOT Happen (By Design)

```
✗ Dashboard does NOT write directly to SQLite
  (it reads JSON files exported by Saul)

✗ GHL push does NOT overwrite existing GHL contacts
  (dedup check: if contact_id exists, push is blocked)

✗ Enrichment does NOT overwrite Gregory's manual notes
  (notes field is append-only, not replaced)

✗ GHL does NOT push data back to SQLite automatically (yet)
  (bidirectional sync is Phase 3 -- coming soon via webhooks)

✗ Nothing touches the Google Sheet CRM directly
  (CoWork manages that separately, xlsx exports are the bridge)
```

## The Three Data Stores (and who owns what)

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  SQLite (lead store)         ← SOURCE OF TRUTH              │
│  Owner: Saul                                                │
│  Contains: Everything. All lead data, enrichment,           │
│  scores, DM drafts, GHL IDs, activity log.                  │
│  Writes: Saul (enrichment, scoring, DM drafting)            │
│  Reads: Dashboard (via JSON export), GHL push               │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  GoHighLevel                 ← EXECUTION LAYER              │
│  Owner: LEx Team                                            │
│  Contains: Contacts, pipeline stages, conversations,        │
│  appointments, email/SMS sequences.                         │
│  Writes: GHL push (from dashboard), team (manually),        │
│          GHL automations                                    │
│  Reads: Team (daily work), Gregory (pipeline view)          │
│                                                             │
│  GHL is DOWNSTREAM of SQLite. The lead store is always      │
│  the authority for enrichment data. GHL is the authority    │
│  for pipeline stage, conversations, and appointments.       │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Google Sheet (CoWork CRM)   ← LEGACY / BRIDGE              │
│  Owner: CoWork                                              │
│  Contains: Original lead data, DM history                   │
│  Status: Being phased out. New enrichment goes              │
│  directly to SQLite. xlsx exports are the bridge            │
│  for bulk imports.                                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Future: Bidirectional GHL Sync

When GHL outbound webhooks are connected:

```
Team moves lead to "DM Sent" in GHL
        │
        ▼
GHL fires webhook → Netlify Function catches it
        │
        ▼
Event queued → Saul processes → SQLite updated
        │
        ▼
Dashboard shows "DM Sent" status automatically

Same for: responses, appointments, stage changes, notes
```

This closes the loop. Right now it's one-way (SQLite → GHL).
Soon it'll be two-way (SQLite ↔ GHL).

## Summary: Enrichment → Dashboard → GHL

```
Night: Saul enriches leads
  └→ SQLite updated with new data + provenance tags
  └→ JSON exported for dashboard
  └→ Leads auto-scored, DMs auto-drafted

Morning: Gregory reviews dashboard
  └→ Approves/edits DMs in Approval Queue
  └→ Pushes approved leads to GHL (one click)
  └→ Score 5 leads flagged for personal outreach

Day: Team works in GHL
  └→ Sends DMs on Instagram (copy from GHL custom field)
  └→ Logs responses, moves pipeline stages
  └→ Books demos, manages conversations

Evening: Saul runs health check
  └→ Verifies SQLite and GHL are in sync
  └→ Flags mismatches, stale leads
  └→ Runs next batch of enrichment
  └→ Cycle repeats
```
