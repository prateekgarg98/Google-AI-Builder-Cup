import os
import base64
import httpx
import json

# ============================================================
# Atlassian Gateway Adapter
# ============================================================

class AtlassianMCPGateway:
    def __init__(self):
        self.base_url = os.environ.get("JIRA_URL").strip().rstrip("/")
        self.email = os.environ.get("ATLASSIAN_EMAIL").strip()
        self.token = os.environ.get("ATLASSIAN_TOKEN")

        if not self.token:
            raise RuntimeError("ATLASSIAN_TOKEN is not set")

        # # --- PHASE 2 IMPLEMENTATION: Secure Proxy for Decisions ---
        # # The Frontend hits the agent backend, which securely forwards the HUMAN's token 
        # # directly to the gateway for validation.
        #
        # self.rovo_url = os.environ.get("ATLASSIAN_ROVO_URL").strip().rstrip("/")
        # self.rovo_headers = {
        #     "Authorization": f"Bearer {self.token}",
        #     "Accept": "application/json, text/event-stream",
        # }

        # --- HACKATHON MVP IMPLEMENTATION: Proxy for Decisions ---
        # Direct Jira REST API v3 implementation (Zero Rovo credits consumed, stable HTTP)
        raw_creds = f"{self.email}:{self.token}".encode("utf-8")
        encoded_creds = base64.b64encode(raw_creds).decode("utf-8")
        
        self.headers = {
            "Authorization": f"Basic {encoded_creds}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def list_tools(self):
        return [
            {"name": "searchJiraIssuesUsingJql", "description": "Search Jira issues using JQL"},
            {"name": "getJiraIssue", "description": "Get Jira issue by key"},
            {"name": "updateJiraIssue", "description": "Update Jira issue by key"},
            {"name": "createJiraIssue", "description": "Create a new Jira issue"}
        ]

    async def call_tool(self, tool_name: str, arguments: dict):
        args = dict(arguments or {})
        
        # # --- PHASE 2 IMPLEMENTATION: Secure Proxy for Decisions ---
        # async with httpx.AsyncClient(headers=self.rovo_headers, timeout=30.0) as http_client:
        #     from mcp import Client
        #     from mcp.client.streamable_http import streamable_http_client
        #     
        #     transport = streamable_http_client(
        #         self.rovo_url,
        #         http_client=http_client,
        #     )
        #     async with Client(transport, mode="auto") as client:
        #         result = await client.call_tool(
        #             tool_name,
        #             arguments=arguments,
        #         )
        #         return result

        # --- HACKATHON MVP IMPLEMENTATION: Proxy for Decisions ---
        async with httpx.AsyncClient(headers=self.headers, timeout=30.0) as client:
            
            # 1. Search JQL
            if tool_name in ("searchJiraIssuesUsingJql", "search_issues"):
                jql = args.get("jql") or "created >= -90d ORDER BY created DESC"
                resp = await client.post(
                    f"{self.base_url}/rest/api/3/search/jql",
                    json={"jql": jql, "maxResults": 10, "fields": ["summary", "status", "issuetype", "created", "description"]}
                )
                resp.raise_for_status()
                data = resp.json()
                
                class ResultObj:
                    def __init__(self, text):
                        self.content = [type('obj', (object,), {'text': text})]
                return ResultObj(json.dumps(data))

            # 2. Get Issue
            elif tool_name in ("getJiraIssue", "get_issue"):
                issue_key = args.get("issueIdOrKey") or args.get("issue_key")
                resp = await client.get(f"{self.base_url}/rest/api/3/issue/{issue_key}")
                resp.raise_for_status()
                data = resp.json()
                
                class ResultObj:
                    def __init__(self, text):
                        self.content = [type('obj', (object,), {'text': text})]
                return ResultObj(json.dumps(data))

            # 3. Update Issue
            elif tool_name in ("updateJiraIssue", "update_issue"):
                issue_key = args.get("issueIdOrKey") or args.get("issue_key")
                payload = args.get("payload", {"fields": {"summary": args.get("summary", "")}})
                resp = await client.put(f"{self.base_url}/rest/api/3/issue/{issue_key}", json=payload)
                resp.raise_for_status()
                
                class ResultObj:
                    def __init__(self, text):
                        self.content = [type('obj', (object,), {'text': text})]
                return ResultObj(json.dumps({"success": True, "message": f"Issue {issue_key} updated successfully."}))

            # 4. Create Issue
            elif tool_name in ("createJiraIssue", "create_issue"):
                payload = {
                    "fields": {
                        "project": {"key": args.get("project_key", "PAY")},
                        "summary": args.get("summary", "Incident Report"),
                        "issuetype": {"name": args.get("issue_type", "Bug")},
                        "description": {
                            "type": "doc", "version": 1,
                            "content": [{"type": "paragraph", "content": [{"type": "text", "text": args.get("description", "")}]}]
                        }
                    }
                }
                resp = await client.post(f"{self.base_url}/rest/api/3/issue", json=payload)
                resp.raise_for_status()
                data = resp.json()
                
                class ResultObj:
                    def __init__(self, text):
                        self.content = [type('obj', (object,), {'text': text})]
                return ResultObj(json.dumps(data))

            else:
                raise ValueError(f"Unknown Atlassian tool: {tool_name}")