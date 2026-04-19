# Phase 1 Build -- Outreach Sequence Engine

## Goal
Give Saul the ability to orchestrate multi-channel sequences across IG, Facebook Messenger, Email, SMS, and Phone. Approve everything in the existing dashboard before it sends.

## Data Model Additions

### New Table: sequences
Campaign definitions. A sequence is a template that can be run against any lead.

```sql
CREATE TABLE sequences (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,                     -- "New Operator 14-Day", "F1 Miami Event", "Score-5 Personal"
  description TEXT,
  trigger_type TEXT,                      -- 'manual', 'lead_enters_status', 'score_reaches', 'event_proximity'
  trigger_value TEXT,                     -- e.g. "score>=3", "status=New"
  active BOOLEAN DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

### New Table: sequence_steps
Ordered steps within a sequence.

```sql
CREATE TABLE sequence_steps (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  sequence_id TEXT NOT NULL,
  step_order INTEGER NOT NULL,
  delay_days INTEGER NOT NULL,            -- days after sequence start
  channel TEXT NOT NULL,                  -- 'ig_dm', 'fb_dm', 'email', 'sms', 'phone'
  template_id TEXT,                       -- reference to DM/email template
  template_override TEXT,                 -- inline content if not using template
  skip_if_responded BOOLEAN DEFAULT 1,    -- skip subsequent steps if lead responded
  FOREIGN KEY (sequence_id) REFERENCES sequences(id)
);
```

### New Table: lead_sequences
Tracks which leads are in which sequences.

```sql
CREATE TABLE lead_sequences (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  lead_id TEXT NOT NULL,
  sequence_id TEXT NOT NULL,
  started_at TEXT NOT NULL,
  current_step INTEGER DEFAULT 0,
  status TEXT DEFAULT 'active',           -- 'active', 'paused', 'completed', 'stopped_responded'
  next_touch_due TEXT,                    -- ISO timestamp
  stopped_reason TEXT,
  FOREIGN KEY (lead_id) REFERENCES leads(id),
  FOREIGN KEY (sequence_id) REFERENCES sequences(id)
);
```

### New Table: outreach_queue
Drafted outbound touches awaiting approval.

```sql
CREATE TABLE outreach_queue (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  lead_id TEXT NOT NULL,
  sequence_id TEXT,
  step_id INTEGER,
  channel TEXT NOT NULL,                  -- 'ig_dm', 'fb_dm', 'email', 'sms'
  subject TEXT,                           -- for email
  content TEXT NOT NULL,
  status TEXT DEFAULT 'pending',          -- 'pending', 'approved', 'sent', 'rejected', 'held'
  scheduled_for TEXT,
  approved_by TEXT,
  approved_at TEXT,
  sent_at TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (lead_id) REFERENCES leads(id)
);
```

### New Table: content_templates
Reusable content blocks Saul can stitch together.

```sql
CREATE TABLE content_templates (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  channel TEXT NOT NULL,                  -- 'ig_dm', 'fb_dm', 'email', 'sms'
  template_type TEXT,                     -- 'opener', 'follow_up_1', 'follow_up_2', 'proof', 'close'
  subject_template TEXT,                  -- for email
  body_template TEXT NOT NULL,
  variables TEXT,                         -- JSON list of expected vars: ["first_name", "fleet_size", "recent_car"]
  proof_tier TEXT,                        -- 'tier1', 'tier2' (V3 compliance)
  notes TEXT,
  created_at TEXT NOT NULL
);
```

## Dashboard Changes

### New Tab: Sequences
Between "Pipeline Funnel" and "Activity Feed."

Views:
- **Campaigns:** List of all sequences. Create new, edit, pause, delete.
- **Active Leads:** Which leads are currently in which sequences. Filter by status.
- **Queue Preview:** Upcoming scheduled touches.

### Expanded Approval Queue
Current tab shows only initial DM drafts. Expanded version shows all outbound across channels.
- Channel tabs: All / IG / FB / Email / SMS
- Each item shows: lead, channel, scheduled send time, content preview
- Approve / Edit / Hold / Skip (skip = advance sequence without sending this step)

### Lead Card: Sequence Panel
On each lead's expanded card, add a "Sequences" section showing:
- Current active sequence(s)
- Last touch date and channel
- Next touch scheduled
- Full history of all sends for this lead

## Phase 1 Deliverables

1. SQL migration for 5 new tables
2. React UI for Sequences tab (list + create + edit)
3. Expanded Approval Queue with channel filtering
4. Python skill: sequence_engine.py that processes due touches
5. Seed data: 3 starter sequences
   - "New Operator 14-Day" (5 touches)
   - "Warm Response 7-Day" (3 touches)
   - "F1 Miami Event" (time-boxed, event-specific)

## Out of Scope for Phase 1
- Actual sending (phase 3)
- Reply classification (phase 2)
- Resend integration (phase 3)
- Voice AI (phase 4)

## Open Questions for Gregory
1. Approve individually vs approve-all-in-sequence? Recommend: approve the sequence template once, then individual touches auto-approve unless flagged for review.
2. Time-of-day windows? Don't send DMs at 3am local. Recommend: 9am-6pm local time for each lead's market.
3. Quiet days? Recommend: no cold touches on weekends for first contact.
