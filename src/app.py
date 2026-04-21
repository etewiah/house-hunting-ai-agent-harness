from __future__ import annotations

import os

from src.config import load_config
from src.connectors.mock_listing_api import MockListingApi
from src.harness.orchestrator import HouseHuntOrchestrator


def build_app() -> HouseHuntOrchestrator:
    config = load_config()
    listings = MockListingApi(config.listings_data_path)
    llm = _try_load_llm()
    return HouseHuntOrchestrator(listings=listings, trace_dir=config.trace_output_dir, llm=llm)


def _try_load_llm():
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None
    try:
        from src.connectors.anthropic_adapter import AnthropicAdapter
        return AnthropicAdapter()
    except Exception:
        return None
