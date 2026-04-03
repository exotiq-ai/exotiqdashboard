"""
Lead discovery skill -- finds exotic car rental operators via web search.

This module stubs web search API calls with documented interfaces.
Replace the stub implementations with real API calls when keys are available.
"""

import logging
import warnings
from typing import Optional

from skills.db_utils import get_all_leads, log_activity

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Private search stubs
# ---------------------------------------------------------------------------


def _search_google(market: str, max_results: int) -> list[dict]:
    """
    Search Google for exotic car rental operators in the given market.

    Real implementation: Use the Google Custom Search JSON API.
    Endpoint: https://www.googleapis.com/customsearch/v1
    Required env vars: GOOGLE_SEARCH_API_KEY, GOOGLE_SEARCH_CX
    Query format: "exotic car rental {market} site:instagram.com OR -site:instagram.com"
    Returns raw search results parsed into candidate dicts.

    Each returned dict should have these keys:
        company (str): Business name parsed from search result title/snippet.
        ig_handle (str): Instagram handle if discoverable, else empty string.
        website (str): Primary website URL from the search result.
        market (str): The market passed in.
        source (str): Always "google_search".

    Stub returns empty list -- replace with real API call.

    Args:
        market: Geographic market to search within, e.g. "Miami".
        max_results: Maximum number of candidate dicts to return.

    Returns:
        List of candidate dicts, up to max_results entries.
    """
    return []


def _search_instagram(market: str, max_results: int) -> list[dict]:
    """
    Search Instagram for exotic car rental operators in the given market.

    Real implementation: Use the Instagram Graph API or a third-party scraping
    service (e.g. Apify Instagram Scraper) to search hashtags and location tags
    associated with the market.
    Required env vars: INSTAGRAM_ACCESS_TOKEN (Graph API) or
        APIFY_API_KEY (scraper route).
    Search strategy:
        - Hashtag search: #exoticcarrental{market.lower().replace(' ', '')}
        - Location tag search for the given market city.
        - Keyword search in bio: "exotic rental", "supercar rental", etc.

    Each returned dict should have these keys:
        company (str): Business name from the Instagram profile display name.
        ig_handle (str): Instagram username (without the @ symbol).
        website (str): Link-in-bio URL, or empty string if absent.
        market (str): The market passed in.
        source (str): Always "instagram_search".

    Stub returns empty list -- replace with real API call.

    Args:
        market: Geographic market to search within, e.g. "Miami".
        max_results: Maximum number of candidate dicts to return.

    Returns:
        List of candidate dicts, up to max_results entries.
    """
    return []


def _search_maps(market: str, max_results: int) -> list[dict]:
    """
    Search Google Maps for exotic car rental operators in the given market.

    Real implementation: Use the Google Places API (Text Search endpoint).
    Endpoint: https://maps.googleapis.com/maps/api/place/textsearch/json
    Required env vars: GOOGLE_MAPS_API_KEY
    Query format: "exotic car rental {market}"
    Follow up each result with a Place Details call to obtain the website.

    Each returned dict should have these keys:
        company (str): Business name from the Places API name field.
        ig_handle (str): Empty string -- Maps does not surface IG handles.
        website (str): Website from Place Details, or empty string if absent.
        market (str): The market passed in.
        source (str): Always "google_maps".

    Stub returns empty list -- replace with real API call.

    Args:
        market: Geographic market to search within, e.g. "Miami".
        max_results: Maximum number of candidate dicts to return.

    Returns:
        List of candidate dicts, up to max_results entries.
    """
    return []


# ---------------------------------------------------------------------------
# Deduplication helpers
# ---------------------------------------------------------------------------


def _build_existing_sets(
    existing_leads: list[dict],
) -> tuple[set[str], set[str]]:
    """
    Build sets of known company names and IG handles from existing leads.

    Company names are normalised to lower-case for case-insensitive matching.
    IG handles are normalised to lower-case with leading '@' stripped.

    Args:
        existing_leads: List of lead dicts as returned by get_all_leads().

    Returns:
        A 2-tuple of (company_names, ig_handles) where each element is a set
        of normalised strings.  Null/empty values are omitted.
    """
    company_names: set[str] = set()
    ig_handles: set[str] = set()

    for lead in existing_leads:
        company = lead.get("company") or ""
        if company:
            company_names.add(company.strip().lower())

        handle = lead.get("company_ig_handle") or ""
        if handle:
            ig_handles.add(handle.strip().lower().lstrip("@"))

    return company_names, ig_handles


def _is_duplicate(
    candidate: dict,
    existing_companies: set[str],
    existing_ig_handles: set[str],
) -> bool:
    """
    Return True if a candidate already exists in the leads database.

    Matching rules:
        1. Company name -- case-insensitive exact match.
        2. IG handle -- case-insensitive exact match (if candidate has one).

    Args:
        candidate: A candidate dict with at least 'company' and 'ig_handle' keys.
        existing_companies: Normalised set of known company names.
        existing_ig_handles: Normalised set of known IG handles.

    Returns:
        True if the candidate is a duplicate, False otherwise.
    """
    company = (candidate.get("company") or "").strip().lower()
    if company and company in existing_companies:
        return True

    ig_handle = (candidate.get("ig_handle") or "").strip().lower().lstrip("@")
    if ig_handle and ig_handle in existing_ig_handles:
        return True

    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def discover_leads(market: str, max_results: int = 20) -> list[dict]:
    """
    Find new exotic car rental operators in the given market via web search.

    Executes three search strategies in sequence -- Google search, Instagram
    handle search, and Google Maps -- merges the raw candidates, deduplicates
    them against the leads already stored in SQLite, and returns only the
    genuinely new entries.

    Each returned dict has these keys:
        company (str): Business name.
        ig_handle (str): Instagram handle, or empty string if unknown.
        website (str): Website URL, or empty string if unknown.
        market (str): The market searched.
        source (str): Which strategy surfaced this candidate.
        discovery_note (str): Human-readable note summarising how the lead
            was found and whether any dedup checks were applied.

    Activity is logged to the activity_log table with type="lead_discovery"
    and agent="lead_discovery" regardless of how many new leads are found.

    Search stub errors are caught and logged as warnings; discovery continues
    with whatever results the remaining strategies provide.

    Args:
        market: Geographic market to search within, e.g. "Miami".
        max_results: Upper bound on total new leads to return across all
            strategies.  Defaults to 20.

    Returns:
        List of new candidate dicts not yet present in the database, capped
        at max_results entries.
    """
    strategies = [
        ("google_search", _search_google),
        ("instagram_search", _search_instagram),
        ("google_maps", _search_maps),
    ]

    raw_candidates: list[dict] = []

    for strategy_name, search_fn in strategies:
        try:
            results = search_fn(market, max_results)
            raw_candidates.extend(results)
        except Exception as exc:  # noqa: BLE001
            warnings.warn(
                f"Search strategy '{strategy_name}' failed for market "
                f"'{market}': {exc}",
                stacklevel=2,
            )
            logger.warning(
                "Search strategy '%s' raised an exception for market '%s': %s",
                strategy_name,
                market,
                exc,
                exc_info=True,
            )

    # Deduplicate candidates within this batch by company name first (keep
    # first occurrence), then apply DB-level dedup.
    seen_companies: set[str] = set()
    seen_handles: set[str] = set()
    deduped_within_batch: list[dict] = []

    for candidate in raw_candidates:
        company_key = (candidate.get("company") or "").strip().lower()
        handle_key = (
            (candidate.get("ig_handle") or "").strip().lower().lstrip("@")
        )

        already_seen = False
        if company_key and company_key in seen_companies:
            already_seen = True
        if handle_key and handle_key in seen_handles:
            already_seen = True

        if not already_seen:
            deduped_within_batch.append(candidate)
            if company_key:
                seen_companies.add(company_key)
            if handle_key:
                seen_handles.add(handle_key)

    # Load existing leads and build lookup sets for DB-level dedup.
    existing_leads = get_all_leads()
    existing_companies, existing_ig_handles = _build_existing_sets(
        existing_leads
    )

    new_leads: list[dict] = []
    for candidate in deduped_within_batch:
        if len(new_leads) >= max_results:
            break

        if _is_duplicate(candidate, existing_companies, existing_ig_handles):
            continue

        # Ensure all required output keys are present and add discovery_note.
        enriched: dict = {
            "company": candidate.get("company") or "",
            "ig_handle": candidate.get("ig_handle") or "",
            "website": candidate.get("website") or "",
            "market": candidate.get("market") or market,
            "source": candidate.get("source") or "unknown",
            "discovery_note": (
                f"Discovered via {candidate.get('source', 'unknown')} "
                f"strategy for market '{market}'. "
                f"Not present in existing leads database."
            ),
        }
        new_leads.append(enriched)

    # Log discovery activity regardless of result count.
    log_activity(
        type="lead_discovery",
        description=(
            f"Discovered {len(new_leads)} new lead(s) for market '{market}' "
            f"from {len(raw_candidates)} raw candidate(s) across "
            f"{len(strategies)} search strategies."
        ),
        source=None,
        agent="lead_discovery",
    )

    return new_leads
