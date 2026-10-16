import os
import secrets

from fastapi import Header, HTTPException


def require_operator(authorization: str | None = Header(default=None)):
    token = os.environ.get("REEFTRACE_LOCAL_TOKEN", "")
    if len(token) < 24:
        raise HTTPException(
            503, "Set REEFTRACE_LOCAL_TOKEN to a random secret of at least 24 characters"
        )
    if not secrets.compare_digest(authorization or "", "Bearer " + token):
        raise HTTPException(401, "Local operator token required")
    return os.environ.get("REEFTRACE_OPERATOR_ID", "local-operator")
