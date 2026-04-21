from src.config import load_config
from src.connectors.mock_listing_api import MockListingApi
from src.harness.orchestrator import HouseHuntOrchestrator


def build_app() -> HouseHuntOrchestrator:
    config = load_config()
    listings = MockListingApi(config.listings_data_path)
    return HouseHuntOrchestrator(listings=listings, trace_dir=config.trace_output_dir)

