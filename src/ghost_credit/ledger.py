"""Durable ledger of used Paystack references (DynamoDB), keyed by a hash.

Why: one real payment must not confirm two checks, even after the Lambda
container restarts. Only a keyed hash of the reference is stored, never the
reference itself, so a leaked table reveals no payment references. The item
holds ``ref_hash`` and ``expires_at`` and nothing else.

``boto3`` is imported only when a client is first needed, so this module
imports without it. The reference and the key are never logged or returned.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import time
from typing import Any, Callable, Mapping

from ghost_credit.pipeline import InMemoryUsedReferences, UsedReferences

__all__ = [
    "DynamoUsedReferences",
    "LedgerError",
    "get_used_references",
    "hash_reference",
    "DEFAULT_USED_REFS_TABLE",
    "RETENTION_SECONDS",
]

DEFAULT_USED_REFS_TABLE = "ghost-credit-used-refs"
RETENTION_SECONDS = 30 * 24 * 60 * 60  # 2,592,000: 30 days
KEY_ENV = "LEDGER_HMAC_KEY"
TABLE_ENV = "USED_REFS_TABLE"

_log = logging.getLogger("ghost_credit.ledger")

# One in-memory ledger per process, used when no durable key is set.
_SHARED_MEMORY_LEDGER = InMemoryUsedReferences()


class LedgerError(Exception):
    """A plain ledger failure. Its message never holds a reference or key."""


def hash_reference(reference: str, key: str) -> str:
    """Return ``"hmac:"`` plus the lowercase HMAC-SHA256 hex of the reference."""
    if not isinstance(reference, str) or not reference:
        raise LedgerError("empty reference")
    if not isinstance(key, str) or not key:
        raise LedgerError("missing ledger key")
    digest = hmac.new(
        key.encode("utf-8"), reference.encode("utf-8", "surrogatepass"), hashlib.sha256
    )
    return "hmac:" + digest.hexdigest()


def _error_code(exc: BaseException) -> str:
    """Return the AWS error code of an exception, or its class name."""
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        error = response.get("Error")
        if isinstance(error, dict) and isinstance(error.get("Code"), str):
            return error["Code"]
    return type(exc).__name__


class DynamoUsedReferences:
    """Used-reference ledger in DynamoDB. Implements the UsedReferences protocol."""

    def __init__(
        self,
        table_name: str | None = None,
        client: Any = None,
        env: Mapping[str, str] | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        """Keep the settings. The key is read from ``env`` at call time."""
        self._env = os.environ if env is None else env
        self._table = table_name or self._env.get(TABLE_ENV) or DEFAULT_USED_REFS_TABLE
        self._client = client
        self._clock = clock

    def _get_client(self) -> Any:
        """Return the DynamoDB client, creating it on first use."""
        if self._client is None:
            import boto3  # lazy: tests and imports never need it

            self._client = boto3.client("dynamodb")
        return self._client

    def _ref_hash(self, reference: str) -> str:
        """Hash the reference with the key read now from the environment."""
        return hash_reference(reference, self._env.get(KEY_ENV) or "")

    def is_used(self, reference: str) -> bool:
        """True when the hashed reference is in the table.

        Any failure raises a plain LedgerError so the caller takes the safe
        "could not check" path. The message never holds the reference.
        """
        try:
            response = self._get_client().get_item(
                TableName=self._table,
                Key={"ref_hash": {"S": self._ref_hash(reference)}},
                ConsistentRead=True,
            )
            return bool(isinstance(response, dict) and response.get("Item"))
        except Exception as exc:  # noqa: BLE001 - re-raised as a plain, clean error
            raise LedgerError("ledger lookup failed: " + type(exc).__name__) from None

    def mark_used(self, reference: str) -> None:
        """Store the hashed reference once. Never raises.

        An already-stored reference counts as success. Other failures are logged
        by error type only, because a failed note must not change the verdict.
        """
        try:
            expires_at = int(self._clock()) + RETENTION_SECONDS
            self._get_client().put_item(
                TableName=self._table,
                Item={
                    "ref_hash": {"S": self._ref_hash(reference)},
                    "expires_at": {"N": str(expires_at)},
                },
                ConditionExpression="attribute_not_exists(ref_hash)",
            )
        except Exception as exc:  # noqa: BLE001 - never leak or raise
            if _error_code(exc) == "ConditionalCheckFailedException":
                return
            _log.warning("ledger mark_used failed: %s", type(exc).__name__)


def get_used_references(
    env: Mapping[str, str] | None = None, client: Any = None
) -> UsedReferences:
    """Return the DynamoDB ledger when LEDGER_HMAC_KEY is set, else the shared in-memory one."""
    source = os.environ if env is None else env
    key = source.get(KEY_ENV)
    if isinstance(key, str) and key.strip():
        return DynamoUsedReferences(client=client, env=source)
    return _SHARED_MEMORY_LEDGER
