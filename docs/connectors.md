# Connectors

Connectors should keep external systems out of core skills.

## Included

- `homestocompare_connector.py`: HomesToCompare listing search and comparison adapters
- `local_csv.py`: CSV listing source adapter
- `mcp_client.py`: minimal MCP-style adapter stub

## Connector Contract

A listing connector should expose:

- `search(profile) -> list[Listing]`

Real providers should preserve source labels and raw payloads for auditability.
