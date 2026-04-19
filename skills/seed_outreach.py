"""
Seed the outreach engine with initial sequences and content templates.
Idempotent: safe to run multiple times.
"""

import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "db" / "exotiq.db"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


TEMPLATES = [
    # -- V3 DM templates
    {
        "id": "tpl_ig_dm_peer_d",
        "name": "IG DM -- Template D (Peer)",
        "channel": "ig_dm",
        "template_type": "opener",
        "body_template": """Hey {first_name}, Gregory here. I run Exotiq. Started in exotics before building the tech.

Curious how you're handling pricing and fleet logistics at {company}. That's where most operators tell us they're leaving money on the table.

Connecting with operators this month. Happy to share what we're learning from the ones already on the platform. No sales pitch.""",
        "proof_tier": "tier2",
        "variables": '["first_name","company"]',
    },
    {
        "id": "tpl_ig_dm_fomo_b",
        "name": "IG DM -- Template B (FOMO / Score 5)",
        "channel": "ig_dm",
        "template_type": "opener",
        "body_template": """Hey {first_name}, Gregory here from Exotiq.

Jay at Denver Exotic Rentals just replaced his entire ops stack with our Command Center. His words: "after 10 years in the exotic rental business, we finally have a system that gets what we need."

{company} is clearly running at a level where this fits. Worth a 15-minute look?""",
        "proof_tier": "tier1",
        "variables": '["first_name","company"]',
    },
    {
        "id": "tpl_ig_dm_visual_e",
        "name": "IG DM -- Template E (Visual / Fleet)",
        "channel": "ig_dm",
        "template_type": "opener",
        "body_template": """Hey {first_name}, it's Gregory at Exotiq.

First off, the fleet at {company} is unreal. You clearly know the {market} market.

I'm connecting with exotic car operators this month and helping optimize fleets. With you running at this scale, I'd love your take. Could we grab 15?""",
        "proof_tier": "tier2",
        "variables": '["first_name","company","market"]',
    },
    {
        "id": "tpl_ig_dm_repair_f",
        "name": "IG DM -- Template F (Re-engagement)",
        "channel": "ig_dm",
        "template_type": "follow_up_1",
        "body_template": """Hey {first_name}, Gregory Ringler here from Exotiq. I realized I dropped the ball on my end. You responded and I missed it. That's on me.

Wanted to circle back properly. We've built a command center specifically for multi-city exotic operators. Jay at Denver Exotic Rentals went from spreadsheets to a full dashboard and hasn't looked back.

Would love to reconnect if the timing works better now.""",
        "proof_tier": "tier1",
        "variables": '["first_name"]',
    },

    # -- Facebook Messenger DMs (same tone, slightly shorter)
    {
        "id": "tpl_fb_dm_peer",
        "name": "FB Messenger -- Peer Intro",
        "channel": "fb_dm",
        "template_type": "opener",
        "body_template": """Hey {first_name}, Gregory here from Exotiq. Built a platform specifically for exotic rental operators. Jay at Denver Exotic just replaced his full ops stack with it.

Saw {company} and wanted to reach out. Worth a quick 15-minute chat?""",
        "proof_tier": "tier1",
        "variables": '["first_name","company"]',
    },

    # -- Emails
    {
        "id": "tpl_email_jay_case",
        "name": "Email -- Jay Denver Case Study",
        "channel": "email",
        "template_type": "follow_up_1",
        "subject_template": "How Jay at Denver Exotic Rentals replaced 4 tools with 1",
        "body_template": """Hey {first_name},

Quick follow-up from Exotiq.

Jay at Denver Exotic Rentals had been piecing together 4 different tools for 10 years. Booking, fleet tracking, contracts, GPS. Each in a different app.

Last month he switched to our Command Center. One dashboard now. His exact words:

"After 10 years in the exotic rental business, we finally have a system that gets what we need. Exotiq just works."

I built this because I came up in this industry myself. No enterprise bloat, no Turo-style consumer mess, just software that fits how we actually operate.

Happy to show you what it looks like. 15 minutes, no pitch deck. Just a walkthrough with the founder (me).

Worth a look?

Gregory Ringler
Exotiq""",
        "proof_tier": "tier1",
        "variables": '["first_name"]',
    },
    {
        "id": "tpl_email_proof_picks_up",
        "name": "Email -- Gregory Picks Up The Phone",
        "channel": "email",
        "template_type": "follow_up_2",
        "subject_template": "One thing most software vendors won't do",
        "body_template": """{first_name},

Something Jay at Denver Exotic told me last week that stuck:

"Gregory picks up the phone. That alone puts Exotiq ahead of every other software vendor I've dealt with in ten years."

That's the bar for me. I'm the founder. If you become a customer, I'm the one answering when something breaks, when you need a feature, when you just want to talk shop.

If that sounds different than the vendors who've sold you things before, let's grab 15 minutes.

Gregory
(same number that picked up for Jay)""",
        "proof_tier": "tier1",
        "variables": '["first_name"]',
    },
    {
        "id": "tpl_email_punchy",
        "name": "Email -- Punchy Subject / Short Body",
        "channel": "email",
        "template_type": "follow_up_1",
        "subject_template": "Ten years waiting for software built for us",
        "body_template": """{first_name},

That line is from Jay at Denver Exotic Rentals. He's been running exotics for a decade and never found software that fit.

He found Exotiq.

Worth a 15-minute look at what it does for your fleet at {company}?

Gregory
Founder, Exotiq""",
        "proof_tier": "tier1",
        "variables": '["first_name","company"]',
    },

    # -- SMS (final touch)
    {
        "id": "tpl_sms_close",
        "name": "SMS -- Final Touch",
        "channel": "sms",
        "template_type": "close",
        "body_template": """Hey {first_name}, Gregory from Exotiq. Tried reaching you a couple times. Still worth 15 minutes to show you what Jay at Denver Exotic is using? No pitch, just a walkthrough.""",
        "proof_tier": "tier1",
        "variables": '["first_name"]',
    },
]

# Sequences (id, name, description, trigger_type, trigger_value, steps)
SEQUENCES = [
    {
        "id": "seq_new_operator_14",
        "name": "New Operator 14-Day",
        "description": "Default sequence for Score 3-4 leads. 5 touches across IG, email, and SMS over 14 days.",
        "trigger_type": "manual",
        "trigger_value": "score:3-4",
        "steps": [
            {"delay_days": 0,  "channel": "ig_dm", "template_id": "tpl_ig_dm_peer_d"},
            {"delay_days": 3,  "channel": "email", "template_id": "tpl_email_jay_case"},
            {"delay_days": 7,  "channel": "ig_dm", "template_id": "tpl_ig_dm_visual_e"},
            {"delay_days": 10, "channel": "email", "template_id": "tpl_email_proof_picks_up"},
            {"delay_days": 14, "channel": "sms",   "template_id": "tpl_sms_close"},
        ],
    },
    {
        "id": "seq_score5_personal",
        "name": "Score 5 Personal",
        "description": "For Score 5 leads. Gregory-led with email backup.",
        "trigger_type": "manual",
        "trigger_value": "score:5",
        "steps": [
            {"delay_days": 0, "channel": "ig_dm", "template_id": "tpl_ig_dm_fomo_b"},
            {"delay_days": 3, "channel": "phone", "template_id": None,
             "template_override": "TASK: Gregory call {company} / {first_name}. Phone: {phone}. Talk track: Jay/Denver proof, 15-min demo ask.",
             "notes": "This is a Gregory task, not an auto-send. Shows up in queue to remind Gregory to call."},
            {"delay_days": 7, "channel": "email", "template_id": "tpl_email_proof_picks_up"},
        ],
    },
    {
        "id": "seq_f1_miami",
        "name": "F1 Miami Event",
        "description": "Late April Miami event play. 3 touches focused on F1 GP proximity.",
        "trigger_type": "manual",
        "trigger_value": "market:Miami,event:F1",
        "steps": [
            {"delay_days": 0, "channel": "ig_dm", "template_id": None,
             "template_override": "Hey {first_name}, Gregory here from Exotiq. F1 Miami is coming up. Your fleet at {company} is going to be slammed. Quick question, are you adjusting pricing in real time for the weekend or setting rates in advance?"},
            {"delay_days": 3, "channel": "email", "template_id": None,
             "template_override": "{first_name},\n\nF1 Miami is one of the best weeks of the year for exotic operators in Miami. It's also the week most operators leave the most money on the table.\n\nThree ways operators typically underprice during events:\n1. Locking in rates a month out\n2. Not adjusting per day (Thursday isn't Saturday)\n3. Missing the uplift on premium inventory\n\nExotiq's pricing engine handles all three automatically. Jay in Denver saw his event-week revenue jump the first time he ran it.\n\nWant a quick look before F1? 15 minutes.\n\nGregory",
             "template_id": None},
            {"delay_days": 7, "channel": "ig_dm", "template_id": None,
             "template_override": "Hey {first_name}, F1 is next week. Last chance if you want your pricing dialed in before the weekend. 15 minutes with me and we can get it set up. Worth it?"},
        ],
    },
]


def seed():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    created_at = now()

    # Templates
    tpl_new = 0
    for tpl in TEMPLATES:
        existing = conn.execute(
            "SELECT id FROM content_templates WHERE id = ?", (tpl["id"],)
        ).fetchone()
        if existing:
            continue
        conn.execute(
            """INSERT INTO content_templates
               (id, name, channel, template_type, subject_template, body_template, variables, proof_tier, notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                tpl["id"],
                tpl["name"],
                tpl["channel"],
                tpl.get("template_type"),
                tpl.get("subject_template"),
                tpl["body_template"],
                tpl.get("variables"),
                tpl.get("proof_tier"),
                tpl.get("notes"),
                created_at,
            ),
        )
        tpl_new += 1

    # Sequences and steps
    seq_new = 0
    step_new = 0
    for seq in SEQUENCES:
        existing = conn.execute(
            "SELECT id FROM sequences WHERE id = ?", (seq["id"],)
        ).fetchone()
        if not existing:
            conn.execute(
                """INSERT INTO sequences (id, name, description, trigger_type, trigger_value, active, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, 1, ?, ?)""",
                (
                    seq["id"],
                    seq["name"],
                    seq["description"],
                    seq.get("trigger_type"),
                    seq.get("trigger_value"),
                    created_at,
                    created_at,
                ),
            )
            seq_new += 1

        # Steps (idempotent on sequence_id + step_order)
        for idx, step in enumerate(seq["steps"], start=1):
            existing_step = conn.execute(
                "SELECT id FROM sequence_steps WHERE sequence_id = ? AND step_order = ?",
                (seq["id"], idx),
            ).fetchone()
            if existing_step:
                continue
            conn.execute(
                """INSERT INTO sequence_steps
                   (sequence_id, step_order, delay_days, channel, template_id, template_override, skip_if_responded, notes)
                   VALUES (?, ?, ?, ?, ?, ?, 1, ?)""",
                (
                    seq["id"],
                    idx,
                    step["delay_days"],
                    step["channel"],
                    step.get("template_id"),
                    step.get("template_override"),
                    step.get("notes"),
                ),
            )
            step_new += 1

    conn.commit()
    conn.close()

    print(f"Seed complete: {tpl_new} new templates, {seq_new} new sequences, {step_new} new steps.")


if __name__ == "__main__":
    seed()
