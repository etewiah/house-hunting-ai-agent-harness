# Connectors

Connectors should keep external systems out of core skills.

## Included

- `local_csv.py`: placeholder for CSV listing sources
- `mock_listing_api.py`: loads JSONL fixtures
- `mcp_client.py`: minimal MCP-style adapter stub

## Connector Contract

A listing connector should expose:

- `search(profile) -> list[Listing]`
- `get_listing(listing_id) -> Listing | None`

Real providers should preserve source labels and raw payloads for auditability.

