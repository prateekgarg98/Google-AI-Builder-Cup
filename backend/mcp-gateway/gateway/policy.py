ALLOWED_GITHUB_TOOLS = {
    "get_me",
    "get_commit",
    "get_file_contents",
    "get_latest_release",
    "get_release_by_tag",
    "get_tag",
    "list_branches",
    "list_commits",
    "list_issues",
    "list_pull_requests",
    "list_releases",
    "list_tags",
    "search_code",
    "search_commits",
    "search_issues",
    "search_pull_requests",
    "search_repositories",
    "search_users",
}

ALLOWED_ATLASSIAN_TOOLS = {
    "getJiraIssue",
    "searchJiraIssuesUsingJql",
    "updateJiraIssue",
    "createJiraIssue",
    "get_issue",
    "search_issues",
    "update_issue",
    "create_issue",
}

def is_github_tool_allowed(tool_name: str) -> bool:
    return tool_name in ALLOWED_GITHUB_TOOLS


def is_atlassian_tool_allowed(tool_name: str) -> bool:
    return tool_name in ALLOWED_ATLASSIAN_TOOLS


# ============================================================
# DEVOPS MCP POLICY
# ============================================================

ALLOWED_DEVOPS_READ_TOOLS = {
    "get_deployment_status",
    "get_logs",
    "get_service_health",
    "get_current_version",
    "verify_deployment",
    "reset_demo_environment"
}


ALLOWED_DEVOPS_HIGH_RISK_TOOLS = {
    "rollback_deployment",
}


def is_devops_tool_allowed(tool_name: str) -> bool:
    """
    Return True only for explicitly approved DevOps MCP tools.
    """
    return (
        tool_name in ALLOWED_DEVOPS_READ_TOOLS
        or tool_name in ALLOWED_DEVOPS_HIGH_RISK_TOOLS
    )


def is_devops_high_risk_tool(tool_name: str) -> bool:
    """
    Return True when a DevOps MCP tool changes system state
    and therefore requires an additional approval boundary.
    """
    return tool_name in ALLOWED_DEVOPS_HIGH_RISK_TOOLS
