-- Exotiq Lead Intelligence Pipeline -- SQLite Schema
-- Single source of truth for all pipeline data

-- ============================================================
-- LEADS TABLE
-- Flattened from canonical JSON schema (SPEC_QA_SCHEMA.md)
-- Nested objects use underscore notation: contact.first_name -> contact_first_name
-- ============================================================

CREATE TABLE IF NOT EXISTS leads (
    id                                  TEXT PRIMARY KEY,
    company                             TEXT NOT NULL,

    -- Contact: person
    contact_first_name                  TEXT,
    contact_first_name_source           TEXT,
    contact_first_name_confidence       TEXT,
    contact_last_name                   TEXT,
    contact_last_name_source            TEXT,
    contact_last_name_confidence        TEXT,
    contact_title                       TEXT,
    contact_title_source                TEXT,
    contact_title_confidence            TEXT,
    contact_email                       TEXT,
    contact_email_source                TEXT,
    contact_email_confidence            TEXT,
    contact_phone                       TEXT,
    contact_phone_source                TEXT,
    contact_phone_confidence            TEXT,
    contact_linkedin                    TEXT,
    contact_ig_personal                 TEXT,

    -- Company data
    company_ig_handle                   TEXT,
    company_ig_followers                INTEGER,
    company_ig_followers_source         TEXT,
    company_ig_followers_confidence     TEXT,
    company_website                     TEXT,
    company_address                     TEXT,
    company_google_rating               REAL,
    company_google_rating_source        TEXT,
    company_google_rating_confidence    TEXT,
    company_google_reviews              INTEGER,
    company_google_reviews_source       TEXT,
    company_google_reviews_confidence   TEXT,

    -- Fleet
    fleet_size                          INTEGER,
    fleet_size_source                   TEXT,
    fleet_size_confidence               TEXT,
    fleet_vehicle_types                 TEXT,       -- JSON array stored as string
    fleet_vehicle_types_source          TEXT,

    -- Scoring
    scoring_score                       INTEGER,
    scoring_confidence                  TEXT,
    scoring_rationale                   TEXT,
    scoring_scored_at                   TEXT,       -- ISO 8601 timestamp
    scoring_previous_score              INTEGER,

    -- Outreach
    outreach_status                     TEXT,
    outreach_dm_draft                   TEXT,
    outreach_template_used              TEXT,
    outreach_client_review              TEXT,
    outreach_approval_status            TEXT,
    outreach_do_not_say                 TEXT,       -- JSON array stored as string
    outreach_dm1_sent                   TEXT,       -- ISO 8601 timestamp
    outreach_dm2_sent                   TEXT,       -- ISO 8601 timestamp
    outreach_dm3_sent                   TEXT,       -- ISO 8601 timestamp
    outreach_response_received          BOOLEAN,
    outreach_response_category          TEXT,
    outreach_response_date              TEXT,       -- ISO 8601 timestamp
    outreach_calendly_sent              TEXT,       -- ISO 8601 timestamp
    outreach_demo_scheduled             BOOLEAN,

    -- GHL (system-managed, no provenance columns)
    ghl_contact_id                      TEXT,
    ghl_opportunity_id                  TEXT,
    ghl_pipeline_stage                  TEXT,
    ghl_last_sync                       TEXT,       -- ISO 8601 timestamp
    ghl_in_ghl                          BOOLEAN DEFAULT 0,
    ghl_tags                            TEXT,       -- JSON array stored as string

    -- Top-level fields
    market                              TEXT,
    lead_source                         TEXT,
    enrichment_history                  TEXT,       -- JSON array stored as string
    notes                               TEXT,
    created_at                          TEXT NOT NULL,  -- ISO 8601 timestamp
    updated_at                          TEXT NOT NULL   -- ISO 8601 timestamp
);

CREATE INDEX IF NOT EXISTS idx_leads_market ON leads (market);
CREATE INDEX IF NOT EXISTS idx_leads_scoring_score ON leads (scoring_score);
CREATE INDEX IF NOT EXISTS idx_leads_outreach_status ON leads (outreach_status);
CREATE INDEX IF NOT EXISTS idx_leads_ghl_in_ghl ON leads (ghl_in_ghl);
CREATE INDEX IF NOT EXISTS idx_leads_company_ig_handle ON leads (company_ig_handle);

-- ============================================================
-- ACTIVITY LOG
-- Every agent action, enrichment event, sync, and workflow step
-- ============================================================

CREATE TABLE IF NOT EXISTS activity_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT NOT NULL,      -- ISO 8601
    type        TEXT NOT NULL,      -- e.g. "enrichment", "scoring", "dm_draft", "ghl_push"
    lead_id     TEXT,               -- NULL for system-level events
    description TEXT NOT NULL,
    source      TEXT,               -- e.g. "apollo", "ig_profile", "manual"
    agent       TEXT                -- e.g. "lead_enrichment", "lead_scoring"
);

CREATE INDEX IF NOT EXISTS idx_activity_log_lead_id ON activity_log (lead_id);
CREATE INDEX IF NOT EXISTS idx_activity_log_timestamp ON activity_log (timestamp);
CREATE INDEX IF NOT EXISTS idx_activity_log_type ON activity_log (type);

-- ============================================================
-- DM DRAFTS
-- All generated DM drafts and their approval state
-- ============================================================

CREATE TABLE IF NOT EXISTS dm_drafts (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id                 TEXT NOT NULL,
    template_used           TEXT,               -- A, B, D, E, F
    dm_text                 TEXT NOT NULL,
    personalization_notes   TEXT,
    do_not_say              TEXT,               -- JSON array
    client_review           TEXT DEFAULT 'Y',
    approval_status         TEXT DEFAULT 'PENDING',  -- PENDING, APPROVED, REJECTED
    approved_by             TEXT,
    approved_at             TEXT,               -- ISO 8601
    created_at              TEXT NOT NULL       -- ISO 8601
);

CREATE INDEX IF NOT EXISTS idx_dm_drafts_lead_id ON dm_drafts (lead_id);
CREATE INDEX IF NOT EXISTS idx_dm_drafts_approval_status ON dm_drafts (approval_status);

-- ============================================================
-- GHL SYNC LOG
-- Full audit trail of every GHL API call, inbound and outbound
-- ============================================================

CREATE TABLE IF NOT EXISTS ghl_sync_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT NOT NULL,      -- ISO 8601
    direction       TEXT NOT NULL,      -- "outbound" or "inbound"
    lead_id         TEXT,
    ghl_contact_id  TEXT,
    endpoint        TEXT,               -- e.g. "POST /contacts/"
    http_status     INTEGER,
    payload_summary TEXT,               -- truncated JSON description
    error_message   TEXT
);

CREATE INDEX IF NOT EXISTS idx_ghl_sync_log_lead_id ON ghl_sync_log (lead_id);
CREATE INDEX IF NOT EXISTS idx_ghl_sync_log_timestamp ON ghl_sync_log (timestamp);
