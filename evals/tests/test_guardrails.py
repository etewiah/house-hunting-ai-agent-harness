from src.harness.policies import advice_boundary_notice, check_guardrails
from src.skills.offer_brief import generate_offer_brief
from src.connectors.mock_listing_api import MockListingApi


def test_boundary_notice_names_prohibited_advice_categories():
    notice = advice_boundary_notice().lower()
    assert "legal" in notice
    assert "mortgage" in notice
    assert "inspection" in notice


def test_offer_brief_contains_boundary():
    listing = MockListingApi("evals/datasets/listings_small.jsonl").get_listing("L001")
    assert listing is not None
    brief = generate_offer_brief(listing)
    assert "Do not treat this as" in brief
    assert "legal" in brief.lower()
    assert "mortgage" in brief.lower()
    assert check_guardrails("This is legal advice") == ["legal advice"]
