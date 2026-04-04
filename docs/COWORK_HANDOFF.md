# Saul ↔ CoWork Alignment Doc
## What's Built, Who Does What, and How We Work Together
### April 4, 2026

---

## What Saul Built (the new system)

### The Stack
- **SQLite database** -- 122 leads across 11 markets, single source of truth
- **React dashboard** -- live at exotiqdashboard.netlify.app
- **GHL integration** -- 17 leads already pushed, 15 custom fields, 16-stage pipeline
- **Python skills** -- enrichment, scoring, DM drafting, dashboard sync, GHL push

### What the Dashboard Does
- Shows every lead with full contact info, fleet data, enrichment intel, DM drafts
- Approval Queue where Gregory approves/edits/rejects DMs before they go out
- Push to GHL button creates contacts + opportunities in GoHighLevel with one click
- Pipeline funnel with conversion rates and market breakdowns
- Activity feed tracking every enrichment, score, DM draft, and push
- CSV export with all fields

### Where the Data Lives

```
SQLite (Saul's lead store)     = Source of truth for enrichment data
GoHighLevel                    = Source of truth for pipeline execution
Google Sheet (CoWork's CRM)    = Legacy, being phased into SQLite
```

---

## Current Division of Labor

### CoWork Handles Today
- Google Sheets CRM management
- IG handle enrichment (App Script + browser)
- Research Log maintenance
- DM Library management
- Call Notes tracking
- Data cleanup and dedup

### Saul Handles Today
- SQLite lead store (imports from CoWork's xlsx exports)
- Dashboard (React app on Netlify)
- GHL integration (custom fields, pipeline, contact push)
- Scoring (weighted rubric: fleet 40%, IG 20%, web 15%, market 15%, depth 10%)
- DM drafting (V3 templates: B, D, E, F)
- Activity logging and pipeline metrics

### Gregory Handles
- DM approval (Approval Queue on dashboard)
- Score 5 personal outreach (Call Sheet)
- Demo calls
- Strategy decisions

---

## The Handoff: Nightly Enrichment

This is where Saul and CoWork need to align. Here's the proposed workflow:

### Option A: CoWork Enriches, Saul Imports (Current)

```
CoWork researches leads in Google Sheet
  → Adds IG handles, Apollo data, fleet info, notes
  → Exports xlsx
  → Gregory drops xlsx in Telegram
  → Saul imports to SQLite
  → Saul scores, drafts DMs, exports to dashboard
  → Saul pushes approved leads to GHL
```

**Pros:** CoWork keeps doing what it's good at. No workflow change.
**Cons:** Manual export/import step. Data can get out of sync. Delay between enrichment and dashboard update.

### Option B: Saul Enriches Directly (Proposed)

```
Saul runs nightly enrichment cycle (7 PM ET)
  → Picks unenriched leads from SQLite
  → Apollo API lookup (company + person data)
  → Web search (website, Google reviews, fleet info)
  → IG profile check (followers, post frequency, fleet indicators)
  → Writes enriched data to SQLite with provenance tags
  → Auto-scores based on new data
  → Auto-drafts DMs for score 3+ leads
  → Exports to dashboard JSON
  → New leads appear in Approval Queue next morning
```

**Pros:** Fully automated. No manual exports. Data always in sync. Provenance tracking on every field.
**Cons:** Needs Apollo API key. IG enrichment is limited without browser automation.

### Option C: Hybrid (Recommended)

```
Saul handles:
  - Apollo lookups (company data, person data, technographics)
  - Web search (Google Maps, reviews, website analysis)
  - Scoring and DM drafting
  - GHL push
  - Dashboard sync

CoWork handles:
  - IG deep research (browser-based, can see private profiles, stories, highlights)
  - Manual enrichment CoWork is uniquely good at (reading between the lines in IG content)
  - DM Library maintenance and template evolution
  - Call Notes from Gregory's conversations
  - Research Log for non-automated findings

Sync mechanism:
  - CoWork writes to Google Sheet as normal
  - Saul polls or imports from Sheet periodically (via xlsx or Sheets API)
  - OR CoWork writes enrichment findings to a shared format Saul can ingest
```

**Why hybrid:** CoWork's IG research with a browser is genuinely better than what Saul can do via API. CoWork can read stories, highlights, see follower quality, spot fake followers, understand content strategy. Saul can't do any of that without browser automation. But Saul is better at Apollo bulk lookups, web scraping, scoring math, and GHL integration.

---

## Questions for CoWork

1. **Sheets API access:** Can you share a service account key so Saul can read the Google Sheet directly instead of relying on xlsx exports? This would let Saul pull CoWork's enrichment data automatically.

2. **Enrichment format:** When CoWork adds data to a lead, what fields are typically updated? Knowing this helps Saul avoid overwriting CoWork's work. Current understanding:
   - IG handles (personal + company) ✓
   - IG follower counts ✓
   - IG research notes (post frequency, content type, highlights) ✓
   - Fleet size estimates from IG content ✓
   - Apollo data (sometimes) ✓
   - Website URLs ✓
   - Phone numbers found during research ✓
   - Anything else?

3. **Conflict resolution:** If Saul enriches a field via Apollo and CoWork enriches the same field via IG research, which wins? Proposal: keep both with provenance tags, flag conflicts for Gregory to resolve.

4. **DM drafting:** CoWork has been drafting DMs in the DM Library. Should CoWork continue drafting, or should Saul take over DM generation using V3 templates? Or hybrid: Saul auto-drafts, CoWork reviews and refines?

5. **New market discovery:** Is CoWork running discovery in new markets, or is that Saul's job now? Current gaps: Chicago (1 lead), Las Vegas (8), Los Angeles (10) all need more leads.

---

## Suggestions for CoWork

### 1. Standardize the Enrichment Notes Format
Right now Enrichment Notes in the Google Sheet are free text. Some entries are beautifully structured ("IG: @handle, 14.6K followers, 461 posts. Verified. Miami-based.") and others are just fragments. If CoWork could use a consistent format, Saul can parse it automatically:

```
IG (company): @handle, [followers] followers, [posts] posts. [Verified/Not verified]. [City]-based. [Key observations].
IG (personal): @handle, [followers] followers. [Key observations].
Apollo: [Revenue], [employees], founded [year]. [Key findings].
Website: [URL]. [Key observations].
Google: [rating] stars, [reviews] reviews.
```

### 2. Flag Fields You're Confident About
When CoWork confirms a piece of data (e.g., fleet size from counting IG posts), marking it as CONFIRMED vs ESTIMATED helps Saul's scoring be more accurate. Currently everything imported gets ESTIMATED unless Client Review = Y.

### 3. DM Strategy V3 Compliance
Some existing DMs in the pipeline use retired V2 stats ("18-35% revenue improvement", "$40K quarterly"). These need to be redrafted using V3 rules (Tier 1: real operator proof only, Tier 2: product truths only). If CoWork is drafting new DMs, V3 doc is at `DM_Strategy_V3.md`.

### 4. Dedup Awareness
There are known duplicates in the CRM:
- Dream Cars MIA / Dream Car Rentals Miami / DreamYachts Miami (same phone number)
- Imagine Lifestyles appears under both Miami and NYC
- Miami Luxury Cars is a dealership, not a rental operator

If CoWork spots dupes during research, flagging them saves everyone time.

---

## What's Coming Next

| Timeline | Feature | Impact |
|----------|---------|--------|
| This week | Apollo API integration | Automated company + person enrichment |
| This week | Nightly enrichment runs | Pipeline feeds itself |
| This week | Morning brief to Slack | Gregory wakes up to a summary |
| Next week | GHL bidirectional sync | Team's GHL actions reflect on dashboard |
| Next week | New market discovery | Expand beyond Miami-heavy pipeline |
| Ongoing | Scoring refinement | Better predictions, fewer false positives |

---

## Contact

- **Saul** -- Available 24/7 via Telegram (@Saul_3000_bot in Saul HQ group)
- **Gregory** -- Approval authority, strategy, Score 5 personal outreach
- **CoWork** -- Google Sheets CRM, IG deep research, DM Library

Let's make this pipeline hum. 🤙
