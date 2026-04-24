from src.skills.listing_input import listing_from_dict


def test_listing_from_dict_coerces_common_browser_string_fields():
    listing = listing_from_dict(
        {
            "id": "listing-1",
            "title": "Example home",
            "price": "£250,000",
            "bedrooms": "3 bedrooms",
            "bathrooms": "1.5 baths",
            "location": "Birmingham",
            "commute_minutes": "22 min",
            "features": "parking",
            "description": "Near station",
            "source_url": "https://example.com/listing",
            "image_urls": "https://example.com/image.jpg",
            "external_refs": {"extraction_quality_score": 80},
        }
    )

    assert listing.price == 250000
    assert listing.bedrooms == 3
    assert listing.bathrooms == 1
    assert listing.commute_minutes == 22
    assert listing.features == ["parking"]
    assert listing.image_urls == ["https://example.com/image.jpg"]
    assert listing.external_refs["extraction_quality_score"] == 80


def test_listing_from_dict_handles_missing_or_invalid_collection_fields():
    listing = listing_from_dict(
        {
            "id": "listing-2",
            "title": "Example home",
            "price": None,
            "bedrooms": None,
            "bathrooms": None,
            "location": "Birmingham",
            "commute_minutes": "",
            "features": None,
            "description": "",
            "source_url": "https://example.com/listing",
            "image_urls": None,
            "external_refs": "not-a-dict",
        }
    )

    assert listing.price == 0
    assert listing.bedrooms == 0
    assert listing.bathrooms == 0
    assert listing.commute_minutes is None
    assert listing.features == []
    assert listing.image_urls == []
    assert listing.external_refs == {}


def test_listing_from_dict_coerces_area_data_evidence():
    listing = listing_from_dict(
        {
            "id": "listing-3",
            "title": "Example with area context",
            "price": "£300,000",
            "bedrooms": "2",
            "bathrooms": "1",
            "location": "Birmingham",
            "commute_minutes": "20",
            "features": ["parking"],
            "description": "",
            "source_url": "https://example.com/listing",
            "area_data": {
                "evidence": [
                    {
                        "category": "schools",
                        "summary": "Two schools rated good nearby",
                        "source_name": "Ofsted",
                        "source": "listing_provided",
                        "retrieved_at": "2026-04-23T12:00:00Z",
                    }
                ],
                "warnings": ["school distance estimated"],
            },
        }
    )

    assert listing.area_data is not None
    assert listing.area_data.listing_id == "listing-3"
    assert len(listing.area_data.evidence) == 1
    assert listing.area_data.evidence[0].category == "schools"
    assert listing.area_data.warnings == ["school distance estimated"]


def test_listing_from_dict_coerces_decision_details():
    listing = listing_from_dict(
        {
            "id": "listing-4",
            "title": "Leasehold flat",
            "price": "£300,000",
            "bedrooms": "2",
            "bathrooms": "1",
            "location": "Birmingham",
            "commute_minutes": "20",
            "features": ["parking"],
            "description": "",
            "source_url": "https://example.com/listing",
            "decision_details": {
                "tenure": {"value": "leasehold", "source": "listing_provided"},
                "lease_years_remaining": {"value": 82, "source": "listing_provided"},
                "service_charge_annual": {"value": 3600, "source": "listing_provided"},
                "epc_rating": "C",
                "notes": ["check lease pack"],
            },
        }
    )

    assert listing.decision_details is not None
    assert listing.decision_details.tenure.value == "leasehold"
    assert listing.decision_details.lease_years_remaining.value == 82
    assert listing.decision_details.epc_rating.value == "C"
    assert listing.decision_details.notes == ["check lease pack"]
