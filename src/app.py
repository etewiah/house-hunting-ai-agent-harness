from __future__ import annotations

from src.config import load_config
from src.connectors.homestocompare_connector import H2CListingConnector, HomesToCompareConnector
from src.connectors.local_csv import LocalCsvListingConnector
from src.connectors.provider_factory import load_llm
from src.harness.orchestrator import HouseHuntOrchestrator
from src.models.capabilities import ListingProvider


def build_app() -> HouseHuntOrchestrator:
    config = load_config()
    listings = _load_listing_provider(config)
    h2c_connector = (
        HomesToCompareConnector(config.h2c_base_url, config.h2c_service_key)
        if config.h2c_service_key
        else None
    )
    llm = load_llm()
    return HouseHuntOrchestrator(
        listings=listings,
        trace_dir=config.trace_output_dir,
        h2c_connector=h2c_connector,
        llm=llm,
    )


def _load_listing_provider(config) -> ListingProvider:
    if config.h2c_read_key:
        return H2CListingConnector(config.h2c_base_url, config.h2c_read_key)

    if config.listings_csv_path:
        return LocalCsvListingConnector(config.listings_csv_path)

    raise RuntimeError(
        "No listing provider configured. Set H2C_READ_KEY for HomesToCompare search "
        "or LISTINGS_CSV_PATH to an explicit CSV export."
    )
