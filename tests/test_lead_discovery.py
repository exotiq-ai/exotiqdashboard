"""
Tests for skills/lead_discovery.py

Uses unittest.mock to patch database access so no real SQLite connection
is required during the test run.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

# Ensure project root is on path so skills.* imports resolve.
sys.path.insert(0, str(Path(__file__).parent.parent))

import skills.lead_discovery as ld
from skills.lead_discovery import discover_leads


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def patch_db(monkeypatch):
    """
    Patch all database access in skills.lead_discovery with safe defaults.

    By default:
        - get_all_leads returns an empty list (no existing leads).
        - log_activity returns 1.

    Individual tests can override these via additional patches or by
    re-configuring the mocks exposed in the fixture.
    """
    mock_get_all_leads = MagicMock(return_value=[])
    mock_log_activity = MagicMock(return_value=1)

    monkeypatch.setattr(ld, "get_all_leads", mock_get_all_leads)
    monkeypatch.setattr(ld, "log_activity", mock_log_activity)

    yield {
        "get_all_leads": mock_get_all_leads,
        "log_activity": mock_log_activity,
    }


def _make_candidate(
    company: str = "Exotic Rentals LLC",
    ig_handle: str = "exoticrentals",
    website: str = "https://exoticrentals.com",
    market: str = "Miami",
    source: str = "google_search",
) -> dict:
    """Return a minimal candidate dict for use in tests."""
    return {
        "company": company,
        "ig_handle": ig_handle,
        "website": website,
        "market": market,
        "source": source,
    }


# ---------------------------------------------------------------------------
# Test: discover_leads returns a list
# ---------------------------------------------------------------------------


class TestDiscoverLeadsReturnType:
    def test_returns_list_when_no_results(self, patch_db):
        result = discover_leads("Miami")
        assert isinstance(result, list)

    def test_returns_list_with_new_leads(self, patch_db):
        with patch.object(ld, "_search_google", return_value=[_make_candidate()]):
            result = discover_leads("Miami")
        assert isinstance(result, list)
        assert len(result) == 1

    def test_each_result_has_required_keys(self, patch_db):
        with patch.object(ld, "_search_google", return_value=[_make_candidate()]):
            result = discover_leads("Miami")
        required_keys = {"company", "ig_handle", "website", "market", "source", "discovery_note"}
        for lead in result:
            assert required_keys.issubset(lead.keys()), (
                f"Lead is missing keys: {required_keys - lead.keys()}"
            )


# ---------------------------------------------------------------------------
# Test: deduplication against existing leads
# ---------------------------------------------------------------------------


class TestDeduplication:
    def test_existing_company_name_excluded(self, patch_db):
        """A candidate whose company name matches an existing lead is dropped."""
        existing = [{"company": "Test Co", "company_ig_handle": None, "market": "Miami"}]
        patch_db["get_all_leads"].return_value = existing

        candidates = [
            _make_candidate(company="Test Co", ig_handle="", source="google_search"),
            _make_candidate(company="Brand New Co", ig_handle="brandnewco", source="google_search"),
        ]
        with patch.object(ld, "_search_google", return_value=candidates):
            result = discover_leads("Miami")

        company_names = [r["company"] for r in result]
        assert "Test Co" not in company_names
        assert "Brand New Co" in company_names

    def test_company_name_match_is_case_insensitive(self, patch_db):
        """Dedup ignores case differences in company names."""
        existing = [{"company": "test co", "company_ig_handle": None, "market": "Miami"}]
        patch_db["get_all_leads"].return_value = existing

        candidates = [_make_candidate(company="TEST CO", ig_handle="")]
        with patch.object(ld, "_search_google", return_value=candidates):
            result = discover_leads("Miami")

        assert len(result) == 0

    def test_existing_ig_handle_excluded(self, patch_db):
        """A candidate whose IG handle matches an existing lead is dropped."""
        existing = [{"company": "Different Name", "company_ig_handle": "exoticrentals", "market": "Miami"}]
        patch_db["get_all_leads"].return_value = existing

        candidates = [_make_candidate(company="Exotic Rentals LLC", ig_handle="exoticrentals")]
        with patch.object(ld, "_search_google", return_value=candidates):
            result = discover_leads("Miami")

        assert len(result) == 0

    def test_ig_handle_match_strips_at_symbol(self, patch_db):
        """IG handle matching is robust to leading '@' in either source."""
        existing = [{"company": "Some Co", "company_ig_handle": "@superhandle", "market": "Miami"}]
        patch_db["get_all_leads"].return_value = existing

        candidates = [_make_candidate(company="Other Co", ig_handle="superhandle")]
        with patch.object(ld, "_search_google", return_value=candidates):
            result = discover_leads("Miami")

        assert len(result) == 0

    def test_no_match_returns_candidate(self, patch_db):
        """A candidate with no overlap against existing leads is included."""
        existing = [{"company": "Old Co", "company_ig_handle": "oldco", "market": "Miami"}]
        patch_db["get_all_leads"].return_value = existing

        candidates = [_make_candidate(company="New Co", ig_handle="newco")]
        with patch.object(ld, "_search_google", return_value=candidates):
            result = discover_leads("Miami")

        assert len(result) == 1
        assert result[0]["company"] == "New Co"

    def test_within_batch_duplicates_deduplicated(self, patch_db):
        """Duplicate companies across search strategies are only returned once."""
        candidate_a = _make_candidate(company="Dup Co", ig_handle="dupco", source="google_search")
        candidate_b = _make_candidate(company="Dup Co", ig_handle="dupco", source="google_maps")

        with (
            patch.object(ld, "_search_google", return_value=[candidate_a]),
            patch.object(ld, "_search_maps", return_value=[candidate_b]),
        ):
            result = discover_leads("Miami")

        assert len(result) == 1


# ---------------------------------------------------------------------------
# Test: activity logging
# ---------------------------------------------------------------------------


class TestActivityLogging:
    def test_log_activity_called_once(self, patch_db):
        discover_leads("Miami")
        assert patch_db["log_activity"].call_count == 1

    def test_log_activity_called_with_correct_type(self, patch_db):
        discover_leads("Miami")
        kwargs = patch_db["log_activity"].call_args.kwargs
        assert kwargs.get("type") == "lead_discovery"

    def test_log_activity_called_with_correct_agent(self, patch_db):
        discover_leads("Miami")
        kwargs = patch_db["log_activity"].call_args.kwargs
        assert kwargs.get("agent") == "lead_discovery"

    def test_log_activity_called_even_with_no_results(self, patch_db):
        """Logging occurs whether or not any new leads are found."""
        discover_leads("Phoenix")
        assert patch_db["log_activity"].call_count == 1

    def test_log_description_contains_market(self, patch_db):
        discover_leads("Las Vegas")
        kwargs = patch_db["log_activity"].call_args.kwargs
        assert "Las Vegas" in kwargs.get("description", "")


# ---------------------------------------------------------------------------
# Test: max_results limit
# ---------------------------------------------------------------------------


class TestMaxResults:
    def _many_candidates(self, n: int, market: str = "Miami") -> list[dict]:
        return [
            _make_candidate(
                company=f"Company {i}",
                ig_handle=f"company{i}",
                website=f"https://company{i}.com",
                market=market,
            )
            for i in range(n)
        ]

    def test_default_max_results_is_20(self, patch_db):
        candidates = self._many_candidates(50)
        with patch.object(ld, "_search_google", return_value=candidates):
            result = discover_leads("Miami")
        assert len(result) <= 20

    def test_custom_max_results_respected(self, patch_db):
        candidates = self._many_candidates(30)
        with patch.object(ld, "_search_google", return_value=candidates):
            result = discover_leads("Miami", max_results=5)
        assert len(result) == 5

    def test_max_results_zero_returns_empty(self, patch_db):
        candidates = self._many_candidates(10)
        with patch.object(ld, "_search_google", return_value=candidates):
            result = discover_leads("Miami", max_results=0)
        assert result == []

    def test_fewer_candidates_than_max_returns_all(self, patch_db):
        candidates = self._many_candidates(3)
        with patch.object(ld, "_search_google", return_value=candidates):
            result = discover_leads("Miami", max_results=10)
        assert len(result) == 3


# ---------------------------------------------------------------------------
# Test: error handling in search stubs
# ---------------------------------------------------------------------------


class TestErrorHandling:
    def test_failing_search_strategy_does_not_crash(self, patch_db):
        """An exception in one strategy should not prevent others from running."""
        with (
            patch.object(ld, "_search_google", side_effect=RuntimeError("API key missing")),
            patch.object(ld, "_search_maps", return_value=[_make_candidate()]),
        ):
            result = discover_leads("Miami")

        # Google failed but Maps succeeded -- should have 1 result.
        assert len(result) == 1

    def test_all_strategies_failing_returns_empty_list(self, patch_db):
        with (
            patch.object(ld, "_search_google", side_effect=Exception("fail")),
            patch.object(ld, "_search_instagram", side_effect=Exception("fail")),
            patch.object(ld, "_search_maps", side_effect=Exception("fail")),
        ):
            result = discover_leads("Miami")

        assert result == []

    def test_all_strategies_failing_still_logs(self, patch_db):
        """Activity is logged even when every strategy raises."""
        with (
            patch.object(ld, "_search_google", side_effect=Exception("fail")),
            patch.object(ld, "_search_instagram", side_effect=Exception("fail")),
            patch.object(ld, "_search_maps", side_effect=Exception("fail")),
        ):
            discover_leads("Miami")

        assert patch_db["log_activity"].call_count == 1
