# Exotiq Pipeline -- V2 Status and What's Next
## Morning Debrief -- April 4, 2026

---

## What We Built (April 3, one session)

### The System
- **122 leads** across 11 markets in SQLite with full provenance
- **React dashboard** live at exotiqdashboard.netlify.app
- **17 leads pushed to GHL** with contacts, opportunities, custom fields, tags
- **16-stage pipeline** in GHL (Exotiq Operator Sales)
- **15 custom fields** in GHL (Lead Score, Fleet Size, IG Handle, DM Draft, etc.)
- **433 activity log entries** backfilled from CRM history
- **$530K total pipeline value** at monthly pricing

### Dashboard Features
- 6 tabs: All Leads, Approval Queue, Call Sheet, Pipeline Funnel, Activity Feed, Export
- 3-column lead cards with contact info, outreach timeline, GHL status
- Clickable IG handles (@handle format linking to Instagram)
- Score badges (gold/teal/blue/gray), GHL sync badges
- Inline DM editor with word count
- Stale lead detection (orange warnings)
- Pipeline funnel with conversion rates and market breakdown
- CSV export with all fields including pricing
- Mobile responsive

### GHL Integration
- Live API connection (token + location ID confirmed)
- Contact creation with all 15 custom fields
- Opportunity creation with correct pipeline stages
- Health check verifying all 17 pushed contacts
- Webhook listener deployed on Netlify (ready for outbound webhooks)

---

## What's Next -- Prioritized TODO

### Priority 1: Daily Enrichment Engine (The Big Unlock)

This is what turns the dashboard from a static CRM into a living pipeline.

**Goal:** Every evening, Saul runs enrichment on unenriched leads automatically.

**Steps:**
- [ ] Get Apollo API key from Gregory (enables company + person lookup)
- [ ] Build scheduled enrichment runner (evening cycle, max 10 leads per run)
- [ ] For each lead: Apollo lookup, web search, IG profile check
- [ ] Auto-score after enrichment (weighted rubric)
- [ ] Auto-draft DMs for newly scored leads (score 3+, V3 templates)
- [ ] New leads land in Approval Queue automatically
- [ ] Activity feed updates in real time

**What this means for Gregory:** Wake up to new scored leads with drafted DMs waiting for approval. Approve, push to GHL, team executes. The pipeline feeds itself.

### Priority 2: Morning Brief

- [ ] Set up Slack bot token for #exotiq-outreach-ops
- [ ] 6:30 AM ET daily post with:
  - Hot leads requiring action
  - New GHL responses overnight
  - Follow-ups due today
  - Stale leads count
  - Pipeline total and health

### Priority 3: Bidirectional GHL Sync

- [ ] Register GHL outbound webhooks (needs Gregory to enable in GHL UI, or test API)
- [ ] When team marks "DM Sent" in GHL, dashboard updates automatically
- [ ] When prospect responds in GHL, Saul gets notified
- [ ] Score 5 response alerts go directly to Gregory

### Priority 4: New Market Discovery

- [ ] Saul discovers new operators in under-explored markets
- [ ] Priority markets needing leads: Chicago (only 1), Las Vegas, Los Angeles
- [ ] Google Maps, IG search, Apollo company search
- [ ] Dedup against existing 122 leads
- [ ] New leads enter as "New" with enrichment pending

### Priority 5: Dashboard Polish

- [ ] Wire approve/reject to actually write to SQLite and re-export JSON
- [ ] Wire "Push to GHL" button on approval queue to live GHL API
- [ ] Add search across enrichment notes/intel
- [ ] Real-time WebSocket updates (kill 30-second polling)
- [ ] Custom domain for dashboard (dashboard.exotiq.ai?)

---

## Ideas Worth Exploring

### 1. Competitive Intel Layer
During enrichment, scrape competitor pricing (Turo listings, website rates) for each operator. Store as enrichment data. Give Gregory ammo on demo calls: "Your competitor down the street is charging $799/day for the Huracan, you could be at $899 with dynamic pricing."

### 2. IG Engagement Scoring
Track post frequency, follower growth rate, engagement quality. Operators with declining IG activity might be struggling (good time to pitch). Operators with growing presence are doing well (different pitch angle).

### 3. Event-Based Outreach Triggers
Calendar of major events per market (Art Basel Miami Dec 4-6, F1 Miami late April, CES Las Vegas Jan). Auto-draft event-specific DMs 2 weeks before each event. "Art Basel is 2 weeks out. How's your fleet positioned?"

### 4. Demo Prep Packets
When a demo is scheduled, auto-generate a one-pager for Gregory:
- Operator profile, fleet size, market position
- Their top 3 likely pain points based on enrichment data
- Competitor comparison in their market
- Suggested pricing tier and ROI framing
- DO NOT SAY reminders
- Reminder to bridge to the demo ask (Gregory's pattern: over-explains instead of closing)

### 5. Lead Scoring V2
Current scoring is mostly manual from the CRM. V2 scoring could weight:
- IG growth trajectory (not just current followers)
- Website quality score (SSL, mobile-friendly, booking system)
- Google review sentiment (not just count)
- Response to outreach (engaged leads score higher)
- Time in market (established operators have more pain points)

### 6. Multi-Channel Outreach Tracking
Track not just IG DMs but also:
- LinkedIn messages (some leads have LinkedIn URLs)
- Email sequences (once GHL email is set up)
- Phone calls (GHL call tracking)
- Unified timeline per lead showing all touchpoints

---

## Testing Plan

### Daily Smoke Test (Saul runs automatically)
1. Dashboard loads at exotiqdashboard.netlify.app
2. leads.json has correct count (currently 122)
3. GHL health check passes (17 contacts verified)
4. No stale leads older than 30 days without action
5. Activity log growing (not static)

### Weekly Review (Gregory)
1. Review approval queue -- approve or reject pending DMs
2. Check Call Sheet for Score 5 leads needing personal outreach
3. Review pipeline funnel for conversion bottlenecks
4. Check for new leads from discovery runs
5. Verify GHL pipeline stages match dashboard

---

## Blockers (Need from Gregory)

1. **Apollo API key** -- unlocks real enrichment (company data, person data, technographics)
2. **Slack bot token** -- enables morning briefs to #exotiq-outreach-ops
3. **GHL outbound webhook setup** -- either via API (I'll try) or manually in GHL UI
4. **Custom domain decision** -- dashboard.exotiq.ai? pipeline.exotiq.ai?

---

## Session Stats (April 3)

- Build time: ~12 hours (10 AM - 10 PM MDT + overnight sprint)
- Files created: 68+
- Lines of code: 10,000+
- Git commits: 20+
- GHL API calls: ~60
- Leads migrated: 122
- Leads pushed to GHL: 17
- Total pipeline value: $530,136/yr
- Tunnels killed by Vite: 1
- Google Chrome profiles accidentally created: 1
- Gregory's sleep schedule: compromised
