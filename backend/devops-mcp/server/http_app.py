import os
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from server.app import mcp

# Read allowed host from environment variable (default fallback for local/testing)
allowed_host = os.environ.get("ALLOWED_HOST")

mcp.settings.transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=True if allowed_host != "*" else False,
    allowed_hosts=[allowed_host] if allowed_host != "*" else ["*"],
)

app = mcp.streamable_http_app()