from __future__ import annotations

from typing import Protocol

from src.models.schemas import (
    AreaData,
    BuyerProfile,
    CommuteEstimate,
    ExportOptions,
    ExportPayload,
    ExportResult,
    ImageAnalysis,
    Listing,
    Session,
)


class ListingProvider(Protocol):
    name: str

    def search(self, profile: BuyerProfile, limit: int = 200) -> list[Listing]:
        ...


class CommuteProvider(Protocol):
    name: str

    def estimate(
        self,
        listing: Listing,
        destination: str,
        mode: str | None = None,
        assumptions: dict | None = None,
    ) -> CommuteEstimate:
        ...


class AreaDataProvider(Protocol):
    name: str
    categories: set[str]

    def supports(self, listing: Listing, jurisdiction: str | None = None) -> bool:
        ...

    def fetch(self, listing: Listing, categories: list[str] | None = None) -> AreaData:
        ...


class VisionAnalyzer(Protocol):
    name: str

    def analyse(
        self,
        listing: Listing,
        image_urls: list[str] | None = None,
        max_images: int = 6,
    ) -> ImageAnalysis:
        ...


class SessionStore(Protocol):
    def load(self, session_id: str) -> Session | None:
        ...

    def save(self, session: Session) -> Session:
        ...

    def list_sessions(self) -> list[Session]:
        ...

    def delete(self, session_id: str) -> bool:
        ...


class Exporter(Protocol):
    format: str

    def export(self, payload: ExportPayload, options: ExportOptions) -> ExportResult:
        ...
