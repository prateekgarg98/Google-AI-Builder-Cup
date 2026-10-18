from mcp.server.fastmcp import FastMCP
from server.state import get_state, validate_rollback_target, reset_state

mcp = FastMCP("DevOps MCP")


@mcp.tool()
def get_deployment_status(service: str, environment: str) -> dict:
    """Get the current deployment status of a service."""
    state = get_state(service, environment)

    return {
        "service": state.service,
        "environment": state.environment,
        "status": state.deployment_status,
        "version": state.current_version,
        "failure_reason": state.failure_reason,
        "risk_level": "LOW",
        "operation": "READ",
    }


@mcp.tool()
def get_logs(service: str, environment: str) -> dict:
    """Get recent deployment and application logs."""
    state = get_state(service, environment)

    return {
        "service": state.service,
        "environment": state.environment,
        "logs": state.logs,
        "risk_level": "LOW",
        "operation": "READ",
    }


@mcp.tool()
def get_service_health(service: str, environment: str) -> dict:
    """Get the current health status of a service."""
    state = get_state(service, environment)

    return {
        "service": state.service,
        "environment": state.environment,
        "health": state.health,
        "risk_level": "LOW",
        "operation": "READ",
    }


@mcp.tool()
def get_current_version(service: str, environment: str) -> dict:
    """Get the currently deployed version of a service."""
    state = get_state(service, environment)

    return {
        "service": state.service,
        "environment": state.environment,
        "version": state.current_version,
        "risk_level": "LOW",
        "operation": "READ",
    }


@mcp.tool()
def rollback_deployment(
    service: str,
    environment: str,
    target_version: str,
) -> dict:
    """Rollback a service to a validated target version and append recovery logs."""
    state = get_state(service, environment)

    previous_version = state.current_version

    validate_rollback_target(
        service,
        environment,
        target_version,
        previous_version,
    )

    state.current_version = target_version
    state.deployment_status = "ROLLED_BACK"
    state.health = "HEALTHY"
    state.failure_reason = None
    
    # Append the rollback logs directly onto the existing failure log history
    state.logs.extend([
        f"Rollback initiated from {previous_version} to {target_version}",
        f"Traffic successfully redirected to {target_version}",
        "Health checks passed: Service status is HEALTHY"
    ])

    return {
        "service": state.service,
        "environment": state.environment,
        "previous_version": previous_version,
        "target_version": state.current_version,
        "status": "ROLLED_BACK",
        "risk_level": "HIGH",
        "operation": "STATE_CHANGE",
        "approval_required": True,
    }


@mcp.tool()
def verify_deployment(service: str, environment: str) -> dict:
    """Verify whether the service deployment is healthy."""
    state = get_state(service, environment)

    return {
        "service": state.service,
        "environment": state.environment,
        "deployment_status": state.deployment_status,
        "health": state.health,
        "version": state.current_version,
        "verified": (
            state.deployment_status in {"HEALTHY", "ROLLED_BACK"}
            and state.health == "HEALTHY"
        ),
        "risk_level": "LOW",
        "operation": "READ",
    }


@mcp.tool()
def reset_demo_environment(service: str, environment: str) -> dict:
    """Reset the service state and error logs back to the failed deployment for the next demo."""
    state = get_state(service, environment) 
    reset_state()

    return {
        "service": state.service,
        "environment": state.environment,
        "status": "RESET_FOR_DEMO",
        "message": "Environment and logs successfully reset to FAILED state for the next judge."
    }


if __name__ == "__main__":
    mcp.run()