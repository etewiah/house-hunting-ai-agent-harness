from __future__ import annotations


class McpClient:
    """Placeholder for MCP-style tool/resource integration."""

    def __init__(self, server_name: str) -> None:
        self.server_name = server_name

    def list_tools(self) -> list[str]:
        return []

    def call_tool(self, name: str, payload: dict[str, object]) -> dict[str, object]:
        return {
            "server": self.server_name,
            "tool": name,
            "payload": payload,
            "status": "not_configured",
        }
