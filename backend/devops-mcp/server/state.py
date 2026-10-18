from dataclasses import dataclass, field

@dataclass
class DeploymentState:
    service: str
    environment: str
    current_version: str
    deployment_status: str
    health: str
    failure_reason: str | None = None
    logs: list[str] = field(default_factory=list)

STATE = DeploymentState(
    service="payment-service",
    environment="production",
    current_version="v2.4.1",
    deployment_status="FAILED",
    health="UNHEALTHY",
    failure_reason="Missing required environment variable: PAYMENT_API_URL",
    logs=[
        "Deployment v2.4.1 started",
        "Configuration validation failed",
        "Missing required environment variable: PAYMENT_API_URL",
        "Deployment marked as FAILED",
    ],
)

ALLOWED_VERSIONS = {
    "payment-service": {
        "production": {
            "v2.4.0",
            "v2.4.1",
        }
    }
}

def get_state(service: str, environment: str) -> DeploymentState:
    if service != STATE.service or environment != STATE.environment:
        raise ValueError(
            f"Unknown service/environment: {service}/{environment}"
        )
    return STATE

def validate_rollback_target(
    service: str,
    environment: str,
    target_version: str,
    current_version: str,
) -> None:
    allowed_versions = (
        ALLOWED_VERSIONS
        .get(service, {})
        .get(environment, set())
    )

    if target_version not in allowed_versions:
        raise ValueError(
            f"Invalid rollback target: {target_version}. "
            f"Allowed versions: {sorted(allowed_versions)}"
        )

    if target_version == current_version:
        raise ValueError(
            f"Rollback target {target_version} is already the current version"
        )

def reset_state() -> None:
    """Instantly resets the global state back to the broken scenario and restores initial failure logs."""
    STATE.current_version = "v2.4.1"
    STATE.deployment_status = "FAILED"
    STATE.health = "UNHEALTHY"
    STATE.failure_reason = "Missing required environment variable: PAYMENT_API_URL"
    STATE.logs = [
        "Deployment v2.4.1 started",
        "Configuration validation failed",
        "Missing required environment variable: PAYMENT_API_URL",
        "Deployment marked as FAILED",
    ]