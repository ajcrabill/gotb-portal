"""Content pipeline tests — Phase 0 acceptance gate.

These tests run in CI on every push. The pipeline is the most critical
quality gate in the system; every ESB content string passes through it.
"""
import pytest

from esb.pipeline.antislop import scan, clean, SANCTIONED_PHRASES
from esb.pipeline.quality import ContentClass, Verdict, Stage2UnavailableError
from esb.pipeline.service import check, PipelineResult


# ── Stage 1: antislop ────────────────────────────────────────────────────────

class TestAntislop:
    def test_clean_text_scores_100(self):
        result = scan("The board has set clear goals for student learning.")
        assert result["score"] == 100
        assert result["clean"] is True

    def test_tier1_term_penalized(self):
        result = scan("We need to delve into this topic.")
        assert result["score"] < 100
        assert any(b["term"] == "delve" for b in result["banned"])

    def test_ip_violation_coach_client_facing(self):
        result = scan("Contact your ESB coach for more information.", is_client_facing=True)
        assert result["has_ip_violation"] is True
        assert result["score"] < 100

    def test_coach_ok_not_client_facing(self):
        result = scan("The coaching manager will review this.", is_client_facing=False)
        assert result["has_ip_violation"] is False

    def test_sofg_always_blocked(self):
        result = scan("This approach uses SOFG principles.", is_client_facing=False)
        assert result["has_ip_violation"] is True

    def test_lsg_always_blocked(self):
        result = scan("Drawing from Lone Star Governance methodology.", is_client_facing=True)
        assert result["has_ip_violation"] is True

    def test_sanctioned_phrases_not_flagged(self):
        text = "This is an indicative, self-scored assessment."
        result = scan(text, is_client_facing=True)
        assert result["has_ip_violation"] is False
        # "indicative" appears in TIER2 but is sanctioned — should not be penalized
        assert result["clean"] is True or result["score"] >= 90

    def test_practice_names_not_flagged(self):
        result = scan("Focus Mindset, Clarify Priorities, Monitor Progress")
        assert result["has_ip_violation"] is False

    def test_band_labels_not_flagged(self):
        result = scan("Beginning Clarity, Emerging Focus, Highly Effective Focus")
        assert result["has_ip_violation"] is False

    def test_credential_name_not_flagged(self):
        result = scan("Certified Great on Their Behalf Practitioner", is_client_facing=True)
        assert result["has_ip_violation"] is False

    def test_clean_preserves_meaning(self):
        text = "The board has  goals..."
        fixed, findings = clean(text)
        # collapses double space, normalizes ellipsis
        assert "  " not in fixed
        assert "..." not in fixed or "…" in fixed

    def test_ruleset_version_stamped(self):
        result = scan("Clean text here.", ruleset_version="esb-v2-test")
        assert result["ruleset_version"] == "esb-v2-test"

    def test_bucket_ceilings_sum_to_100(self):
        from esb.models.scoring import PRACTICE_CEILINGS, TOTAL_CEILING
        assert sum(PRACTICE_CEILINGS.values()) == TOTAL_CEILING

    def test_band_scores_cover_all_practices(self):
        from esb.models.scoring import PRACTICE_KEYS, BAND_LABELS
        assert set(BAND_LABELS.keys()) == set(PRACTICE_KEYS)

    def test_each_practice_has_four_bands(self):
        from esb.models.scoring import BAND_LABELS
        for practice, bands in BAND_LABELS.items():
            assert len(bands) == 4, f"{practice} must have exactly 4 band labels"

    def test_beginning_bands_are_practice_specific(self):
        from esb.models.scoring import BAND_LABELS
        beginning_labels = {practice: bands[0] for practice, bands in BAND_LABELS.items()}
        # All 5 beginning labels must be distinct
        assert len(set(beginning_labels.values())) == 5

    def test_upper_bands_use_focus_frame(self):
        from esb.models.scoring import BAND_LABELS
        for practice, bands in BAND_LABELS.items():
            assert "Focus" in bands[1], f"{practice} Band 2 must contain 'Focus'"
            assert "Focus" in bands[2], f"{practice} Band 3 must contain 'Focus'"
            assert "Focus" in bands[3], f"{practice} Band 4 must contain 'Focus'"


# ── Stage 2: quality reviewer ─────────────────────────────────────────────────

class TestQualityReviewer:
    def test_no_llm_returns_ok(self):
        from esb.pipeline.quality import review_content
        verdict = review_content(None, content="Short.", content_class=ContentClass.internal)
        assert verdict.ok is True

    def test_fail_closed_class_raises_when_unavailable(self):
        from esb.pipeline.quality import review_content
        with pytest.raises(Stage2UnavailableError):
            review_content(
                None,
                content="This instrument is validated by research.",
                content_class=ContentClass.validation_status,
            )

    def test_fail_open_class_skips_gracefully_when_unavailable(self):
        from esb.pipeline.quality import review_content
        verdict = review_content(
            None,
            content="Some client-facing copy here.",
            content_class=ContentClass.client_facing,
        )
        assert verdict.stage2_skipped is True
        assert verdict.block is False


# ── Pipeline service ──────────────────────────────────────────────────────────

class TestPipelineService:
    def test_ip_violation_hard_blocks(self):
        result = check(
            "This uses SOFG methodology.",
            content_class=ContentClass.client_facing,
            llm_provider=None,
        )
        assert result.passed is False
        assert result.held is True
        assert "IP violation" in result.hold_reason

    def test_clean_content_passes_without_llm(self):
        result = check(
            "The board has set clear goals for student achievement.",
            content_class=ContentClass.internal,
            llm_provider=None,
        )
        assert result.passed is True
        assert result.stage1_score == 100

    def test_validation_status_held_without_stage2(self):
        result = check(
            "This instrument is validated.",
            content_class=ContentClass.validation_status,
            llm_provider=None,
        )
        assert result.passed is False
        assert result.held is True
