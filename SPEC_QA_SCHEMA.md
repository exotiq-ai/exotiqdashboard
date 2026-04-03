# OpenClaw Q&A -- Concept B Build
## Answers + Canonical Schema Reference
### April 2026

---

## OpenClaw Questions + Answers

### Data / Migration

**Q1: The spec references Miami_Operators_Clean_2.xlsx for migration. Do you have that file ready to drop in, or should I build the schema and migration script to accept it later?**

Gregory will send the file directly. Build the migration script expecting it at the workspace root. The file has 12 tabs, all sharing the same 36-column schema. Tab names: Export Summary, Miami Operators, Daily Activity Log, Lead Source Tracker, Phoenix Scottsdale, Dallas Fort Worth, Atlanta, NYC, Las Vegas, Los Angeles, SF Bay Area, DC DMV. Skip the Export Summary tab (it's a Numbers export artifact with no data). The Daily Activity Log and Lead Source Tracker tabs are structural -- import them as metadata, not leads. All other tabs contain lead rows.

Lead counts by tab:
- Miami Operators: 38 leads (200 total rows, many empty)
- Phoenix Scottsdale: 16 leads
- Dallas Fort Worth: 10 leads
- Atlanta: ~8 leads
- NYC: ~8 leads
- Las Vegas: ~8 leads
- Los Angeles: ~10 leads
- SF Bay Area: ~7 leads
- DC DMV: ~8 leads

Watch out for: empty rows (skip them), the "Company Email" column sometimes contains phone numbers (check format -- if it starts with +1 or is all digits, map to contact.phone), and the Enrichment Notes column is free text that sometimes contains structured intel worth parsing.

---

**Q2: The lead store schema mentions "all fields from the lead JSON schema" but I don't see a Concept A lead schema in this doc.**

Fixed. The canonical schema is now embedded in the Concept B spec (Section 7, Part 1). It's also included at the end of this document as a standalone reference. Use it as the single source of truth. Don't derive -- it's defined.

---

### GHL

**Q3: Do you have the GHL sub-account set up yet? Specifically: do you have GHL_API_TOKEN and GHL_LOCATION_ID ready?**

Yes. GHL has full API access.

- **Private Integration Token:** `Pit-552a2cee-fe18-4e7a-9c5f-597596a8dfb7`
- **Sub-account:** "Exotiq" is set up in GHL
- **Location ID:** Pull this from the GHL API using the token. Hit `GET https://services.leadconnectorhq.com/locations/search` with the auth header to retrieve the Exotiq sub-account's locationId. Store it as GHL_LOCATION_ID.
- **Webhooks:** Not configured yet. You (OpenClaw) will set up GHL outbound webhooks via the API or walk Gregory through the UI setup. See Q5 for the listener endpoint.

**Action for OpenClaw:** Use the token to query the Locations API, confirm the Exotiq sub-account exists, extract the locationId, and store both values in your workspace config. Then use the Custom Fields V2 API to create the 15 custom fields from the spec, and the Opportunities API to create the "Exotiq Operator Sales" pipeline with all stages. Run setup_ghl.py as the first GHL action.

---

**Q4: The spec mentions Slack notifications in several places (#exotiq-outreach-ops, C0AM9DRETRS). Are we routing those through Slack, or should I adapt to Telegram?**

Keep Slack. The existing CoWork setup runs through a Slack MCP integration. The confirmed workspace is **exotiq-ai**, channel **#exotiq-outreach-ops** (ID: C0AM9DRETRS). All pipeline notifications, morning briefs, alerts, and GHL sync summaries go there.

For how you connect to Slack: use whatever method is available in your environment. If you have Slack MCP access, use it. If you need to fall back to the Slack Web API (chat.postMessage), that works too -- just needs a bot token with chat:write scope for the #exotiq-outreach-ops channel. Gregory can generate that from the exotiq-ai Slack workspace admin if needed. Let him know what you need.

---

**Q5: For the ghl-listener webhook receiver, where is this running? The GHL outbound webhooks need a reachable endpoint.**

The listener needs a publicly reachable URL. GHL sends HTTP POST requests to it when events fire (contact updates, stage changes, inbound messages, etc.). It can't run inside GHL -- GHL is the sender, not the host.

**Recommended approach: Netlify Functions.**

Gregory already deploys to Netlify and has a git-to-Netlify auto-deploy workflow. Netlify Functions are serverless endpoints that deploy alongside the dashboard. No VPS needed. No Docker. No new infrastructure.

Setup:
1. Create a `/netlify/functions/ghl-webhook.js` file in the dashboard repo
2. This function receives GHL POST requests, verifies the X-GHL-Signature header, parses the payload, and writes to a shared data store (or queues the event for OpenClaw to process)
3. The public URL will be: `https://{your-netlify-site}.netlify.app/.netlify/functions/ghl-webhook`
4. Register that URL in GHL's outbound webhook settings for the events listed in the spec (ContactCreate, ContactUpdate, OpportunityStatusUpdate, NoteCreate, AppointmentCreate, InboundMessage)

**Alternatively:** If you want the listener running locally during dev, use Cloudflare Tunnel (`cloudflared tunnel`) to expose a local Flask/Express server to a public URL. This is faster for testing but not production-grade.

**For production:** Netlify Functions is the move. It auto-deploys with the dashboard repo, scales to zero when idle, and costs nothing at your volume.

**Action for OpenClaw:** Build the ghl-listener as a Netlify Function (Node.js). Include signature verification, event routing, and a `/health` endpoint for testing. When Gregory pushes to git, Netlify deploys it automatically. Then configure the GHL outbound webhooks via the API using the Netlify URL.

---

### Dashboard

**Q6: The spec calls for Geist Mono and Geist Sans fonts. Should I pull those from Google Fonts / Vercel's CDN?**

Don't use Geist. Pick highly readable, modern fonts that look sharp in a dark-mode data dashboard. Your call -- just make sure data (numbers, scores, timestamps, IDs) is in a monospaced font and UI elements (labels, buttons, headings) are in a clean sans-serif. Prioritize legibility at small sizes since lead cards pack a lot of info.

Some directions worth considering: JetBrains Mono for data, General Sans or Satoshi for UI. But you're the designer here -- pick what looks best and commit to it.

---

**Q7: Where do you want the dashboard served?**

Local dev server during build. Production goes to Netlify.

Workflow:
1. Build the dashboard locally, serve with `npx serve` or Vite dev server
2. When it's working, push to a git repo
3. Netlify auto-deploys from the repo on every push
4. The ghl-listener Netlify Function lives in the same repo (under `/netlify/functions/`)

This means the dashboard and the webhook listener deploy together as one unit. Clean.

**Git repo structure suggestion:**
```
exotiq-dashboard/
├── src/
│   └── dashboard.jsx          (or broken into components)
├── public/
│   └── data/                  (JSON files from dashboard-sync)
│       ├── leads.json
│       ├── activity.json
│       ├── stats.json
│       ├── ghl_sync_status.json
│       └── pipeline_metrics.json
├── netlify/
│   └── functions/
│       └── ghl-webhook.js     (GHL inbound webhook listener)
├── package.json
├── netlify.toml
└── README.md
```

**Note:** The `/public/data/` JSON files are written by OpenClaw's dashboard-sync skill. For local dev, OpenClaw writes them directly. For production on Netlify, you'll need OpenClaw to push updated JSON files to the git repo (triggering a redeploy) OR use a lightweight external data store (like a Supabase table or even a Netlify Blob) that the dashboard fetches from at runtime. The simplest v1: OpenClaw commits updated JSON to the repo and Netlify redeploys. The polling interval becomes "however fast Netlify builds" (~30-60 seconds), which is fine for now.

---

### Scope

**Q8: Recommended build order -- Phase 1 through 4. Sound right?**

The order is correct. All four phases ship in one session. This is execution order, not a multi-day plan:

1. **Data layer first:** SQLite schema + migration script + OpenClaw config files (SOUL.md, USER.md, HEARTBEAT.md, AGENTS.md). This gives you a working foundation everything else builds on.

2. **Core skills second:** Discovery, enrichment, scoring, DM drafting, dashboard-sync. These are the intelligence engine. Test them against the migrated data.

3. **GHL integration third:** setup_ghl.py (create custom fields + pipeline), ghl-push, ghl-listener (Netlify Function). Wire the bridge. Test with one lead.

4. **Dashboard last:** React app with all tabs, filters, GHL status badges, pipeline funnel. It reads from the JSON files the skills already export, so it works immediately once the data layer and skills are running.

Build it all. Ship it all. One session.

---

## Canonical Lead JSON Schema (Standalone Reference)

This is the single source of truth for all lead data in the Exotiq pipeline.
The SQLite `leads` table flattens nested objects using underscore notation
(e.g., `contact.first_name` → column `contact_first_name`).

```json
{
  "id": "lead_001",
  "company": "Prestige Luxury Rentals",

  "contact": {
    "first_name": "Xavier",
    "last_name": "Guerrero",
    "title": "Business Owner",
    "email": "xavier@prestigeluxuryrentals.com",
    "phone": "+17862024892",
    "linkedin": "https://linkedin.com/in/xavierguerrero",
    "ig_personal": "@xavier.g"
  },

  "company_data": {
    "ig_handle": "@prestigeluxuryrentals",
    "ig_followers": 45000,
    "website": "prestigeluxuryrentals.com",
    "address": "4019 NW 25th Street, Miami",
    "google_rating": 4.7,
    "google_reviews": 312
  },

  "fleet": {
    "size": 43,
    "size_confidence": "ESTIMATED",
    "size_source": "ig_profile",
    "vehicle_types": ["Lamborghini", "Ferrari", "Rolls-Royce", "McLaren"],
    "vehicle_source": "ig_profile"
  },

  "scoring": {
    "score": 5,
    "confidence": "HIGH",
    "rationale": "43+ fleet, strong web/IG presence, multi-location",
    "scored_at": "2026-03-17T21:00:00Z",
    "previous_score": null
  },

  "outreach": {
    "status": "Pending Approval",
    "dm_draft": "Hey, Gregory Ringler here, founder of Exotiq AI...",
    "template_used": "B",
    "client_review": "Y",
    "approval_status": "PENDING",
    "do_not_say": [],
    "dm1_sent": null,
    "dm2_sent": null,
    "dm3_sent": null,
    "response_received": null,
    "response_category": null,
    "response_date": null,
    "calendly_sent": null,
    "demo_scheduled": null
  },

  "ghl": {
    "contact_id": null,
    "opportunity_id": null,
    "pipeline_stage": null,
    "last_ghl_sync": null,
    "in_ghl": false,
    "ghl_tags": []
  },

  "market": "Miami",
  "lead_source": "Apollo + IG Research",

  "enrichment_history": [
    {
      "action": "apollo_lookup",
      "timestamp": "2026-03-16T21:00:00Z",
      "fields_updated": ["contact.first_name", "contact.last_name", "contact.title"],
      "source": "apollo"
    },
    {
      "action": "ig_research",
      "timestamp": "2026-03-16T21:45:00Z",
      "fields_updated": ["fleet.size", "company_data.ig_followers"],
      "source": "ig_profile"
    }
  ],

  "notes": "Gregory's Score 5. Call, don't DM.",
  "created_at": "2026-03-16T20:30:00Z",
  "updated_at": "2026-03-17T21:00:00Z"
}
```

### Field Provenance Convention

Every data field in the leads table that comes from enrichment gets two companion columns:

- `{field}_source`: Where the data came from. Valid values: `apollo`, `ig_profile`, `website`, `google_search`, `manual`, `gregory_input`, `ghl_sync`
- `{field}_confidence`: How reliable the data is. Valid values: `CONFIRMED`, `ESTIMATED`, `INFERRED`

Example: `fleet_size` = 43, `fleet_size_source` = "ig_profile", `fleet_size_confidence` = "ESTIMATED"

Not every field needs provenance columns. Apply them to fields that are researched or inferred:
- fleet.size, fleet.vehicle_types
- company_data.ig_followers, company_data.google_rating, company_data.google_reviews
- contact.first_name, contact.last_name, contact.title, contact.email, contact.phone
- scoring.score, scoring.confidence

Do NOT add provenance columns to: id, market, lead_source, created_at, updated_at, notes, or any ghl.* fields (those are system-managed).

### SQLite Column List (Flattened)

For quick reference, here's every column in the `leads` table:

```
id                          TEXT PRIMARY KEY
company                     TEXT NOT NULL
contact_first_name          TEXT
contact_first_name_source   TEXT
contact_first_name_confidence TEXT
contact_last_name           TEXT
contact_last_name_source    TEXT
contact_last_name_confidence TEXT
contact_title               TEXT
contact_title_source        TEXT
contact_title_confidence    TEXT
contact_email               TEXT
contact_email_source        TEXT
contact_email_confidence    TEXT
contact_phone               TEXT
contact_phone_source        TEXT
contact_phone_confidence    TEXT
contact_linkedin            TEXT
contact_ig_personal         TEXT
company_ig_handle           TEXT
company_ig_followers        INTEGER
company_ig_followers_source TEXT
company_ig_followers_confidence TEXT
company_website             TEXT
company_address             TEXT
company_google_rating       REAL
company_google_rating_source TEXT
company_google_rating_confidence TEXT
company_google_reviews      INTEGER
company_google_reviews_source TEXT
company_google_reviews_confidence TEXT
fleet_size                  INTEGER
fleet_size_source           TEXT
fleet_size_confidence       TEXT
fleet_vehicle_types         TEXT  -- JSON array stored as string
fleet_vehicle_types_source  TEXT
scoring_score               INTEGER
scoring_confidence          TEXT
scoring_rationale           TEXT
scoring_scored_at           TEXT  -- ISO 8601 timestamp
scoring_previous_score      INTEGER
outreach_status             TEXT
outreach_dm_draft           TEXT
outreach_template_used      TEXT
outreach_client_review      TEXT
outreach_approval_status    TEXT
outreach_do_not_say         TEXT  -- JSON array stored as string
outreach_dm1_sent           TEXT  -- ISO 8601 timestamp
outreach_dm2_sent           TEXT
outreach_dm3_sent           TEXT
outreach_response_received  BOOLEAN
outreach_response_category  TEXT
outreach_response_date      TEXT
outreach_calendly_sent      TEXT
outreach_demo_scheduled     BOOLEAN
ghl_contact_id              TEXT
ghl_opportunity_id          TEXT
ghl_pipeline_stage          TEXT
ghl_last_sync               TEXT  -- ISO 8601 timestamp
ghl_in_ghl                  BOOLEAN DEFAULT 0
ghl_tags                    TEXT  -- JSON array stored as string
market                      TEXT
lead_source                 TEXT
enrichment_history          TEXT  -- JSON array stored as string
notes                       TEXT
created_at                  TEXT  -- ISO 8601 timestamp
updated_at                  TEXT  -- ISO 8601 timestamp
```

### xlsx Column Mapping (Migration Reference)

| xlsx Column              | SQLite Column                      | Notes                        |
|--------------------------|------------------------------------|------------------------------|
| Company                  | company                            |                              |
| First Name               | contact_first_name                 |                              |
| Last Name                | contact_last_name                  |                              |
| Title                    | contact_title                      |                              |
| Email                    | contact_email                      |                              |
| Company Email            | contact_phone                      | Check format -- often phone  |
| LinkedIn URL (personal)  | contact_linkedin                   |                              |
| IG Handle (personal)     | contact_ig_personal                |                              |
| IG Handle (company)      | company_ig_handle                  |                              |
| City + State             | market                             | Combine into market name     |
| Fleet Size               | fleet_size                         |                              |
| Lead Score               | scoring_score                      |                              |
| Enrichment Notes         | notes + enrichment_history         | Parse for structured data    |
| Recent Car Post          | fleet_vehicle_types                | Parse car names into array   |
| Status                   | outreach_status                    |                              |
| Draft DM                 | outreach_dm_draft                  |                              |
| Approved DM              | outreach_dm_draft                  | Set approval_status=APPROVED |
| DM1 Sent Date            | outreach_dm1_sent                  |                              |
| DM2 Sent Date            | outreach_dm2_sent                  |                              |
| DM2 Copy                 | (append to enrichment_history)     |                              |
| DM3 Sent Date            | outreach_dm3_sent                  |                              |
| DM3 Copy                 | (append to enrichment_history)     |                              |
| Response Received         | outreach_response_received         |                              |
| Response Category         | outreach_response_category         |                              |
| Response Date            | outreach_response_date             |                              |
| Calendly Sent            | outreach_calendly_sent             |                              |
| Demo Scheduled           | outreach_demo_scheduled            |                              |
| Lead Source              | lead_source                        |                              |
| Notes                    | notes                              |                              |
| Client Review (Y/N)      | outreach_client_review             |                              |
| Client Notes             | notes (append)                     | Preserve Gregory's notes     |
| Outreach Sent            | (derive from outreach_dm1_sent)    |                              |
| Market                   | market                             |                              |
| Outreach Type            | (skip -- metadata only)            |                              |

All migrated rows get:
- `*_source` = "manual" for all provenance fields
- `*_confidence` = "CONFIRMED" if the lead has been reviewed by Gregory (Client Review = Y), otherwise "ESTIMATED"
- All `ghl_*` fields initialized to null/false/empty
- `created_at` = migration timestamp
- `updated_at` = migration timestamp
- `enrichment_history` = empty array (no prior enrichment events recorded)
