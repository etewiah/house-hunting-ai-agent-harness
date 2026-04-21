import pytest
from src.skills.intake import parse_buyer_brief


@pytest.mark.parametrize("brief, expected_location", [
    ("3-bed near Manchester Piccadilly, budget £350k", "Manchester Piccadilly"),
    ("2-bed flat, max 20 min commute to London Bridge, under £500k", "London Bridge"),
    ("somewhere quiet in Leeds with a garden, 4 beds", "Leeds"),
    ("I want a 3-bed within 45 minutes of King's Cross, budget £700k", "King's Cross"),
    ("3-bed house in Bristol, budget £400k", "Bristol"),
])
def test_location_extraction(brief, expected_location):
    profile = parse_buyer_brief(brief)
    assert profile.location_query == expected_location


@pytest.mark.parametrize("brief, expected_budget", [
    ("budget £350k", 350_000),
    ("under £500k", 500_000),
    ("budget £1200k", 1_200_000),
    ("$400k budget", 400_000),
])
def test_budget_extraction(brief, expected_budget):
    profile = parse_buyer_brief(brief)
    assert profile.max_budget == expected_budget


@pytest.mark.parametrize("brief, expected_beds", [
    ("3-bed house", 3),
    ("2-bed flat", 2),
    ("4 bed semi", 4),
    ("1-bedroom flat", 1),
])
def test_bedroom_extraction(brief, expected_beds):
    profile = parse_buyer_brief(brief)
    assert profile.min_bedrooms == expected_beds


@pytest.mark.parametrize("brief, expected_commute", [
    ("max 30 min commute", 30),
    ("within 45 minutes of King's Cross", 45),
    ("20 minute commute", 20),
    ("no commute mentioned", None),
])
def test_commute_extraction(brief, expected_commute):
    profile = parse_buyer_brief(brief)
    assert profile.max_commute_minutes == expected_commute


@pytest.mark.parametrize("brief, expected_must_haves", [
    ("need a garden and walkable area", ["garden", "walkable"]),
    ("quiet street, good schools", ["quiet", "schools"]),
    ("parking essential", ["parking"]),
    ("no special requirements", []),
])
def test_must_haves_extraction(brief, expected_must_haves):
    profile = parse_buyer_brief(brief)
    assert sorted(profile.must_haves) == sorted(expected_must_haves)


def test_full_brief_parses_correctly():
    brief = "3-bed house near Manchester Piccadilly, budget £350k, need a garden, max 30 min commute, quiet street preferred"
    profile = parse_buyer_brief(brief)
    assert profile.location_query == "Manchester Piccadilly"
    assert profile.max_budget == 350_000
    assert profile.min_bedrooms == 3
    assert profile.max_commute_minutes == 30
    assert "garden" in profile.must_haves
    assert "quiet" in profile.must_haves
