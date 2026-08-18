"""Politique de retry partagée pour les appels Bedrock (converse + embeddings)."""

from __future__ import annotations

from botocore.exceptions import ClientError

RETRYABLE_ERROR_CODES = {
    "ThrottlingException",
    "ModelTimeoutException",
    "ServiceUnavailableException",
    "InternalServerException",
}


def is_retryable_bedrock_error(exc: BaseException) -> bool:
    if not isinstance(exc, ClientError):
        return False
    code = exc.response.get("Error", {}).get("Code", "")
    return code in RETRYABLE_ERROR_CODES
