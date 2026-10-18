
import os

import google.auth.transport.requests
import google.oauth2.id_token


AUTHORIZED_APPROVERS = {
    "dhanvantraj7@gmail.com",
    "prateek.pgarg@gmail.com",
}


class ApprovalAuthenticationError(Exception):
    """Raised when an approval request has no valid authorized identity."""


def verify_approver_token(token: str) -> dict:
    """Verify a Google ID token and return the authorized identity."""

    if not isinstance(token, str) or not token.strip():
        raise ApprovalAuthenticationError("Missing Google ID token")

    client_id = os.environ.get("EWA_GOOGLE_CLIENT_ID")
    if not client_id:
        raise ApprovalAuthenticationError(
            "EWA Google OAuth Client ID is not configured"
        )

    try:
        request_adapter = google.auth.transport.requests.Request()
        claims = google.oauth2.id_token.verify_oauth2_token(
            token.strip(),
            request_adapter,
            audience=client_id,
        )
    except Exception as exc:
        raise ApprovalAuthenticationError(
            "Google ID token is invalid or expired"
        ) from exc

    email = claims.get("email", "").strip().lower()

    if claims.get("email_verified") is not True:
        raise ApprovalAuthenticationError(
            "Google account email is not verified"
        )

    if email not in AUTHORIZED_APPROVERS:
        raise ApprovalAuthenticationError(
            "This Google account is not an authorized approver"
        )

    return {
        "email": email,
        "name": claims.get("name", email),
        "subject": claims.get("sub"),
    }