"""
DM Drafting skill for the Exotiq Lead Intelligence Pipeline.

Generates personalized Instagram DM drafts for exotic car rental operator leads,
selects the appropriate message template based on lead scoring and context,
enforces message constraints, and persists the result to the dm_drafts table.
"""

import json
import re
from datetime import datetime, timezone
from typing import Optional

from skills.db_utils import get_db, get_lead, log_activity, update_lead


# ---------------------------------------------------------------------------
# Template definitions
# ---------------------------------------------------------------------------

TEMPLATE_D = (
    "Hey {handle} -- Gregory here, founder of Exotiq AI. "
    "Been following your operation, {fleet_context}. "
    "We help operators like you get in front of buyers who are already "
    "searching for exactly what you're running -- qualified leads, no cold calls. "
    "We're selective about who we work with and {market} is a market we're "
    "actively building in. Would love to show you what we're doing for operators "
    "there. Worth a quick look?"
)

TEMPLATE_B = (
    "Hey {handle} -- Gregory, founder of Exotiq AI. "
    "We're working with a few top operators in {market} right now. "
    "The ones we partner with are seeing real inbound from people who searched, "
    "found them, and are ready to book. We keep the network tight so the leads "
    "stay clean. You're exactly the kind of operation we look for. "
    "If you're open to it, happy to show you what it looks like."
)

TEMPLATE_E = (
    "Hey {handle} -- love the {vehicle_mention}. "
    "Gregory here, founder of Exotiq AI. "
    "We connect operators running fleets like yours with buyers who are actively "
    "searching -- not browsers, actual bookers. "
    "Working with a handful of operators in {market} and keeping it tight. "
    "Your setup would be a strong fit. Worth a conversation?"
)

TEMPLATE_F = (
    "Hey {handle} -- Gregory again. Wanted to follow up properly. "
    "We help exotic operators get in front of qualified buyers who are already "
    "searching in {market}. No fluff, just results. "
    "Happy to show you exactly how it works if you want a quick look."
)

# Maps template letter to raw template string
TEMPLATES: dict[str, str] = {
    "D": TEMPLATE_D,
    "B": TEMPLATE_B,
    "E": TEMPLATE_E,
    "F": TEMPLATE_F,
}

# Outreach status values that signal a previous failed or errored outreach
_FAILED_OUTREACH_STATUSES = frozenset(
    {"failed", "error", "bounced", "no_response", "undelivered"}
)

# Words/phrases forbidden in any DM text
_FORBIDDEN_PATTERNS: list[tuple[str, str]] = [
    (r"calendly", "Calendly"),
    (r"\$", "$"),
    (r"\bpercent\b", "percent"),
    (r"%", "%"),
    (r"\bcost\b", "cost"),
    (r"\bprice\b", "price"),
    (r"\bfee\b", "fee"),
    (r"ai[\s-]?tools", "AI tools"),
    (r"ai[\s-]?powered", "AI-powered"),
]

_MAX_WORDS = 150


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _select_template(lead: dict) -> str:
    """
    Choose the best template letter for a given lead dict.

    Priority order (highest to lowest): F > E > B > D.

    Args:
        lead: A lead record dict as returned by get_lead().

    Returns:
        A single uppercase letter string: "F", "E", "B", or "D".
    """
    score: Optional[int] = lead.get("scoring_score")
    outreach_status: Optional[str] = (lead.get("outreach_status") or "").lower()
    fleet_vehicle_types: Optional[str] = lead.get("fleet_vehicle_types")

    # Template F -- previous failed/error outreach (highest priority)
    if outreach_status in _FAILED_OUTREACH_STATUSES:
        return "F"

    # Template E -- score >= 3 AND fleet_vehicle_types is set
    if score is not None and score >= 3 and fleet_vehicle_types:
        return "E"

    # Template B -- score == 5
    if score == 5:
        return "B"

    # Template D -- score 3 or 4, or unknown/None (default)
    return "D"


def _resolve_handle(lead: dict) -> str:
    """
    Return the best display handle for the opening greeting.

    Preference order: contact_ig_personal > company_ig_handle > company name.
    Strips a leading "@" if present.

    Args:
        lead: A lead record dict.

    Returns:
        A non-empty string to use as the {handle} variable.
    """
    for field in ("contact_ig_personal", "company_ig_handle"):
        value: Optional[str] = lead.get(field)
        if value and value.strip():
            return value.strip().lstrip("@")
    return lead.get("company", "friend") or "friend"


def _resolve_fleet_context(lead: dict) -> str:
    """
    Build the fleet context phrase used in Template D.

    Args:
        lead: A lead record dict.

    Returns:
        A short string describing the fleet size.
    """
    fleet_size: Optional[int] = lead.get("fleet_size")
    if fleet_size:
        return f"running {fleet_size} cars"
    return "running a solid fleet"


def _resolve_vehicle_mention(lead: dict) -> str:
    """
    Extract the first vehicle type from fleet_vehicle_types JSON array.

    Args:
        lead: A lead record dict.

    Returns:
        The first vehicle name, or "fleet" as a fallback.
    """
    raw: Optional[str] = lead.get("fleet_vehicle_types")
    if raw:
        try:
            vehicles = json.loads(raw)
            if isinstance(vehicles, list) and vehicles:
                first = str(vehicles[0]).strip()
                if first:
                    return first
        except (json.JSONDecodeError, TypeError):
            pass
    return "fleet"


def _build_dm_text(template_letter: str, lead: dict) -> str:
    """
    Render the chosen template with lead-specific variable substitutions.

    Args:
        template_letter: One of "D", "B", "E", "F".
        lead: A lead record dict.

    Returns:
        The rendered DM text string before constraint enforcement.
    """
    handle = _resolve_handle(lead)
    market: str = lead.get("market") or "your market"

    template_str = TEMPLATES[template_letter]

    variables: dict[str, str] = {
        "handle": handle,
        "market": market,
        "fleet_context": _resolve_fleet_context(lead),
        "vehicle_mention": _resolve_vehicle_mention(lead),
    }

    return template_str.format(**variables)


def _replace_em_dashes(text: str) -> str:
    """
    Replace all em-dash characters (U+2014) with " -- ".

    Also catches the common HTML entity and the two-char sequence.

    Args:
        text: Raw DM text.

    Returns:
        Text with em-dashes substituted.
    """
    # Unicode em-dash
    text = text.replace("\u2014", " -- ")
    # HTML entity (just in case)
    text = text.replace("&mdash;", " -- ")
    return text


def _enforce_word_limit(text: str, max_words: int = _MAX_WORDS) -> str:
    """
    Truncate text to at most max_words words at a word boundary.

    If truncation occurs, appends "..." to the result.

    Args:
        text: The DM text to check.
        max_words: Maximum allowed word count (inclusive).

    Returns:
        The original text if within limit, or a truncated version ending in "...".
    """
    words = text.split()
    if len(words) <= max_words:
        return text
    truncated = " ".join(words[:max_words])
    return truncated + "..."


def _check_forbidden_content(text: str) -> list[str]:
    """
    Return a list of forbidden phrases found in the DM text.

    Args:
        text: The DM text to inspect.

    Returns:
        A (possibly empty) list of matched forbidden terms.
    """
    found: list[str] = []
    lower_text = text.lower()
    for pattern, label in _FORBIDDEN_PATTERNS:
        if re.search(pattern, lower_text, re.IGNORECASE):
            found.append(label)
    return found


def _build_do_not_say(lead: dict) -> list[str]:
    """
    Build the DO NOT SAY list for a lead.

    Always includes: "competitor names", "pricing", "Calendly links".
    Conditionally adds items based on lead data.

    Args:
        lead: A lead record dict.

    Returns:
        A list of strings describing things to avoid in outreach.
    """
    items: list[str] = [
        "competitor names",
        "pricing",
        "Calendly links",
    ]

    notes: str = (lead.get("notes") or "").lower()
    if "call only" in notes or "no dm" in notes:
        items.append("direct outreach -- use phone")

    score: Optional[int] = lead.get("scoring_score")
    if score == 5:
        items.append("automated outreach tools")

    return items


def _save_dm_draft(
    lead_id: str,
    template_used: str,
    dm_text: str,
    do_not_say: list[str],
) -> int:
    """
    Insert a new row into the dm_drafts table and return its rowid.

    Args:
        lead_id: The lead's primary key.
        template_used: Template letter ("D", "B", "E", or "F").
        dm_text: The finalized DM text.
        do_not_say: List of items to avoid.

    Returns:
        The integer primary key of the newly inserted dm_drafts row.

    Raises:
        RuntimeError: If the database insert fails.
    """
    conn = get_db()
    try:
        cursor = conn.execute(
            """
            INSERT INTO dm_drafts
                (lead_id, template_used, dm_text, do_not_say,
                 client_review, approval_status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                lead_id,
                template_used,
                dm_text,
                json.dumps(do_not_say),
                "Y",
                "PENDING",
                _now_iso(),
            ),
        )
        conn.commit()
        draft_id: int = cursor.lastrowid
        return draft_id
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def draft_dm(lead_id: str) -> dict:
    """
    Draft a personalized DM for a lead and save it to the dm_drafts table.

    Workflow:
        1. Fetch lead data via get_lead().
        2. Select the best template (priority: F > E > B > D).
        3. Render template variables from lead fields.
        4. Replace em-dashes with " -- ".
        5. Enforce the 150-word maximum (truncate at word boundary + "...").
        6. Raise ValueError if any forbidden content survives rendering.
        7. Persist the draft to dm_drafts and update the leads record.
        8. Log to activity_log.

    Args:
        lead_id: The primary key of the lead to draft a DM for.

    Returns:
        A dict with the following keys:
            - lead_id (str): The lead's primary key.
            - template_used (str): Template letter selected ("D", "B", "E", "F").
            - dm_text (str): The final DM body text.
            - word_count (int): Number of words in dm_text.
            - draft_id (int): Primary key of the new dm_drafts row.

    Raises:
        ValueError: If the lead is not found, or if forbidden content is detected
                    in the rendered DM text.
        RuntimeError: If the database is unavailable.
    """
    lead = get_lead(lead_id)
    if lead is None:
        raise ValueError(f"Lead not found: {lead_id!r}")

    # Step 1: Select template
    template_letter = _select_template(lead)

    # Step 2: Render DM text
    dm_text = _build_dm_text(template_letter, lead)

    # Step 3: Clean up em-dashes
    dm_text = _replace_em_dashes(dm_text)

    # Step 4: Enforce word limit
    dm_text = _enforce_word_limit(dm_text)

    # Step 5: Guard against forbidden content
    forbidden_found = _check_forbidden_content(dm_text)
    if forbidden_found:
        raise ValueError(
            f"DM text contains forbidden content: {forbidden_found}. "
            f"Review template or lead data."
        )

    # Step 6: Build DO NOT SAY list
    do_not_say = _build_do_not_say(lead)

    # Step 7: Persist draft
    draft_id = _save_dm_draft(lead_id, template_letter, dm_text, do_not_say)

    # Step 8: Update lead record
    update_lead(
        lead_id,
        {
            "outreach_dm_draft": dm_text,
            "outreach_template_used": template_letter,
            "outreach_client_review": "Y",
            "outreach_approval_status": "PENDING",
            "outreach_do_not_say": json.dumps(do_not_say),
        },
    )

    # Step 9: Log activity
    log_activity(
        type="dm_draft",
        description=f"Drafted DM for lead {lead_id} using template {template_letter}",
        lead_id=lead_id,
        agent="dm_drafting",
    )

    word_count = len(dm_text.split())

    return {
        "lead_id": lead_id,
        "template_used": template_letter,
        "dm_text": dm_text,
        "word_count": word_count,
        "draft_id": draft_id,
    }
