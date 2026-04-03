"""
Lead scoring skill for the Exotiq Lead Intelligence Pipeline.

Computes a 1-5 score for an exotic car rental operator lead using a
weighted rubric across five dimensions: fleet size, Instagram presence,
web presence, market position, and enrichment depth.  Results are
persisted back to the lead record and logged to the activity_log table.
"""

from datetime import datetime, timezone
from typing import Optional

from skills.db_utils import get_lead, log_activity, update_lead

# ---------------------------------------------------------------------------
# Rubric weights (must sum to 1.0)
# ---------------------------------------------------------------------------

_WEIGHT_FLEET: float = 0.40
_WEIGHT_IG: float = 0.20
_WEIGHT_WEB: float = 0.15
_WEIGHT_MARKET: float = 0.15
_WEIGHT_DEPTH: float = 0.10

# Top-tier and second-tier markets used for market-position scoring.
_TIER1_MARKETS: frozenset[str] = frozenset({"Miami", "Los Angeles"})
_TIER2_MARKETS: frozenset[str] = frozenset({"NYC", "Las Vegas", "SF Bay Area"})


# ---------------------------------------------------------------------------
# Internal helpers -- one scorer per dimension
# ---------------------------------------------------------------------------


def _score_fleet(lead: dict) -> tuple[int, str]:
    """
    Score the fleet-size dimension (weight 40%).

    Args:
        lead: Full lead record dict from the database.

    Returns:
        A 2-tuple of (points 1-5, human-readable label for rationale).
    """
    raw = lead.get("fleet_size")
    try:
        size = int(raw)
    except (TypeError, ValueError):
        return 1, "unknown fleet size"

    if size >= 20:
        return 5, f"{size} vehicles"
    if size >= 10:
        return 4, f"{size} vehicles"
    if size >= 5:
        return 3, f"{size} vehicles"
    if size >= 2:
        return 2, f"{size} vehicles"
    return 1, f"{size} vehicles"


def _score_ig(lead: dict) -> tuple[int, str]:
    """
    Score the Instagram-presence dimension (weight 20%).

    Args:
        lead: Full lead record dict from the database.

    Returns:
        A 2-tuple of (points 1-5, human-readable label for rationale).
    """
    handle = lead.get("company_ig_handle") or lead.get("ig_handle")
    raw_followers = lead.get("company_ig_followers")

    if not handle:
        return 1, "no IG handle"

    try:
        followers = int(raw_followers)
    except (TypeError, ValueError):
        # Handle exists but follower count is unknown -- treat as 0.
        return 1, "0 followers"

    if followers == 0:
        return 1, "0 followers"
    if followers >= 10_000:
        return 5, f"{followers:,} followers"
    if followers >= 5_000:
        return 4, f"{followers:,} followers"
    if followers >= 1_000:
        return 3, f"{followers:,} followers"
    return 2, f"{followers:,} followers"


def _score_web(lead: dict) -> tuple[int, str]:
    """
    Score the web-presence dimension (weight 15%).

    Args:
        lead: Full lead record dict from the database.

    Returns:
        A 2-tuple of (points 1-5, human-readable label for rationale).
    """
    website = lead.get("company_website")
    ig_handle = lead.get("company_ig_handle") or lead.get("ig_handle")
    raw_rating = lead.get("company_google_rating")

    has_website = bool(website)

    google_rating: Optional[float] = None
    try:
        google_rating = float(raw_rating)
    except (TypeError, ValueError):
        pass

    if has_website and google_rating is not None and google_rating >= 4.0:
        return 5, f"website+{google_rating} rating"
    if has_website and google_rating is not None and google_rating >= 3.0:
        return 4, f"website+{google_rating} rating"
    if has_website:
        return 3, "website only"
    if ig_handle:
        return 2, "IG only, no website"
    return 1, "no website, no IG"


def _score_market(lead: dict) -> tuple[int, str]:
    """
    Score the market-position dimension (weight 15%).

    Args:
        lead: Full lead record dict from the database.

    Returns:
        A 2-tuple of (points 1-5, human-readable label for rationale).
    """
    market: Optional[str] = lead.get("market")

    if not market:
        return 2, "unknown market"
    if market in _TIER1_MARKETS:
        return 5, market
    if market in _TIER2_MARKETS:
        return 4, market
    return 3, market


def _score_depth(lead: dict) -> tuple[int, str]:
    """
    Score the enrichment-depth dimension (weight 10%).

    Args:
        lead: Full lead record dict from the database.

    Returns:
        A 2-tuple of (points 1-5, human-readable label for rationale).
    """
    email = lead.get("contact_email")
    phone = lead.get("contact_phone")
    ig_handle = lead.get("company_ig_handle") or lead.get("ig_handle")

    has_email = bool(email)
    has_phone = bool(phone)
    has_ig = bool(ig_handle)

    if has_email and has_phone and has_ig:
        return 5, "email+phone+IG"
    if has_email and (has_phone or has_ig):
        return 4, "email+" + ("phone" if has_phone else "IG")
    if has_email:
        return 3, "email only"
    if has_ig:
        return 2, "IG only"
    return 1, "no contact data"


# ---------------------------------------------------------------------------
# Confidence calculation
# ---------------------------------------------------------------------------


def _compute_confidence(lead: dict) -> str:
    """
    Determine scoring confidence based on how many dimensions have data.

    A dimension is considered to have confirmed data when the primary field
    is present and non-None:
        - fleet:   fleet_size
        - IG:      company_ig_handle or ig_handle
        - web:     company_website
        - market:  market
        - depth:   contact_email

    Args:
        lead: Full lead record dict from the database.

    Returns:
        One of "HIGH", "MEDIUM", or "LOW".
    """
    dimensions_with_data = sum([
        lead.get("fleet_size") is not None,
        bool(lead.get("company_ig_handle") or lead.get("ig_handle")),
        lead.get("company_website") is not None,
        lead.get("market") is not None,
        lead.get("contact_email") is not None,
    ])

    if dimensions_with_data == 5:
        return "HIGH"
    if dimensions_with_data >= 3:
        return "MEDIUM"
    return "LOW"


# ---------------------------------------------------------------------------
# Rationale builder
# ---------------------------------------------------------------------------


def _build_rationale(
    fleet_pts: int,
    fleet_label: str,
    ig_pts: int,
    ig_label: str,
    web_pts: int,
    web_label: str,
    market_pts: int,
    market_label: str,
    depth_pts: int,
    depth_label: str,
    final_score: int,
    confidence: str,
) -> str:
    """
    Assemble the human-readable rationale string.

    Uses " -- " (spaced double hyphens) as a separator between sections.
    No em-dashes are used anywhere in this module.

    Args:
        fleet_pts:    Points awarded for fleet size.
        fleet_label:  Descriptive label for the fleet-size value.
        ig_pts:       Points awarded for Instagram presence.
        ig_label:     Descriptive label for the IG value.
        web_pts:      Points awarded for web presence.
        web_label:    Descriptive label for the web value.
        market_pts:   Points awarded for market position.
        market_label: Descriptive label for the market value.
        depth_pts:    Points awarded for enrichment depth.
        depth_label:  Descriptive label for the depth value.
        final_score:  The rounded, clamped final score (1-5).
        confidence:   One of "HIGH", "MEDIUM", "LOW".

    Returns:
        A single human-readable string summarising the scoring decision.
    """
    parts = [
        f"Fleet: {fleet_label} ({fleet_pts}pts, 40%)",
        f"IG: {ig_label} ({ig_pts}pts, 20%)",
        f"Web: {web_label} ({web_pts}pts, 15%)",
        f"Market: {market_label} ({market_pts}pts, 15%)",
        f"Depth: {depth_label} ({depth_pts}pts, 10%)",
        f"Score: {final_score} ({confidence})",
    ]
    return " -- ".join(parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def score_lead(lead_id: str) -> dict:
    """
    Score a lead using the weighted rubric and return the result.

    Fetches the lead from the database, evaluates all five scoring
    dimensions, computes a weighted average rounded to the nearest integer
    (clamped to [1, 5]), determines a confidence level, builds a
    human-readable rationale, persists the results back to the lead record,
    and logs the event to the activity_log table.

    Previous score handling:
        - If the lead already has ``scoring_score`` set but no
          ``scoring_previous_score``, the current score is promoted to
          ``scoring_previous_score`` before the new score is written.
        - If ``scoring_previous_score`` already exists (the lead has been
          scored at least twice before), it is left unchanged so the
          oldest score is always preserved.

    Args:
        lead_id: Primary key of the lead to score, e.g. "lead_mia_001".

    Returns:
        A dict with the following keys:
            - lead_id (str): The lead that was scored.
            - score (int): The computed score, 1-5.
            - confidence (str): "HIGH", "MEDIUM", or "LOW".
            - rationale (str): Human-readable explanation of the score.
            - previous_score (int | None): The score that was stored before
              this run, or None if the lead had not been scored before.

    Raises:
        ValueError: If no lead with the given ``lead_id`` exists.
        RuntimeError: If the database is unavailable (propagated from
            db_utils).
    """
    # ------------------------------------------------------------------
    # 1. Fetch the lead
    # ------------------------------------------------------------------
    lead = get_lead(lead_id)
    if lead is None:
        raise ValueError(f"Lead '{lead_id}' not found in the database.")

    # ------------------------------------------------------------------
    # 2. Determine previous score (preserve the oldest on repeated scoring)
    # ------------------------------------------------------------------
    existing_score = lead.get("scoring_score")
    existing_previous = lead.get("scoring_previous_score")

    # The value we will surface to the caller and write as scoring_previous_score.
    if existing_previous is not None:
        # Lead has been scored at least twice before -- keep the oldest.
        previous_score: Optional[int] = int(existing_previous)
    elif existing_score is not None:
        # First rescore -- promote current score to previous.
        previous_score = int(existing_score)
    else:
        # Brand-new scoring -- no previous score.
        previous_score = None

    # ------------------------------------------------------------------
    # 3. Score each dimension
    # ------------------------------------------------------------------
    fleet_pts, fleet_label = _score_fleet(lead)
    ig_pts, ig_label = _score_ig(lead)
    web_pts, web_label = _score_web(lead)
    market_pts, market_label = _score_market(lead)
    depth_pts, depth_label = _score_depth(lead)

    # ------------------------------------------------------------------
    # 4. Compute weighted average and clamp to [1, 5]
    # ------------------------------------------------------------------
    weighted_sum = (
        fleet_pts * _WEIGHT_FLEET
        + ig_pts * _WEIGHT_IG
        + web_pts * _WEIGHT_WEB
        + market_pts * _WEIGHT_MARKET
        + depth_pts * _WEIGHT_DEPTH
    )
    final_score: int = max(1, min(5, round(weighted_sum)))

    # ------------------------------------------------------------------
    # 5. Confidence
    # ------------------------------------------------------------------
    confidence = _compute_confidence(lead)

    # ------------------------------------------------------------------
    # 6. Rationale
    # ------------------------------------------------------------------
    rationale = _build_rationale(
        fleet_pts, fleet_label,
        ig_pts, ig_label,
        web_pts, web_label,
        market_pts, market_label,
        depth_pts, depth_label,
        final_score,
        confidence,
    )

    # ------------------------------------------------------------------
    # 7. Persist to the lead record
    # ------------------------------------------------------------------
    update_fields: dict = {
        "scoring_score": final_score,
        "scoring_confidence": confidence,
        "scoring_rationale": rationale,
        "scoring_scored_at": datetime.now(timezone.utc).isoformat(),
    }
    if previous_score is not None:
        update_fields["scoring_previous_score"] = previous_score

    update_lead(lead_id, update_fields)

    # ------------------------------------------------------------------
    # 8. Log to activity_log
    # ------------------------------------------------------------------
    log_activity(
        type="scoring",
        description=(
            f"Scored lead {lead_id} -- "
            f"score: {final_score} ({confidence}) -- "
            f"previous: {previous_score}"
        ),
        lead_id=lead_id,
        agent="lead_scoring",
    )

    # ------------------------------------------------------------------
    # 9. Return result summary
    # ------------------------------------------------------------------
    return {
        "lead_id": lead_id,
        "score": final_score,
        "confidence": confidence,
        "rationale": rationale,
        "previous_score": previous_score,
    }
