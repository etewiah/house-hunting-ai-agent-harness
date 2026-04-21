import pytest
from src.models.schemas import BuyerProfile, Listing
from src.skills.listing_search import filter_by_location, filter_listings


def _make_listing(id: str, location: str, price: int = 400_000, bedrooms: int = 3) -> Listing:
    return Listing(
        id=id, title=id, price=price, bedrooms=bedrooms, bathrooms=1,
        location=location, commute_minutes=20, features=[], description="", source_url="",
    )


LONDON = [
    _make_listing("L1", "Walthamstow, London"),
    _make_listing("L2", "Finsbury Park, London"),
]
MANCHESTER = [
    _make_listing("M1", "Chorlton, Manchester"),
    _make_listing("M2", "Didsbury, Manchester"),
]
BRISTOL = [_make_listing("B1", "Clifton, Bristol")]
ALL = LONDON + MANCHESTER + BRISTOL


@pytest.mark.parametrize("query, expected_ids", [
    ("Manchester Piccadilly", ["M1", "M2"]),
    ("near Bristol", ["B1"]),
    ("Leeds City Station", []),          # no Leeds listings → warning + fallback
    ("King's Cross", ["L1", "L2"]),
    ("commute to London Bridge", ["L1", "L2"]),
])
def test_location_filter_returns_correct_city(query, expected_ids):
    results, warnings = filter_by_location(query, ALL)
    result_ids = [listing.id for listing in results]
    if expected_ids:
        assert sorted(result_ids) == sorted(expected_ids)
    else:
        # fallback: returns all when city not in dataset
        assert len(results) == len(ALL)
        assert warnings


def test_unknown_location_returns_all_without_warning():
    results, warnings = filter_by_location("unknown", ALL)
    assert len(results) == len(ALL)
    assert not warnings


def test_location_mismatch_produces_warning():
    _, warnings = filter_by_location("Leeds City Station", ALL)
    assert warnings
    assert "Leeds" in warnings[0]


def test_filter_listings_price_and_bedroom_bounds():
    profile = BuyerProfile(
        location_query="unknown", max_budget=350_000, min_bedrooms=3,
        must_haves=[], nice_to_haves=[],
    )
    listings = [
        _make_listing("cheap", "Anywhere", price=300_000, bedrooms=3),
        _make_listing("overbudget", "Anywhere", price=500_000, bedrooms=3),
        _make_listing("toosmall", "Anywhere", price=300_000, bedrooms=1),
        _make_listing("borderline", "Anywhere", price=385_000, bedrooms=3),  # within 110%
    ]
    results = filter_listings(profile, listings)
    ids = [listing.id for listing in results]
    assert "cheap" in ids
    assert "borderline" in ids
    assert "overbudget" not in ids
    assert "toosmall" not in ids
