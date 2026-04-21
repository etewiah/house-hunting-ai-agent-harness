from src.harness.policies import (
    GuardrailResult,
    advice_boundary_notice,
    check_generated_recommendation_language,
    check_guardrails,
    check_output_guardrails,
)
from src.models.schemas import Listing
from src.skills.offer_brief import generate_offer_brief


def test_boundary_notice_names_prohibited_advice_categories():
    notice = advice_boundary_notice().lower()
    assert "legal" in notice
    assert "mortgage" in notice
    assert "inspection" in notice


def test_offer_brief_contains_boundary():
    listing = Listing(
        id="L001",
        title="Quiet Garden Terrace",
        price=675_000,
        bedrooms=3,
        bathrooms=1,
        location="Walthamstow, London",
        commute_minutes=38,
        features=["garden", "quiet street"],
        description="",
        source_url="https://example.com",
    )
    brief = generate_offer_brief(listing)
    assert "Do not treat this as" in brief
    assert "legal" in brief.lower()
    assert "mortgage" in brief.lower()
    assert check_guardrails("This is legal advice") == ["legal advice"]


def test_fair_housing_terms_detected_in_generated_recommendations():
    violations = check_generated_recommendation_language(
        "This is a safe neighbourhood with good schools nearby."
    )
    assert "safe neighbourhood" in violations
    assert "good schools nearby" in violations


def test_structured_guardrail_result_passes_for_boundary_output():
    result = check_output_guardrails(advice_boundary_notice(), require_boundary_notice=True)
    assert result == GuardrailResult(passed=True)


def test_structured_guardrail_result_fails_missing_boundary():
    result = check_output_guardrails("Speak to a professional.", require_boundary_notice=True)
    assert not result.passed
    assert "missing advice boundary notice" in result.violations


def test_structured_guardrail_result_requires_source_label():
    result = check_output_guardrails("Matched: garden.", require_source_label=True)
    assert not result.passed
    assert "missing source label" in result.violations


def test_structured_guardrail_result_warns_on_sensitive_recommendations():
    result = check_output_guardrails("This is a family-friendly area.")
    assert result.passed
    assert "sensitive recommendation language: family-friendly area" in result.warnings
