import os

import google.auth
import google.auth.transport.requests
import google.oauth2.id_token
import httpx
import requests

from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from gateway.policy import is_devops_tool_allowed


DEVOPS_MCP_URL = os.environ.get(
    "DEVOPS_MCP_URL"
)

GATEWAY_SERVICE_ACCOUNT = os.environ.get(
    "GATEWAY_SERVICE_ACCOUNT"
)


class DevOpsMCPGateway:
    """
    Controlled wrapper around the private DevOps MCP Cloud Run service.

    Authentication:
    - Local development: ADC user credentials + IAM Credentials API
    - Cloud Run: attached Gateway service account

    Responsibilities:
    - Obtain a Google-signed identity token for the DevOps Cloud Run service
    - Enforce the Gateway DevOps tool policy
    - Verify the requested tool exists on the remote MCP server
    - Execute only approved tools
    """

    def _get_identity_token(self) -> str:
        """
        Obtain an ID token whose audience is the DevOps Cloud Run service.
        """

        audience = DEVOPS_MCP_URL.removesuffix("/mcp")

        # Cloud Run: use the attached Gateway service account.
        if os.environ.get("K_SERVICE"):
            request = google.auth.transport.requests.Request()

            return google.oauth2.id_token.fetch_id_token(
                request,
                audience,
            )

        # Local development:
        # use the authenticated user's ADC access token to call
        # IAM Credentials generateIdToken for the Gateway service account.
        credentials, _ = google.auth.default()

        request = google.auth.transport.requests.Request()
        credentials.refresh(request)

        url = (
            "https://iamcredentials.googleapis.com/v1/projects/-"
            f"/serviceAccounts/{GATEWAY_SERVICE_ACCOUNT}:generateIdToken"
        )

        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {credentials.token}",
                "Content-Type": "application/json",
            },
            json={
                "audience": audience,
                "includeEmail": True,
            },
            timeout=30,
        )

        response.raise_for_status()

        return response.json()["token"]

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict,
    ):
        """
        Execute an approved DevOps MCP tool.
        """

        if not is_devops_tool_allowed(tool_name):
            raise PermissionError(
                f"DevOps MCP tool '{tool_name}' is not allowed "
                "by the Gateway policy"
            )

        token = self._get_identity_token()

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json, text/event-stream",
        }

        async with httpx.AsyncClient(
            headers=headers,
            timeout=30.0,
        ) as http_client:

            transport = streamable_http_client(
                DEVOPS_MCP_URL,
                http_client=http_client,
            )

            async with Client(
                transport,
                mode="auto",
            ) as client:

                tools = await client.list_tools()

                available_tools = {
                    tool.name for tool in tools.tools
                }

                if tool_name not in available_tools:
                    raise ValueError(
                        f"DevOps MCP server does not expose "
                        f"tool '{tool_name}'"
                    )

                return await client.call_tool(
                    tool_name,
                    arguments=arguments,
                )
