from __future__ import annotations

import json
import urllib.error
import urllib.request

from src.connectors.homestocompare_mapper import build_h2c_public_comparison_payload
from src.models.schemas import Listing


class HomesToComparePublicConnector:
    """Public H2C comparison creator.

    This connector intentionally does not use the legacy house-hunt service key.
    If H2C requires an existing visitor session, pass the session cookie value.
    """

    def __init__(
        self,
        base_url: str = "https://homestocompare.com",
        *,
        visitor_session: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.visitor_session = visitor_session

    def create_comparison(
        self,
        listings: list[Listing],
        comparison: dict[str, object] | None = None,
    ) -> dict[str, object]:
        payload = build_h2c_public_comparison_payload(listings, comparison=comparison)
        headers = {"content-type": "application/json"}
        if self.visitor_session:
            headers["cookie"] = f"h2c_visitor_session={self.visitor_session}"
        request = urllib.request.Request(
            f"{self.base_url}/api/create-comparison",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"H2C comparison creation failed with HTTP {exc.code}: {body}") from exc

        if not isinstance(raw, dict):
            raise RuntimeError("H2C comparison creation returned a non-object response.")
        if raw.get("success") is False:
            raise RuntimeError(str(raw.get("error") or "H2C comparison creation failed."))

        comparison_id = str(raw.get("comparison_id") or raw.get("suid_code") or "")
        overview_url = f"{self.base_url}/pc/{comparison_id}/overview" if comparison_id else None
        photos_url = f"{self.base_url}/pc/{comparison_id}/photos" if comparison_id else None
        return {
            "status": "published",
            "comparison_id": comparison_id or None,
            "overview_url": overview_url,
            "photos_url": photos_url,
            "raw_response": raw,
        }
