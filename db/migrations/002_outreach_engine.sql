-- Outreach Sequence Engine -- Phase 1
-- Adds campaign definitions, enrollments, draft queue, and content templates.

CREATE TABLE IF NOT EXISTS sequences (
  id              TEXT PRIMARY KEY,
  name            TEXT NOT NULL,
  description     TEXT,
  trigger_type    TEXT,              -- 'manual', 'lead_enters_status', 'score_reaches', 'event_proximity'
  trigger_value   TEXT,
  active          INTEGER DEFAULT 1,
  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sequence_steps (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
  sequence_id         TEXT NOT NULL,
  step_order          INTEGER NOT NULL,
  delay_days          INTEGER NOT NULL,
  channel             TEXT NOT NULL,  -- 'ig_dm', 'fb_dm', 'email', 'sms', 'phone'
  template_id         TEXT,
  template_override   TEXT,
  skip_if_responded   INTEGER DEFAULT 1,
  notes               TEXT,
  FOREIGN KEY (sequence_id) REFERENCES sequences(id)
);

CREATE INDEX IF NOT EXISTS idx_sequence_steps_sequence ON sequence_steps(sequence_id, step_order);

CREATE TABLE IF NOT EXISTS lead_sequences (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
  lead_id             TEXT NOT NULL,
  sequence_id         TEXT NOT NULL,
  started_at          TEXT NOT NULL,
  current_step        INTEGER DEFAULT 0,
  status              TEXT DEFAULT 'active',  -- 'active','paused','completed','stopped_responded'
  next_touch_due      TEXT,
  stopped_reason      TEXT,
  updated_at          TEXT NOT NULL,
  FOREIGN KEY (lead_id) REFERENCES leads(id),
  FOREIGN KEY (sequence_id) REFERENCES sequences(id)
);

CREATE INDEX IF NOT EXISTS idx_lead_sequences_lead ON lead_sequences(lead_id);
CREATE INDEX IF NOT EXISTS idx_lead_sequences_due  ON lead_sequences(next_touch_due, status);

CREATE TABLE IF NOT EXISTS outreach_queue (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  lead_id         TEXT NOT NULL,
  sequence_id     TEXT,
  step_id         INTEGER,
  channel         TEXT NOT NULL,
  subject         TEXT,
  content         TEXT NOT NULL,
  status          TEXT DEFAULT 'pending',  -- 'pending','approved','sent','rejected','held','skipped'
  scheduled_for   TEXT,
  approved_by     TEXT,
  approved_at     TEXT,
  sent_at         TEXT,
  created_at      TEXT NOT NULL,
  FOREIGN KEY (lead_id) REFERENCES leads(id)
);

CREATE INDEX IF NOT EXISTS idx_outreach_queue_lead   ON outreach_queue(lead_id);
CREATE INDEX IF NOT EXISTS idx_outreach_queue_status ON outreach_queue(status, scheduled_for);

CREATE TABLE IF NOT EXISTS content_templates (
  id                TEXT PRIMARY KEY,
  name              TEXT NOT NULL,
  channel           TEXT NOT NULL,
  template_type     TEXT,
  subject_template  TEXT,
  body_template     TEXT NOT NULL,
  variables         TEXT,
  proof_tier        TEXT,
  notes             TEXT,
  created_at        TEXT NOT NULL
);
