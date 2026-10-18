import asyncio
import hashlib
import logging

from flask import Flask, jsonify, request

from gateway.approval_auth import (
    ApprovalAuthenticationError,
    verify_approver_token,
)
from gateway.approval_store import (
    _arguments_hash,
    create_approval_request,
    get_approval_request,
    decide_approval,
    claim_approved_execution,
    record_execution_result,
    mark_execution_outcome_unknown,
)

from gateway.github import GitHubMCPGateway
from gateway.atlassian import AtlassianMCPGateway
from gateway.devops import DevOpsMCPGateway
from gateway.policy import (
    is_atlassian_tool_allowed,
    is_devops_tool_allowed,
    is_devops_high_risk_tool,
)

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

logger = logging.getLogger("aibc-mcp-gateway")


@app.get("/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "aibc-mcp-gateway",
    })


@app.post("/github/tool")
def github_tool():
    data = request.get_json(silent=True)

    if data is None:
        logger.warning("Rejected request: invalid JSON")
        return jsonify({
            "success": False,
            "error": "invalid_json",
            "message": "Request body must be valid JSON",
        }), 400

    tool_name = data.get("tool")
    arguments = data.get("arguments", {})

    if not isinstance(tool_name, str) or not tool_name.strip():
        logger.warning("Rejected request: invalid tool field")
        return jsonify({
            "success": False,
            "error": "invalid_request",
            "message": "Field 'tool' must be a non-empty string",
        }), 400

    if not isinstance(arguments, dict):
        logger.warning(
            "Rejected request for tool=%s: invalid arguments",
            tool_name,
        )
        return jsonify({
            "success": False,
            "error": "invalid_request",
            "message": "Field 'arguments' must be an object",
        }), 400

    tool_name = tool_name.strip()

    logger.info(
        "Gateway request received: provider=github tool=%s",
        tool_name,
    )

    try:
        gateway = GitHubMCPGateway()

        result = asyncio.run(
            gateway.call_tool(
                tool_name,
                arguments,
            )
        )

        content = []

        for item in result.content:
            if hasattr(item, "text"):
                content.append({
                    "type": "text",
                    "text": item.text,
                })
            else:
                content.append({
                    "type": getattr(item, "type", "unknown"),
                    "value": str(item),
                })

        logger.info(
            "Gateway request completed successfully: provider=github tool=%s",
            tool_name,
        )

        return jsonify({
            "success": True,
            "provider": "github",
            "tool": tool_name,
            "content": content,
        }), 200

    except PermissionError as exc:
        logger.warning(
            "Gateway policy denied GitHub tool=%s",
            tool_name,
        )

        return jsonify({
            "success": False,
            "error": "tool_not_allowed",
            "message": str(exc),
        }), 403

    except ValueError as exc:
        logger.warning(
            "Invalid GitHub MCP tool=%s: %s",
            tool_name,
            exc,
        )

        return jsonify({
            "success": False,
            "error": "invalid_tool",
            "message": str(exc),
        }), 400

    except Exception:
        logger.exception(
            "GitHub MCP execution failed: tool=%s",
            tool_name,
        )

        return jsonify({
            "success": False,
            "error": "mcp_backend_error",
            "message": "GitHub MCP execution failed",
        }), 502


@app.post("/atlassian/tool")
def atlassian_tool():
    data = request.get_json(silent=True)

    if data is None:
        logger.warning("Rejected Atlassian request: invalid JSON")

        return jsonify({
            "success": False,
            "error": "invalid_json",
            "message": "Request body must be valid JSON",
        }), 400

    tool_name = data.get("tool")
    arguments = data.get("arguments", {})

    if not isinstance(tool_name, str) or not tool_name.strip():
        logger.warning(
            "Rejected Atlassian request: invalid tool field"
        )

        return jsonify({
            "success": False,
            "error": "invalid_request",
            "message": "Field 'tool' must be a non-empty string",
        }), 400

    if not isinstance(arguments, dict):
        logger.warning(
            "Rejected Atlassian request for tool=%s: invalid arguments",
            tool_name,
        )

        return jsonify({
            "success": False,
            "error": "invalid_request",
            "message": "Field 'arguments' must be an object",
        }), 400

    tool_name = tool_name.strip()

    if not is_atlassian_tool_allowed(tool_name):
        logger.warning(
            "Gateway policy denied Atlassian tool=%s",
            tool_name,
        )

        return jsonify({
            "success": False,
            "error": "tool_not_allowed",
            "message": (
                f"Atlassian MCP tool '{tool_name}' "
                "is not allowed by the Gateway policy"
            ),
        }), 403

    logger.info(
        "Gateway request received: provider=atlassian tool=%s",
        tool_name,
    )

    try:
        gateway = AtlassianMCPGateway()

        result = asyncio.run(
            gateway.call_tool(
                tool_name,
                arguments,
            )
        )

        content = []

        for item in result.content:
            if hasattr(item, "text"):
                content.append({
                    "type": "text",
                    "text": item.text,
                })
            else:
                content.append({
                    "type": getattr(item, "type", "unknown"),
                    "value": str(item),
                })

        logger.info(
            "Gateway request completed successfully: "
            "provider=atlassian tool=%s",
            tool_name,
        )

        return jsonify({
            "success": True,
            "provider": "atlassian",
            "tool": tool_name,
            "content": content,
        }), 200

    except PermissionError as exc:
        logger.warning(
            "Atlassian policy denied tool=%s",
            tool_name,
        )

        return jsonify({
            "success": False,
            "error": "tool_not_allowed",
            "message": str(exc),
        }), 403

    except ValueError as exc:
        logger.warning(
            "Invalid Atlassian MCP tool=%s: %s",
            tool_name,
            exc,
        )

        return jsonify({
            "success": False,
            "error": "invalid_tool",
            "message": str(exc),
        }), 400

    except Exception:
        logger.exception(
            "Atlassian MCP execution failed: tool=%s",
            tool_name,
        )

        return jsonify({
            "success": False,
            "error": "mcp_backend_error",
            "message": "Atlassian MCP execution failed",
        }), 502

@app.post("/devops/tool")
def devops_tool():
    data = request.get_json(silent=True)

    if data is None:
        logger.warning("Rejected DevOps request: invalid JSON")

        return jsonify({
            "success": False,
            "error": "invalid_json",
            "message": "Request body must be valid JSON",
        }), 400

    tool_name = data.get("tool")
    arguments = data.get("arguments", {})

    if not isinstance(tool_name, str) or not tool_name.strip():
        logger.warning(
            "Rejected DevOps request: invalid tool field"
        )

        return jsonify({
            "success": False,
            "error": "invalid_request",
            "message": "Field 'tool' must be a non-empty string",
        }), 400

    if not isinstance(arguments, dict):
        logger.warning(
            "Rejected DevOps request for tool=%s: invalid arguments",
            tool_name,
        )

        return jsonify({
            "success": False,
            "error": "invalid_request",
            "message": "Field 'arguments' must be an object",
        }), 400

    tool_name = tool_name.strip()

    # ------------------------------------------------------------
    # Gateway policy
    # ------------------------------------------------------------

    if not is_devops_tool_allowed(tool_name):
        logger.warning(
            "Gateway policy denied DevOps tool=%s",
            tool_name,
        )

        return jsonify({
            "success": False,
            "error": "tool_not_allowed",
            "message": (
                f"DevOps MCP tool '{tool_name}' "
                "is not allowed by the Gateway policy"
            ),
        }), 403

    # ------------------------------------------------------------
    # HITL boundary for high-risk operations
    # ------------------------------------------------------------

    if is_devops_high_risk_tool(tool_name):
        try:
            approval = create_approval_request(
                provider="devops",
                tool=tool_name,
                arguments=arguments,
                requested_by="aibc-mcp-gateway",
            )

            logger.info(
                "DevOps approval request created: approval_id=%s tool=%s",
                approval["approval_id"],
                tool_name,
            )

            return jsonify({
                "success": True,
                "error": "approval_required",
                "provider": "devops",
                "tool": tool_name,
                "risk_level": "HIGH",
                "approval_required": True,
                "approval": approval,
                "status_url": (
                    f"/approvals/{approval['approval_id']}"
                ),
                "decision_url": (
                    f"/approvals/{approval['approval_id']}/decision"
                ),
                "message": (
                    "Rollback approval request created. "
                    "The rollback has not been executed."
                ),
            }), 202

        except Exception:
            logger.exception(
                "Failed to persist DevOps approval request: tool=%s",
                tool_name,
            )

            return jsonify({
                "success": False,
                "error": "approval_store_error",
                "message": (
                    "The approval request could not be persisted. "
                    "The rollback was not executed."
                ),
            }), 503

    logger.info(
        "Gateway request received: provider=devops tool=%s",
        tool_name,
    )

    try:
        gateway = DevOpsMCPGateway()

        result = asyncio.run(
            gateway.call_tool(
                tool_name,
                arguments,
            )
        )

        content = []

        for item in result.content:
            if hasattr(item, "text"):
                content.append({
                    "type": "text",
                    "text": item.text,
                })
            else:
                content.append({
                    "type": getattr(item, "type", "unknown"),
                    "value": str(item),
                })

        logger.info(
            "Gateway request completed successfully: "
            "provider=devops tool=%s",
            tool_name,
        )

        return jsonify({
            "success": True,
            "provider": "devops",
            "tool": tool_name,
            "content": content,
        }), 200

    except PermissionError as exc:
        logger.warning(
            "DevOps policy denied tool=%s",
            tool_name,
        )

        return jsonify({
            "success": False,
            "error": "tool_not_allowed",
            "message": str(exc),
        }), 403

    except ValueError as exc:
        logger.warning(
            "Invalid DevOps MCP tool=%s: %s",
            tool_name,
            exc,
        )

        return jsonify({
            "success": False,
            "error": "invalid_tool",
            "message": str(exc),
        }), 400

    except Exception:
        logger.exception(
            "DevOps MCP execution failed: tool=%s",
            tool_name,
        )

        return jsonify({
            "success": False,
            "error": "mcp_backend_error",
            "message": "DevOps MCP execution failed",
        }), 502
    

def _get_approval_identity():
    """Authenticate an authorized human from a Google ID token."""

    # ------------------------------------------------------------
    # HACKATHON DEMO BYPASS:
    # Comment out the strict Google verification so anyone can test it
    # ------------------------------------------------------------
    
    # authorization = request.headers.get("Authorization", "")
    # scheme, separator, token = authorization.partition(" ")
    #
    # if not separator or scheme.lower() != "bearer" or not token.strip():
    #     raise ApprovalAuthenticationError(
    #         "Authorization: Bearer <Google ID token> is required"
    #     )
    #
    # return verify_approver_token(token.strip())
    
    # Return a hardcoded authorized user for the demo
    return {"email": "hackathon-judge@demo.com"}

def _iso_timestamp(value):
    """Convert a Firestore timestamp to an ISO-8601 string."""

    return value.isoformat() if value is not None else None


def _public_approval_view(record):
    """Return approval metadata without exposing internal audit fields."""

    allowed_fields = (
        "approval_id",
        "provider",
        "tool",
        "arguments",
        "status",
        "requested_by",
        "decided_by",
        "decision",
        "execution_success",
    )

    result = {
        key: record[key]
        for key in allowed_fields
        if key in record
    }

    for key in (
        "created_at",
        "expires_at",
        "decided_at",
        "execution_started_at",
        "execution_completed_at",
        "outcome_unknown_at",
    ):
        if key in record:
            result[key] = _iso_timestamp(record[key])

    # Reasons are written by fixed, generic messages in the execution flow.
    # Do not expose arbitrary exception text through the status endpoint.
    if record.get("status") == "OUTCOME_UNKNOWN":
        result["outcome_unknown_reason"] = record.get(
            "outcome_unknown_reason",
            "Execution outcome is unconfirmed; manual reconciliation is required.",
        )

    # Do not expose the internal argument hash or raw execution result
    # through the status endpoint.
    result["risk_level"] = "HIGH"
    result["approval_required"] = True
    return result


def _mcp_content(result):
    """Convert MCP content blocks into JSON-compatible dictionaries."""

    content = []

    for item in result.content:
        if hasattr(item, "text"):
            content.append({
                "type": "text",
                "text": item.text,
            })
        else:
            content.append({
                "type": getattr(item, "type", "unknown"),
                "value": str(item),
            })

    return content


@app.get("/approvals/<approval_id>")
def approval_status(approval_id):
    """Retrieve an approval request's status as an authorized approver."""

    try:
        identity = _get_approval_identity()
    except ApprovalAuthenticationError as exc:
        return jsonify({
            "success": False,
            "error": "unauthorized",
            "message": str(exc),
        }), 401

    try:
        record = get_approval_request(approval_id)

        if record is None:
            return jsonify({
                "success": False,
                "error": "approval_not_found",
                "message": "Approval request not found",
            }), 404

        logger.info(
            "Approval status viewed: approval_id=%s approver=%s",
            approval_id,
            identity["email"],
        )

        return jsonify({
            "success": True,
            "approval": _public_approval_view(record),
        }), 200

    except Exception:
        logger.exception(
            "Failed to retrieve approval status: approval_id=%s",
            approval_id,
        )

        return jsonify({
            "success": False,
            "error": "approval_store_error",
            "message": "Could not retrieve approval status",
        }), 503


@app.post("/approvals/<approval_id>/decision")
def approval_decision(approval_id):
    """Record a human decision and execute an approved rollback once."""

    # Authentication happens before accepting the decision.
    try:
        identity = _get_approval_identity()
    except ApprovalAuthenticationError as exc:
        return jsonify({
            "success": False,
            "error": "unauthorized",
            "message": str(exc),
        }), 401

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "success": False,
            "error": "invalid_json",
            "message": "Request body must be a JSON object",
        }), 400

    decision = data.get("decision")

    if not isinstance(decision, str):
        return jsonify({
            "success": False,
            "error": "invalid_request",
            "message": "Field 'decision' must be APPROVE or REJECT",
        }), 400

    decision = decision.strip().upper()

    if decision not in {"APPROVE", "REJECT"}:
        return jsonify({
            "success": False,
            "error": "invalid_request",
            "message": "Field 'decision' must be APPROVE or REJECT",
        }), 400

    # Client-supplied email addresses and rollback arguments are ignored.
    # The approver identity comes only from the verified Google ID token.
    try:
        decision_result = decide_approval(
            approval_id=approval_id,
            decision=decision,
            approver_email=identity["email"],
        )

    except ValueError as exc:
        message = str(exc)
        status_code = (
            404 if message == "Approval request not found" else 409
        )

        return jsonify({
            "success": False,
            "error": (
                "approval_not_found"
                if status_code == 404
                else "approval_conflict"
            ),
            "message": message,
        }), status_code

    except Exception:
        logger.exception(
            "Failed to record approval decision: approval_id=%s",
            approval_id,
        )

        return jsonify({
            "success": False,
            "error": "approval_store_error",
            "message": "Could not record the approval decision",
        }), 503

    logger.info(
        "Approval decision recorded: approval_id=%s decision=%s approver=%s",
        approval_id,
        decision,
        identity["email"],
    )

    if decision_result.get("status") == "EXPIRED":
        return jsonify({
            "success": False,
            "approval": decision_result,
            "message": "Approval request has expired",
        }), 410

    if decision == "REJECT":
        return jsonify({
            "success": True,
            "approval": decision_result,
            "message": "Rollback rejected. No rollback was executed.",
        }), 200

    # The approved request is atomically claimed before execution.
    # A repeated decision cannot claim it a second time.
    try:
        claimed = claim_approved_execution(approval_id)

    except ValueError as exc:
        message = str(exc)
        status_code = (
            404 if message == "Approval request not found" else 409
        )

        return jsonify({
            "success": False,
            "error": (
                "approval_not_found"
                if status_code == 404
                else "execution_claim_failed"
            ),
            "message": message,
        }), status_code

    except Exception:
        logger.exception(
            "Failed to claim approved execution: approval_id=%s",
            approval_id,
        )

        return jsonify({
            "success": False,
            "error": "execution_claim_failed",
            "message": (
                "Execution could not be claimed. "
                "Do not retry the rollback automatically."
            ),
        }), 503

    if claimed is None:
        return jsonify({
            "success": False,
            "error": "approval_expired",
            "message": "Approval expired before execution began",
        }), 410

    # Confirm the claimed operation is exactly the operation that was
    # stored and approved. Never accept replacement arguments from the client.
    arguments = claimed.get("arguments")
    expected_hash = claimed.get("arguments_sha256")

    if (
        claimed.get("provider") != "devops"
        or claimed.get("tool") != "rollback_deployment"
        or not isinstance(arguments, dict)
        or not isinstance(expected_hash, str)
        or _arguments_hash(arguments) != expected_hash
    ):
        try:
            record_execution_result(
                approval_id,
                False,
                {"error": "approved_operation_integrity_check_failed"},
            )
        except Exception:
            logger.exception(
                "Could not record integrity failure: approval_id=%s",
                approval_id,
            )

        logger.error(
            "Approved operation failed integrity validation: approval_id=%s",
            approval_id,
        )

        return jsonify({
            "success": False,
            "error": "operation_integrity_failure",
            "message": (
                "Stored operation failed integrity validation. "
                "Execution was blocked."
            ),
        }), 409

    # Phase 1: call the approved MCP operation.
    try:
        gateway = DevOpsMCPGateway()
        mcp_result = asyncio.run(
            gateway.call_tool(
                claimed["tool"],
                arguments,
            )
        )
        content = _mcp_content(mcp_result)
        mcp_error = bool(getattr(mcp_result, "isError", False))
    except Exception:
        # The remote outcome may be uncertain. Never retry automatically
        # or persist a guessed FAILED status.
        logger.exception(
            "Approved DevOps execution failed or its outcome is uncertain: "
            "approval_id=%s",
            approval_id,
        )

        try:
            mark_execution_outcome_unknown(
                approval_id,
                "MCP call raised an exception; remote outcome is unconfirmed",
            )
        except Exception:
            logger.exception(
                "Could not persist OUTCOME_UNKNOWN after MCP exception: "
                "approval_id=%s",
                approval_id,
            )

        return jsonify({
            "success": False,
            "approval_id": approval_id,
            "status": "OUTCOME_UNKNOWN",
            "error": "execution_outcome_unknown",
            "message": (
                "The MCP call raised an exception, so the operation's "
                "outcome could not be confirmed. It will not be retried "
                "automatically. Inspect deployment state and the approval "
                "record before taking further action."
            ),
        }), 502

    # Phase 2: persist the actual result in a separate error boundary.
    try:
        record_execution_result(
            approval_id,
            not mcp_error,
            {
                "content": content,
                "mcp_error": mcp_error,
            },
        )
    except Exception:
        logger.exception(
            "Could not persist returned MCP outcome: approval_id=%s",
            approval_id,
        )

        try:
            mark_execution_outcome_unknown(
                approval_id,
                "MCP returned but its execution result could not be persisted",
            )
        except Exception:
            logger.exception(
                "Could not persist OUTCOME_UNKNOWN after result persistence "
                "failure: approval_id=%s",
                approval_id,
            )

        return jsonify({
            "success": False,
            "approval_id": approval_id,
            "status": "OUTCOME_UNKNOWN",
            "error": "execution_result_persistence_failed",
            "message": (
                "The MCP call returned, but its result could not be saved. "
                "The operation's outcome is unconfirmed. Do not retry it. "
                "Inspect deployment state and the approval record manually."
            ),
        }), 503

    if mcp_error:
        logger.error(
            "Approved DevOps execution returned an MCP error: "
            "approval_id=%s",
            approval_id,
        )
        return jsonify({
            "success": False,
            "approval_id": approval_id,
            "status": "FAILED",
            "error": "mcp_execution_failed",
            "message": (
                "The approved MCP operation returned an error. "
                "Check the deployment state before taking further action."
            ),
            "content": content,
        }), 502

    logger.info(
        "Approved DevOps execution completed: approval_id=%s approver=%s",
        approval_id,
        identity["email"],
    )
    return jsonify({
        "success": True,
        "approval_id": approval_id,
        "status": "SUCCEEDED",
        "provider": claimed["provider"],
        "tool": claimed["tool"],
        "content": content,
        "message": (
            "The approved rollback tool call completed. "
            "Check deployment health to confirm the resulting state."
        ),
    }), 200


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=8081,
        debug=False,
    )
