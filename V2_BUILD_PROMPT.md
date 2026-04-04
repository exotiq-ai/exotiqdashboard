# V2 Overnight Sprint

You are continuing the Exotiq Lead Intelligence Pipeline build. This is the v2 overnight sprint.

Read SPEC_CONCEPT_B.md for full context. The project has:
- SQLite DB at db/exotiq.db with 122 leads
- React dashboard in src/ (Vite + Tailwind + Recharts)
- GHL integration in ghl/ and skills/
- Dashboard live at exotiqdashboard.netlify.app
- GHL token: pit-6bc107a4-45c3-410c-a35a-97badf293bd7
- GHL Location ID: hTOVcYDLS1UfuiNzuzpT
- GHL config with field IDs and pipeline stage IDs at ghl/ghl_config.json
- Pricing: monthly * 12 (Starter $29/vehicle min $79, Professional $399, Business $899, Enterprise $1799)
- customFields uses ARRAY format: [{"id": "fieldId", "value": "val"}] not object format

DO NOT ASK QUESTIONS. JUST BUILD.

## Task 1: Bulk GHL Push

Push all approved leads (approval_status = APPROVED, ghl_in_ghl = 0) to GHL.
Use the same pattern that worked for RealCar Miami (lead_mia_021):
- POST /contacts/ with customFields as array: [{"id": "XPkBEJ...", "value": "5"}]
- POST /opportunities/ with pipeline/stage IDs from ghl/ghl_config.json
- Score 5 leads go to stage "Gregory -- Personal Outreach"
- Score 3-4 leads go to stage "DM Drafted"
- Tags: exotiq-pipeline, score-{N}, market-slug, fleet-tier, gregory-only (if score 5)
- Dedup check via GET /contacts/search/duplicate before each create
- Update leads table: ghl_contact_id, ghl_opportunity_id, ghl_pipeline_stage, ghl_in_ghl=1, ghl_last_sync, ghl_tags
- Log to activity_log and ghl_sync_log
- Sleep 200ms between API calls for rate limiting
- Actually execute the push against the live GHL API
- Print a summary at the end

## Task 2: Inline DM Editor

In src/components/LeadCard.jsx:
- When "Edit" button is clicked on a DM draft, replace the draft display with a textarea
- Show word count (max 150 words for IG DMs)
- Save and Cancel buttons
- On Save, update local React state (the leads array in useLeadData)
- Style the textarea to match the dark theme

## Task 3: Stale Lead Detection

In skills/dashboard_sync.py:
- Add "stale" boolean and "days_since_activity" to each lead in leads.json
- A lead is stale if its updated_at is older than 7 days
- In the TopBar, show stale count if > 0
- In LeadCard collapsed row, show a subtle orange dot for stale leads

## Task 4: Mobile Polish

Review and fix all components for mobile (375px width):
- FilterBar: make it collapsible (show/hide toggle button)
- TopBar: stats wrap to second line, smaller text
- Tab nav: horizontal scroll with overflow-x-auto (already has this, verify)
- LeadCard expanded: 3 columns collapse to 1 column on mobile (lg:grid-cols-3 already, verify)
- Approval Queue cards: full width on mobile
- Pipeline Funnel chart: reduce height on mobile, smaller labels

## Task 5: GHL Sync Health Check

Create skills/ghl_health_check.py:
- Function: run_health_check()
- GET all contacts with tag "exotiq-pipeline" from GHL
- Compare against leads with ghl_in_ghl=1 in SQLite
- Flag: in store but not GHL, in GHL but not store, missing custom fields
- Log results to activity_log
- Update ghl_sync_status.json with health data
- Actually run it against the live GHL API

## Task 6: Dashboard Improvements

- Add pricing tier badge to LeadCard (small pill showing "Professional $4,788/yr" etc.)
- Improve ActivityFeed with type-specific icons (use lucide-react: Search for discovery, Database for enrichment, Star for scoring, MessageSquare for dm_draft, Send for outreach, ArrowLeftRight for ghl_push)
- Footer: show total pipeline value ($530K/yr)
- Make sure CSV export includes pricing fields

## Task 7: End-to-End Test

After building:
- Verify npm run build with zero errors
- Check a few GHL contacts via API to confirm the bulk push worked
- Verify leads.json has stale flags and pricing data
- Print a full test report

## After ALL tasks:
- Resync dashboard: python3 -c "from skills.dashboard_sync import sync_dashboard; sync_dashboard('public/data')"
- Build: npm run build
- Commit with detailed message
- Push to origin main
