"""
Tests for skills/lead_scoring.py

Uses unittest.mock to patch all database access so no real SQLite
connection is required during the test run.

Coverage:
    - Each of the five scoring dimensions in isolation
    - Full weighted calculation for known inputs
    - Confidence level assignment
    - Rationale string construction (format checks)
    - Previous-score preservation on first and subsequent rescores
    - update_lead and log_activity called with correct arguments
    - ValueError raised for unknown lead
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

# Ensure the project root is on sys.path so "skills.*" imports resolve.
sys.path.insert(0, str(Path(__file__).parent.parent))

import skills.lead_scoring as ls
from skills.lead_scoring import score_lead


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_lead(
    lead_id: str = "lead_test_001",
    fleet_size=None,
    ig_handle: str = "",
    company_ig_handle: str = "",
    company_ig_followers=None,
    company_website: str = "",
    company_google_rating=None,
    market: str = "",
    contact_email: str = "",
    contact_phone: str = "",
    scoring_score=None,
    scoring_previous_score=None,
) -> dict:
    """Return a minimal lead dict with sensible defaults (mostly empty)."""
    return {
        "id": lead_id,
        "fleet_size": fleet_size,
        "ig_handle": ig_handle,
        "company_ig_handle": company_ig_handle,
        "company_ig_followers": company_ig_followers,
        "company_website": company_website or None,
        "company_google_rating": company_google_rating,
        "market": market or None,
        "contact_email": contact_email or None,
        "contact_phone": contact_phone or None,
        "scoring_score": scoring_score,
        "scoring_previous_score": scoring_previous_score,
    }


@pytest.fixture(autouse=True)
def patch_db(monkeypatch):
    """
    Replace all database callsites in skills.lead_scoring with mocks.

    By default:
        - get_lead returns a mostly-empty lead (all dimensions score 1).
        - update_lead returns True.
        - log_activity returns 1.

    Individual tests override get_lead's return value as needed.
    """
    mock_get_lead = MagicMock(return_value=_make_lead())
    mock_update_lead = MagicMock(return_value=True)
    mock_log_activity = MagicMock(return_value=1)

    monkeypatch.setattr(ls, "get_lead", mock_get_lead)
    monkeypatch.setattr(ls, "update_lead", mock_update_lead)
    monkeypatch.setattr(ls, "log_activity", mock_log_activity)

    yield {
        "get_lead": mock_get_lead,
        "update_lead": mock_update_lead,
        "log_activity": mock_log_activity,
    }


# ---------------------------------------------------------------------------
# Dimension: Fleet size
# ---------------------------------------------------------------------------


class TestFleetScoring:
    """_score_fleet awards points purely from fleet_size."""

    @pytest.mark.parametrize(
        "fleet_size,expected_pts",
        [
            (20, 5),
            (43, 5),
            (100, 5),
            (19, 4),
            (10, 4),
            (9, 3),
            (5, 3),
            (4, 2),
            (2, 2),
            (1, 1),
            (0, 1),
        ],
    )
    def test_fleet_point_boundaries(self, fleet_size, expected_pts):
        pts, _ = ls._score_fleet({"fleet_size": fleet_size})
        assert pts == expected_pts

    def test_fleet_none_returns_1(self):
        pts, label = ls._score_fleet({"fleet_size": None})
        assert pts == 1

    def test_fleet_non_numeric_returns_1(self):
        pts, _ = ls._score_fleet({"fleet_size": "lots"})
        assert pts == 1

    def test_fleet_label_contains_size(self):
        _, label = ls._score_fleet({"fleet_size": 15})
        assert "15" in label


# ---------------------------------------------------------------------------
# Dimension: Instagram presence
# ---------------------------------------------------------------------------


class TestIGScoring:
    """_score_ig awards points based on handle existence and follower count."""

    def test_no_handle_returns_1(self):
        pts, _ = ls._score_ig({"company_ig_handle": None, "ig_handle": None,
                                "company_ig_followers": 50000})
        assert pts == 1

    def test_empty_handle_returns_1(self):
        pts, _ = ls._score_ig({"company_ig_handle": "", "ig_handle": "",
                                "company_ig_followers": 50000})
        assert pts == 1

    @pytest.mark.parametrize(
        "followers,expected_pts",
        [
            (10_000, 5),
            (50_000, 5),
            (9_999, 4),
            (5_000, 4),
            (4_999, 3),
            (1_000, 3),
            (999, 2),
            (1, 2),
            (0, 1),
        ],
    )
    def test_ig_follower_boundaries(self, followers, expected_pts):
        pts, _ = ls._score_ig({
            "company_ig_handle": "handle",
            "ig_handle": "",
            "company_ig_followers": followers,
        })
        assert pts == expected_pts

    def test_handle_present_but_no_follower_data_returns_1(self):
        pts, _ = ls._score_ig({
            "company_ig_handle": "somehandle",
            "ig_handle": "",
            "company_ig_followers": None,
        })
        assert pts == 1

    def test_ig_handle_fallback_to_ig_handle_field(self):
        """Falls back to ig_handle when company_ig_handle is absent."""
        pts, _ = ls._score_ig({
            "company_ig_handle": None,
            "ig_handle": "fallback_handle",
            "company_ig_followers": 12_000,
        })
        assert pts == 5


# ---------------------------------------------------------------------------
# Dimension: Web presence
# ---------------------------------------------------------------------------


class TestWebScoring:
    """_score_web scores based on website + Google rating + IG presence."""

    def test_website_and_high_rating_returns_5(self):
        pts, _ = ls._score_web({
            "company_website": "https://example.com",
            "company_google_rating": 4.7,
            "company_ig_handle": None,
            "ig_handle": None,
        })
        assert pts == 5

    def test_website_and_rating_at_4_returns_5(self):
        pts, _ = ls._score_web({
            "company_website": "https://example.com",
            "company_google_rating": 4.0,
            "company_ig_handle": None,
            "ig_handle": None,
        })
        assert pts == 5

    def test_website_and_mid_rating_returns_4(self):
        pts, _ = ls._score_web({
            "company_website": "https://example.com",
            "company_google_rating": 3.5,
            "company_ig_handle": None,
            "ig_handle": None,
        })
        assert pts == 4

    def test_website_and_rating_at_3_returns_4(self):
        pts, _ = ls._score_web({
            "company_website": "https://example.com",
            "company_google_rating": 3.0,
            "company_ig_handle": None,
            "ig_handle": None,
        })
        assert pts == 4

    def test_website_no_rating_returns_3(self):
        pts, _ = ls._score_web({
            "company_website": "https://example.com",
            "company_google_rating": None,
            "company_ig_handle": None,
            "ig_handle": None,
        })
        assert pts == 3

    def test_no_website_with_ig_returns_2(self):
        pts, _ = ls._score_web({
            "company_website": None,
            "company_google_rating": None,
            "company_ig_handle": "someig",
            "ig_handle": "",
        })
        assert pts == 2

    def test_no_website_no_ig_returns_1(self):
        pts, _ = ls._score_web({
            "company_website": None,
            "company_google_rating": None,
            "company_ig_handle": None,
            "ig_handle": None,
        })
        assert pts == 1

    def test_low_rating_website_only_returns_3(self):
        """A rating below 3.0 should fall through to website-only (3 pts)."""
        pts, _ = ls._score_web({
            "company_website": "https://example.com",
            "company_google_rating": 2.8,
            "company_ig_handle": None,
            "ig_handle": None,
        })
        assert pts == 3

    def test_label_contains_rating(self):
        _, label = ls._score_web({
            "company_website": "https://example.com",
            "company_google_rating": 4.7,
            "company_ig_handle": None,
            "ig_handle": None,
        })
        assert "4.7" in label


# ---------------------------------------------------------------------------
# Dimension: Market position
# ---------------------------------------------------------------------------


class TestMarketScoring:
    """_score_market awards points based on known market tiers."""

    @pytest.mark.parametrize("market", ["Miami", "Los Angeles"])
    def test_tier1_markets_return_5(self, market):
        pts, label = ls._score_market({"market": market})
        assert pts == 5
        assert label == market

    @pytest.mark.parametrize("market", ["NYC", "Las Vegas", "SF Bay Area"])
    def test_tier2_markets_return_4(self, market):
        pts, label = ls._score_market({"market": market})
        assert pts == 4
        assert label == market

    def test_other_market_returns_3(self):
        pts, label = ls._score_market({"market": "Phoenix"})
        assert pts == 3
        assert label == "Phoenix"

    def test_none_market_returns_2(self):
        pts, _ = ls._score_market({"market": None})
        assert pts == 2

    def test_empty_string_market_returns_2(self):
        pts, _ = ls._score_market({"market": ""})
        assert pts == 2


# ---------------------------------------------------------------------------
# Dimension: Enrichment depth
# ---------------------------------------------------------------------------


class TestDepthScoring:
    """_score_depth awards points based on which contact fields are populated."""

    def test_email_phone_ig_returns_5(self):
        pts, label = ls._score_depth({
            "contact_email": "a@b.com",
            "contact_phone": "555-1234",
            "company_ig_handle": "handle",
            "ig_handle": "",
        })
        assert pts == 5
        assert "email" in label.lower()
        assert "phone" in label.lower()
        assert "ig" in label.lower()

    def test_email_and_phone_only_returns_4(self):
        pts, label = ls._score_depth({
            "contact_email": "a@b.com",
            "contact_phone": "555-1234",
            "company_ig_handle": None,
            "ig_handle": None,
        })
        assert pts == 4

    def test_email_and_ig_only_returns_4(self):
        pts, label = ls._score_depth({
            "contact_email": "a@b.com",
            "contact_phone": None,
            "company_ig_handle": "someig",
            "ig_handle": "",
        })
        assert pts == 4

    def test_email_only_returns_3(self):
        pts, _ = ls._score_depth({
            "contact_email": "a@b.com",
            "contact_phone": None,
            "company_ig_handle": None,
            "ig_handle": None,
        })
        assert pts == 3

    def test_ig_only_returns_2(self):
        pts, _ = ls._score_depth({
            "contact_email": None,
            "contact_phone": None,
            "company_ig_handle": "onlyig",
            "ig_handle": "",
        })
        assert pts == 2

    def test_nothing_returns_1(self):
        pts, _ = ls._score_depth({
            "contact_email": None,
            "contact_phone": None,
            "company_ig_handle": None,
            "ig_handle": None,
        })
        assert pts == 1


# ---------------------------------------------------------------------------
# Confidence level
# ---------------------------------------------------------------------------


class TestConfidence:
    """_compute_confidence returns HIGH/MEDIUM/LOW based on data coverage."""

    def test_all_five_dimensions_high(self):
        lead = _make_lead(
            fleet_size=25,
            company_ig_handle="handle",
            company_ig_followers=20_000,
            company_website="https://example.com",
            market="Miami",
            contact_email="a@b.com",
        )
        assert ls._compute_confidence(lead) == "HIGH"

    def test_four_dimensions_medium(self):
        lead = _make_lead(
            fleet_size=25,
            company_ig_handle="handle",
            company_ig_followers=20_000,
            company_website="https://example.com",
            market="Miami",
            contact_email="",          # missing email -> 4 dims
        )
        assert ls._compute_confidence(lead) == "MEDIUM"

    def test_three_dimensions_medium(self):
        lead = _make_lead(
            fleet_size=5,
            company_ig_handle="handle",
            market="Phoenix",
            # no website, no email
        )
        assert ls._compute_confidence(lead) == "MEDIUM"

    def test_two_dimensions_low(self):
        lead = _make_lead(
            fleet_size=3,
            company_ig_handle="handle",
            # no website, no market, no email
        )
        assert ls._compute_confidence(lead) == "LOW"

    def test_zero_dimensions_low(self):
        lead = _make_lead()
        assert ls._compute_confidence(lead) == "LOW"


# ---------------------------------------------------------------------------
# Full weighted calculation
# ---------------------------------------------------------------------------


class TestWeightedCalculation:
    """
    Verify the full score_lead path produces the expected integer score
    for inputs with precisely known dimension scores.
    """

    def test_all_fives_score_5(self, patch_db):
        """
        Fleet>=20, IG>=10k, website+rating>=4.0, Miami, email+phone+IG
        -> all dims = 5 -> weighted avg = 5.0 -> score 5.
        """
        lead = _make_lead(
            fleet_size=43,
            company_ig_handle="elitecars",
            company_ig_followers=45_000,
            company_website="https://elite.com",
            company_google_rating=4.7,
            market="Miami",
            contact_email="hello@elite.com",
            contact_phone="305-555-0000",
        )
        patch_db["get_lead"].return_value = lead
        result = score_lead("lead_test_001")
        assert result["score"] == 5

    def test_all_ones_score_1(self, patch_db):
        """
        Bare minimum data on every dimension -> score 1.
        """
        lead = _make_lead()   # all fields None/empty
        patch_db["get_lead"].return_value = lead
        result = score_lead("lead_test_001")
        assert result["score"] == 1

    def test_known_mixed_calculation(self, patch_db):
        """
        Fleet 10-19 -> 4 pts (40%),  IG 5000-9999 -> 4 pts (20%),
        website only -> 3 pts (15%), Las Vegas -> 4 pts (15%),
        email only -> 3 pts (10%).

        Weighted: 4*0.4 + 4*0.2 + 3*0.15 + 4*0.15 + 3*0.10
                = 1.60 + 0.80 + 0.45 + 0.60 + 0.30
                = 3.75  -> round -> 4
        """
        lead = _make_lead(
            fleet_size=12,
            company_ig_handle="testco",
            company_ig_followers=7_500,
            company_website="https://testco.com",
            company_google_rating=None,
            market="Las Vegas",
            contact_email="ops@testco.com",
            contact_phone=None,
        )
        patch_db["get_lead"].return_value = lead
        result = score_lead("lead_test_001")
        assert result["score"] == 4

    def test_score_clamped_to_5(self, patch_db):
        """Score can never exceed 5 regardless of input."""
        lead = _make_lead(fleet_size=100, company_ig_handle="x",
                          company_ig_followers=1_000_000,
                          company_website="https://x.com",
                          company_google_rating=5.0,
                          market="Miami",
                          contact_email="a@x.com",
                          contact_phone="555-0000")
        patch_db["get_lead"].return_value = lead
        result = score_lead("lead_test_001")
        assert result["score"] <= 5

    def test_score_clamped_to_1(self, patch_db):
        """Score can never be below 1."""
        lead = _make_lead()
        patch_db["get_lead"].return_value = lead
        result = score_lead("lead_test_001")
        assert result["score"] >= 1


# ---------------------------------------------------------------------------
# Previous score preservation
# ---------------------------------------------------------------------------


class TestPreviousScorePreservation:
    """Verify the previous-score carry-forward logic."""

    def test_first_score_previous_score_is_none(self, patch_db):
        """A lead with no prior scoring returns previous_score=None."""
        lead = _make_lead(scoring_score=None, scoring_previous_score=None)
        patch_db["get_lead"].return_value = lead
        result = score_lead("lead_test_001")
        assert result["previous_score"] is None

    def test_rescore_carries_forward_old_score(self, patch_db):
        """
        When a lead has scoring_score=3 but no previous_score,
        the first rescore should set previous_score=3 and return it.
        """
        lead = _make_lead(scoring_score=3, scoring_previous_score=None)
        patch_db["get_lead"].return_value = lead
        result = score_lead("lead_test_001")
        assert result["previous_score"] == 3

    def test_second_rescore_preserves_oldest_score(self, patch_db):
        """
        When scoring_previous_score=2 already exists, subsequent rescoring
        must NOT overwrite it -- the oldest score (2) should be preserved.
        """
        lead = _make_lead(scoring_score=4, scoring_previous_score=2)
        patch_db["get_lead"].return_value = lead
        result = score_lead("lead_test_001")
        assert result["previous_score"] == 2

    def test_previous_score_not_written_when_none(self, patch_db):
        """
        On a brand-new scoring (no prior score), scoring_previous_score
        should not be written to the lead record at all.
        """
        lead = _make_lead(scoring_score=None, scoring_previous_score=None)
        patch_db["get_lead"].return_value = lead
        score_lead("lead_test_001")

        update_args = patch_db["update_lead"].call_args
        update_fields = update_args[0][1] if update_args[0] else update_args[1]["fields"]
        assert "scoring_previous_score" not in update_fields

    def test_previous_score_written_on_rescore(self, patch_db):
        """
        When scoring_score already exists, scoring_previous_score IS
        written to the lead record on rescore.
        """
        lead = _make_lead(scoring_score=2, scoring_previous_score=None)
        patch_db["get_lead"].return_value = lead
        score_lead("lead_test_001")

        update_args = patch_db["update_lead"].call_args
        update_fields = update_args[0][1] if update_args[0] else update_args[1]["fields"]
        assert "scoring_previous_score" in update_fields
        assert update_fields["scoring_previous_score"] == 2


# ---------------------------------------------------------------------------
# update_lead called with correct arguments
# ---------------------------------------------------------------------------


class TestUpdateLeadArgs:
    """Verify that update_lead is called once with all required fields."""

    def test_update_lead_called_once(self, patch_db):
        score_lead("lead_test_001")
        assert patch_db["update_lead"].call_count == 1

    def test_update_lead_receives_correct_lead_id(self, patch_db):
        score_lead("lead_test_001")
        args = patch_db["update_lead"].call_args[0]
        assert args[0] == "lead_test_001"

    def test_update_lead_contains_scoring_score(self, patch_db):
        score_lead("lead_test_001")
        fields = patch_db["update_lead"].call_args[0][1]
        assert "scoring_score" in fields

    def test_update_lead_contains_scoring_confidence(self, patch_db):
        score_lead("lead_test_001")
        fields = patch_db["update_lead"].call_args[0][1]
        assert "scoring_confidence" in fields

    def test_update_lead_contains_scoring_rationale(self, patch_db):
        score_lead("lead_test_001")
        fields = patch_db["update_lead"].call_args[0][1]
        assert "scoring_rationale" in fields

    def test_update_lead_contains_scoring_scored_at(self, patch_db):
        score_lead("lead_test_001")
        fields = patch_db["update_lead"].call_args[0][1]
        assert "scoring_scored_at" in fields

    def test_scoring_score_is_int_in_range(self, patch_db):
        score_lead("lead_test_001")
        fields = patch_db["update_lead"].call_args[0][1]
        assert isinstance(fields["scoring_score"], int)
        assert 1 <= fields["scoring_score"] <= 5

    def test_scoring_confidence_is_valid(self, patch_db):
        score_lead("lead_test_001")
        fields = patch_db["update_lead"].call_args[0][1]
        assert fields["scoring_confidence"] in {"HIGH", "MEDIUM", "LOW"}


# ---------------------------------------------------------------------------
# log_activity called with correct arguments
# ---------------------------------------------------------------------------


class TestLogActivityArgs:
    """Verify that log_activity is called with type='scoring' and agent='lead_scoring'."""

    def test_log_activity_called_once(self, patch_db):
        score_lead("lead_test_001")
        assert patch_db["log_activity"].call_count == 1

    def test_log_activity_type_is_scoring(self, patch_db):
        score_lead("lead_test_001")
        kwargs = patch_db["log_activity"].call_args.kwargs
        assert kwargs.get("type") == "scoring"

    def test_log_activity_agent_is_lead_scoring(self, patch_db):
        score_lead("lead_test_001")
        kwargs = patch_db["log_activity"].call_args.kwargs
        assert kwargs.get("agent") == "lead_scoring"

    def test_log_activity_lead_id_passed(self, patch_db):
        score_lead("lead_test_001")
        kwargs = patch_db["log_activity"].call_args.kwargs
        assert kwargs.get("lead_id") == "lead_test_001"

    def test_log_description_contains_lead_id(self, patch_db):
        score_lead("lead_test_001")
        kwargs = patch_db["log_activity"].call_args.kwargs
        assert "lead_test_001" in kwargs.get("description", "")


# ---------------------------------------------------------------------------
# Rationale format
# ---------------------------------------------------------------------------


class TestRationaleFormat:
    """Check that the rationale string is properly structured."""

    def test_rationale_contains_all_dimension_labels(self, patch_db):
        lead = _make_lead(
            fleet_size=25,
            company_ig_handle="exoticco",
            company_ig_followers=15_000,
            company_website="https://exotic.com",
            company_google_rating=4.7,
            market="Miami",
            contact_email="hi@exotic.com",
            contact_phone="305-555-1234",
        )
        patch_db["get_lead"].return_value = lead
        result = score_lead("lead_test_001")
        rationale = result["rationale"]
        for keyword in ("Fleet:", "IG:", "Web:", "Market:", "Depth:", "Score:"):
            assert keyword in rationale, f"Missing keyword: {keyword}"

    def test_rationale_uses_double_hyphen_not_em_dash(self, patch_db):
        result = score_lead("lead_test_001")
        assert "\u2014" not in result["rationale"], "Rationale must not contain em-dashes"
        assert " -- " in result["rationale"]

    def test_rationale_ends_with_confidence(self, patch_db):
        lead = _make_lead(
            fleet_size=25,
            company_ig_handle="exoticco",
            company_ig_followers=15_000,
            company_website="https://exotic.com",
            company_google_rating=4.7,
            market="Miami",
            contact_email="hi@exotic.com",
            contact_phone="305-555-1234",
        )
        patch_db["get_lead"].return_value = lead
        result = score_lead("lead_test_001")
        assert result["rationale"].endswith(f"Score: {result['score']} ({result['confidence']})")

    def test_full_rationale_example(self, patch_db):
        """
        Exact rationale for the example in the spec:
        Fleet: 43 vehicles (5pts, 40%), IG: 45,000 followers (5pts, 20%),
        Web: website+4.7 rating (5pts, 15%), Market: Miami (5pts, 15%),
        Depth: email+phone+IG (5pts, 10%) -- Score: 5 (HIGH)
        """
        lead = _make_lead(
            fleet_size=43,
            company_ig_handle="elitecars",
            company_ig_followers=45_000,
            company_website="https://elite.com",
            company_google_rating=4.7,
            market="Miami",
            contact_email="hello@elite.com",
            contact_phone="305-555-0000",
        )
        patch_db["get_lead"].return_value = lead
        result = score_lead("lead_test_001")
        r = result["rationale"]
        assert "43 vehicles" in r
        assert "45,000 followers" in r
        assert "4.7" in r
        assert "Miami" in r
        assert "email+phone+IG" in r
        assert "Score: 5 (HIGH)" in r


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    def test_unknown_lead_raises_value_error(self, patch_db):
        """score_lead raises ValueError when the lead does not exist."""
        patch_db["get_lead"].return_value = None
        with pytest.raises(ValueError, match="lead_missing_001"):
            score_lead("lead_missing_001")

    def test_unknown_lead_does_not_call_update(self, patch_db):
        patch_db["get_lead"].return_value = None
        with pytest.raises(ValueError):
            score_lead("lead_missing_001")
        patch_db["update_lead"].assert_not_called()

    def test_unknown_lead_does_not_call_log(self, patch_db):
        patch_db["get_lead"].return_value = None
        with pytest.raises(ValueError):
            score_lead("lead_missing_001")
        patch_db["log_activity"].assert_not_called()
