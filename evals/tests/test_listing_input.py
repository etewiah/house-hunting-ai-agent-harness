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
