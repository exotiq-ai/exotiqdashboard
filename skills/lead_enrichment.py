"""
Lead enrichment skill for the Exotiq Lead Intelligence Pipeline.

Runs three enrichment sources (Apollo, web search, Instagram) in sequence,
merges the results, persists provenance metadata, and logs all activity to
the activity_log table.
"""

import json
import logging
import warnings
from datetime import datetime, timezone
from typing import Any, Optional

from skills.db_utils import get_lead, log_activity, update_lead

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

# Each enrichment source returns a mapping from field name to a 3-tuple:
#   (value, source_label, confidence_label)
EnrichmentResult = dict[str, tuple[Any, str, str]]

# Valid provenance values (kept here for reference -- not enforced at runtime
# so that forward-compatible source names do not raise errors).
VALID_SOURCES = frozenset(
    {"apollo", "ig_profile", "website", "google_search", "manual", "gregory_input", "ghl_sync"}
)
VALID_CONFIDENCES = frozenset({"CONFIRMED", "ESTIMATED", "INFERRED"})


# ---------------------------------------------------------------------------
# Private stub functions
# ---------------------------------------------------------------------------


def _apollo_lookup(company: str, contact_name: str) -> EnrichmentResult:
    """
    Look up company and person data from Apollo.io.

    Real implementation: POST to https://api.apollo.io/v1/people/search
    Required env var: APOLLO_API_KEY
    Expected response format: {
        "people": [{"first_name": str, "last_name": str, "title": str,
                    "email": str, "phone_numbers": [...], "linkedin_url": str}],
        "organizations": [{"name": str, "website_url": str, "phone": str}]
    }
    Returns dict of field_name -> (value, source, confidence) tuples.
    Stub returns empty dict.

    Args:
        company: The company name to look up.
        contact_name: The contact's full name to look up.

    Returns:
        Mapping of field name to (value, source_label, confidence_label).
    """
    return {}


def _web_search_enrichment(company: str, market: str) -> EnrichmentResult:
    """
    Search the web for company website, fleet info, and Google reviews.

    Real implementation: Use Google Custom Search API or requests + BeautifulSoup
    to scrape Google search results for the company.
    Returns dict of field_name -> (value, source, confidence) tuples.
    Fields this can populate: company_website, company_google_rating,
    company_google_reviews, fleet_size, fleet_vehicle_types.
    Stub returns empty dict.

    Args:
        company: The company name to search for.
        market: The geographic market (city/region) used to narrow results.

    Returns:
        Mapping of field name to (value, source_label, confidence_label).
    """
    return {}


def _ig_profile_check(ig_handle: str) -> EnrichmentResult:
    """
    Check Instagram profile for follower count, recent posts, fleet indicators.

    Real implementation: Use the Instagram Graph API or web scraping.
    Required env var: IG_ACCESS_TOKEN
    Fields this can populate: company_ig_followers, fleet_size (estimated from
    post count), fleet_vehicle_types (parsed from post captions/hashtags).
    Returns dict of field_name -> (value, source, confidence) tuples.
    Stub returns empty dict.

    Args:
        ig_handle: The company's Instagram username (without the "@" prefix).

    Returns:
        Mapping of field name to (value, source_label, confidence_label).
    """
    return {}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _run_source(
    label: str,
    fn,
    *args: Any,
    lead_id: str,
) -> tuple[EnrichmentResult, list[str]]:
    """
    Execute one enrichment source function, catching and logging any exception.

    Args:
        label: Short human-readable name used in log messages.
        fn: The callable to invoke.
        *args: Positional arguments forwarded to fn.
        lead_id: The lead being enriched -- used for activity log entries.

    Returns:
        A 2-tuple of (result_dict, warning_messages).  On exception the result
        dict is empty and warning_messages contains one entry.
    """
    warnings_issued: list[str] = []
    try:
        result: EnrichmentResult = fn(*args)
        return result, warnings_issued
    except Exception as exc:  # noqa: BLE001
        msg = f"{label} enrichment failed for lead {lead_id}: {exc}"
        logger.warning(msg)
        warnings_issued.append(msg)
        log_activity(
            type="enrichment",
            description=f"WARNING -- {msg}",
            lead_id=lead_id,
            source=label,
            agent="lead_enrichment",
        )
        return {}, warnings_issued


def _build_history_entry(
    action: str,
    source_label: str,
    fields_updated: list[str],
) -> dict[str, Any]:
    """
    Build a single enrichment_history entry dict.

    Args:
        action: Machine-readable action name, e.g. "apollo_lookup".
        source_label: The data source string stored in provenance columns.
        fields_updated: List of field names that were populated.

    Returns:
        Dict conforming to the enrichment_history entry schema.
    """
    return {
        "action": action,
        "timestamp": _now_iso(),
        "fields_updated": fields_updated,
        "source": source_label,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def enrich_lead(lead_id: str) -> dict[str, Any]:
    """
    Enrich a lead record by running Apollo, web-search, and Instagram lookups.

    Fetches the lead from the database, runs three enrichment sources in
    sequence, merges all results (including provenance columns), appends
    entries to enrichment_history, persists the update, and logs activity.

    Args:
        lead_id: Primary key of the lead to enrich, e.g. "lead_mia_001".

    Returns:
        A summary dict with the following keys:
            - lead_id (str): The lead that was enriched.
            - fields_updated (list[str]): Data field names that received a
              new value (excludes provenance columns).
            - sources_used (list[str]): Enrichment source labels that returned
              at least one field.
            - enrichment_entries_added (int): Number of new entries appended
              to enrichment_history.

    Raises:
        ValueError: If no lead with the given lead_id exists in the database.
        RuntimeError: If the database is unavailable (propagated from db_utils).
    """
    # ------------------------------------------------------------------
    # 1. Fetch the lead
    # ------------------------------------------------------------------
    lead = get_lead(lead_id)
    if lead is None:
        raise ValueError(f"Lead '{lead_id}' not found in the database.")

    company: str = lead.get("company") or ""
    contact_name: str = (
        f"{lead.get('contact_first_name') or ''} {lead.get('contact_last_name') or ''}".strip()
    )
    market: str = lead.get("market") or ""
    ig_handle: str = lead.get("ig_handle") or ""

    # ------------------------------------------------------------------
    # 2. Run enrichment sources in sequence
    # ------------------------------------------------------------------
    apollo_result, _ = _run_source(
        "apollo",
        _apollo_lookup,
        company,
        contact_name,
        lead_id=lead_id,
    )

    web_result, _ = _run_source(
        "website",
        _web_search_enrichment,
        company,
        market,
        lead_id=lead_id,
    )

    ig_result, _ = _run_source(
        "ig_profile",
        _ig_profile_check,
        ig_handle,
        lead_id=lead_id,
    )

    # ------------------------------------------------------------------
    # 3 & 4. Merge results and build provenance columns
    # ------------------------------------------------------------------
    # Later sources override earlier ones for the same field if they also
    # return a value, giving the caller control via source ordering.
    merged_data_fields: dict[str, Any] = {}   # field -> value
    merged_update: dict[str, Any] = {}        # includes _source and _confidence

    source_results: list[tuple[str, str, EnrichmentResult]] = [
        ("apollo_lookup", "apollo", apollo_result),
        ("web_search", "website", web_result),
        ("ig_profile_check", "ig_profile", ig_result),
    ]

    for _action, _src_label, result in source_results:
        for field, payload in result.items():
            value, source_label, confidence_label = payload
            merged_data_fields[field] = value
            merged_update[field] = value
            merged_update[f"{field}_source"] = source_label
            merged_update[f"{field}_confidence"] = confidence_label

    # ------------------------------------------------------------------
    # 5. Append to enrichment_history
    # ------------------------------------------------------------------
    existing_history_raw: Optional[str] = lead.get("enrichment_history")
    try:
        enrichment_history: list[dict[str, Any]] = (
            json.loads(existing_history_raw)
            if existing_history_raw
            else []
        )
        if not isinstance(enrichment_history, list):
            enrichment_history = []
    except (json.JSONDecodeError, TypeError):
        enrichment_history = []

    new_entries: list[dict[str, Any]] = []
    sources_used: list[str] = []

    for action_name, src_label, result in source_results:
        fields_from_source = list(result.keys())
        if fields_from_source:
            sources_used.append(src_label)
        entry = _build_history_entry(action_name, src_label, fields_from_source)
        new_entries.append(entry)

    enrichment_history.extend(new_entries)
    merged_update["enrichment_history"] = json.dumps(enrichment_history)

    # ------------------------------------------------------------------
    # 6. Persist update
    # ------------------------------------------------------------------
    if merged_update:
        update_lead(lead_id, merged_update)

    # ------------------------------------------------------------------
    # 7. Log to activity_log
    # ------------------------------------------------------------------
    fields_updated = list(merged_data_fields.keys())
    description = (
        f"Enriched lead {lead_id} -- "
        f"sources: {sources_used or ['none']} -- "
        f"fields updated: {fields_updated or ['none']}"
    )
    log_activity(
        type="enrichment",
        description=description,
        lead_id=lead_id,
        source=",".join(sources_used) if sources_used else None,
        agent="lead_enrichment",
    )

    # ------------------------------------------------------------------
    # 8. Return summary
    # ------------------------------------------------------------------
    return {
        "lead_id": lead_id,
        "fields_updated": fields_updated,
        "sources_used": sources_used,
        "enrichment_entries_added": len(new_entries),
    }
