import os

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from gateway.policy import is_github_tool_allowed


class GitHubMCPGateway:
    """
    Controlled wrapper around the remote GitHub MCP server.

    Responsibilities:
    - Authenticate with GitHub MCP
    - Enforce the Gateway tool allowlist
    - Execute only approved MCP tools
    """

    def __init__(self):
        self.token = os.environ.get("GITHUB_TOKEN")
        self.mcp_url = os.environ.get(
            "GITHUB_MCP_URL", 
            "https://api.githubcopilot.com/mcp/"
        )

        if not self.token:
            raise RuntimeError("GITHUB_TOKEN is not set")

        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json, text/event-stream",
        }

    async def call_tool(self, tool_name: str, arguments: dict):
        """
        Execute an approved GitHub MCP tool.

        Any tool not explicitly present in the Gateway policy
        is rejected before it reaches GitHub MCP.
        """

        # -----------------------------------------------------
        # 1. Policy check
        # -----------------------------------------------------
        if not is_github_tool_allowed(tool_name):
            raise PermissionError(
                f"GitHub MCP tool '{tool_name}' is not allowed "
                "by the Gateway policy"
            )

        # -----------------------------------------------------
        # 2. Create authenticated HTTP client
        # -----------------------------------------------------
        async with httpx2.AsyncClient(
            headers=self.headers,
            timeout=30.0,
        ) as http_client:

            # -------------------------------------------------
            # 3. Create MCP transport using env-configured URL
            # -------------------------------------------------
            transport = streamable_http_client(
                self.mcp_url,
                http_client=http_client,
            )

            # -------------------------------------------------
            # 4. Create MCP client
            # -------------------------------------------------
            async with Client(
                transport,
                mode="auto",
            ) as client:

                # ---------------------------------------------
                # 5. Verify requested tool exists on server
                # ---------------------------------------------
                tools = await client.list_tools()

                available_tools = {
                    tool.name for tool in tools.tools
                }

                if tool_name not in available_tools:
                    raise ValueError(
                        f"GitHub MCP server does not expose "
                        f"tool '{tool_name}'"
                    )

                # ---------------------------------------------
                # 6. Execute the approved MCP tool
                # ---------------------------------------------
                result = await client.call_tool(
                    tool_name,
                    arguments=arguments,
                )

                return result