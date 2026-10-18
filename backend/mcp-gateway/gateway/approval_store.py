
import hashlib
import json
import os
import secrets
from datetime import datetime, timedelta, timezone

from google.cloud import firestore


COLLECTION_NAME = "ewa_approvals"
APPROVAL_TTL_MINUTES = 15


def _utc_now():
    return datetime.now(timezone.utc)


def _get_client():
    # Uses Application Default Credentials locally and the attached
    # service account on Cloud Run. No service-account key is needed.
    return firestore.Client(
        project=os.environ.get("GOOGLE_CLOUD_PROJECT", "ai-builder-cup-2026")
    )


def _arguments_hash(arguments: dict) -> str:
    canonical = json.dumps(
        arguments,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def create_approval_request(
    provider: str,
    tool: str,
    arguments: dict,
    requested_by: str,
) -> dict:
    """Persist a pending approval request for a specific tool invocation."""

    if provider != "devops" or tool != "rollback_deployment":
        raise ValueError("Only DevOps rollback approvals are supported")

    if not isinstance(arguments, dict):
        raise ValueError("Arguments must be an object")

    if not isinstance(requested_by, str) or not requested_by.strip():
        raise ValueError("A verified requester identity is required")

    now = _utc_now()
    expires_at = now + timedelta(minutes=APPROVAL_TTL_MINUTES)

    db = _get_client()
    document_ref = db.collection(COLLECTION_NAME).document(
        secrets.token_urlsafe(24)
    )

    record = {
        "provider": provider,
        "tool": tool,
        "arguments": arguments,
        "arguments_sha256": _arguments_hash(arguments),
        "requested_by": requested_by.strip().lower(),
        "status": "PENDING",
        "created_at": now,
        "expires_at": expires_at,
        "decided_at": None,
        "decided_by": None,
        "execution_started_at": None,
        "execution_result": None,
    }

    document_ref.create(record)

    return {
        "approval_id": document_ref.id,
        "provider": provider,
        "tool": tool,
        "arguments": arguments,
        "status": "PENDING",
        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
        "risk_level": "HIGH",
        "approval_required": True,
    }


def get_approval_request(approval_id: str) -> dict | None:
    if not isinstance(approval_id, str) or not approval_id.strip():
        return None

    snapshot = (
        _get_client()
        .collection(COLLECTION_NAME)
        .document(approval_id)
        .get()
    )

    if not snapshot.exists:
        return None

    record = snapshot.to_dict()
    record["approval_id"] = snapshot.id
    return record


def decide_approval(
    approval_id: str,
    decision: str,
    approver_email: str,
) -> dict:
    """Atomically approve or reject a pending, unexpired request."""

    decision = decision.strip().upper()
    approver_email = approver_email.strip().lower()

    if decision not in {"APPROVE", "REJECT"}:
        raise ValueError("Decision must be APPROVE or REJECT")

    if not approver_email:
        raise ValueError("Verified approver identity is required")

    db = _get_client()
    document_ref = db.collection(COLLECTION_NAME).document(approval_id)

    @firestore.transactional
    def _decide(transaction):
        snapshot = document_ref.get(transaction=transaction)

        if not snapshot.exists:
            raise ValueError("Approval request not found")

        record = snapshot.to_dict()

        if record.get("status") != "PENDING":
            raise ValueError("Approval request is no longer pending")

        now = _utc_now()
        expires_at = record.get("expires_at")

        if not expires_at or now >= expires_at:
            transaction.update(document_ref, {
                "status": "EXPIRED",
                "updated_at": now,
            })
            return {"approval_id": approval_id, "status": "EXPIRED"}

        new_status = "APPROVED" if decision == "APPROVE" else "REJECTED"

        transaction.update(document_ref, {
            "status": new_status,
            "decided_at": now,
            "decided_by": approver_email,
            "decision": decision,
        })

        return {
            "approval_id": approval_id,
            "status": new_status,
            "decided_by": approver_email,
            "decided_at": now.isoformat(),
        }

    transaction = db.transaction()
    return _decide(transaction)


def claim_approved_execution(approval_id: str) -> dict:
    """Atomically claim an approved request for one execution attempt."""

    db = _get_client()
    document_ref = db.collection(COLLECTION_NAME).document(approval_id)

    @firestore.transactional
    def _claim(transaction):
        snapshot = document_ref.get(transaction=transaction)

        if not snapshot.exists:
            raise ValueError("Approval request not found")

        record = snapshot.to_dict()

        if record.get("status") != "APPROVED":
            raise ValueError("Request is not approved or was already claimed")

        now = _utc_now()
        expires_at = record.get("expires_at")

        if not expires_at or now >= expires_at:
            transaction.update(document_ref, {
                "status": "EXPIRED",
                "updated_at": now,
            })
            return None

        transaction.update(document_ref, {
            "status": "EXECUTING",
            "execution_started_at": now,
        })

        return {
            "approval_id": approval_id,
            "provider": record["provider"],
            "tool": record["tool"],
            "arguments": record["arguments"],
            "arguments_sha256": record["arguments_sha256"],
            "status": "EXECUTING",
        }

    transaction = db.transaction()
    return _claim(transaction)

def record_execution_result(
    approval_id: str,
    success: bool,
    result: dict,
) -> dict:
    """Persist the outcome of a claimed execution exactly once."""

    if not isinstance(success, bool):
        raise ValueError("success must be a boolean")

    if not isinstance(result, dict):
        raise ValueError("result must be an object")

    if not isinstance(approval_id, str) or not approval_id.strip():
        raise ValueError("A valid approval ID is required")

    db = _get_client()
    document_ref = db.collection(COLLECTION_NAME).document(approval_id)

    @firestore.transactional
    def _record(transaction):
        snapshot = document_ref.get(transaction=transaction)

        if not snapshot.exists:
            raise ValueError("Approval request not found")

        record = snapshot.to_dict()

        if record.get("status") != "EXECUTING":
            raise ValueError(
                "Execution result can only be recorded for an executing request"
            )

        now = _utc_now()
        new_status = "SUCCEEDED" if success else "FAILED"

        transaction.update(document_ref, {
            "status": new_status,
            "execution_completed_at": now,
            "execution_success": success,
            "execution_result": result,
        })

        return {
            "approval_id": approval_id,
            "status": new_status,
            "execution_success": success,
            "execution_completed_at": now.isoformat(),
        }

    transaction = db.transaction()
    return _record(transaction)

def mark_execution_outcome_unknown(
    approval_id: str,
    reason: str,
) -> dict:
    """Mark an executing operation as having an uncertain outcome."""

    if not isinstance(approval_id, str) or not approval_id.strip():
        raise ValueError("A valid approval ID is required")

    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("A non-empty reason is required")

    db = _get_client()
    document_ref = db.collection(COLLECTION_NAME).document(approval_id)

    @firestore.transactional
    def _mark_unknown(transaction):
        snapshot = document_ref.get(transaction=transaction)

        if not snapshot.exists:
            raise ValueError("Approval request not found")

        record = snapshot.to_dict()

        if record.get("status") != "EXECUTING":
            raise ValueError(
                "Outcome can only be marked unknown for an executing request"
            )

        now = _utc_now()

        transaction.update(document_ref, {
            "status": "OUTCOME_UNKNOWN",
            "outcome_unknown_at": now,
            "outcome_unknown_reason": reason.strip(),
        })

        return {
            "approval_id": approval_id,
            "status": "OUTCOME_UNKNOWN",
            "outcome_unknown_at": now.isoformat(),
        }

    transaction = db.transaction()
    return _mark_unknown(transaction)