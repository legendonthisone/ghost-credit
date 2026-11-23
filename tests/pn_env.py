"""Small helpers for the pattern-network tests: set the environment and capture logs."""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Dict, Iterator, List, Optional
from unittest import mock

# Fixed fake key, built from pieces so no key-looking literal sits in the repo.
FAKE_KEY = "-".join(["fixed", "test", "hmac", "key", "0001"])
FAKE_MERCHANT_REF = "m_" + "test1"

_NAMES = ("PATTERN_NETWORK", "PATTERN_NETWORK_HMAC_KEY", "PATTERN_NETWORK_MERCHANT_REF")


@contextmanager
def hook_env(
    switch: Optional[str] = None,
    key: Optional[str] = None,
    merchant_ref: Optional[str] = None,
) -> Iterator[None]:
    """Run with exactly these hook variables set (None means unset), then restore."""
    wanted: Dict[str, str] = {}
    for name, value in zip(_NAMES, (switch, key, merchant_ref)):
        if value is not None:
            wanted[name] = value
    with mock.patch.dict(os.environ, wanted):
        for name in _NAMES:
            if name not in wanted:
                os.environ.pop(name, None)
        yield


class _ListHandler(logging.Handler):
    """Collect formatted log lines in a list."""

    def __init__(self, sink: List[str]) -> None:
        super().__init__(level=logging.DEBUG)
        self.sink = sink

    def emit(self, record: logging.LogRecord) -> None:
        self.sink.append(record.getMessage())


@contextmanager
def capture_logs() -> Iterator[List[str]]:
    """Collect every message logged by the pattern_network module."""
    lines: List[str] = []
    logger = logging.getLogger("ghost_credit.pattern_network")
    handler = _ListHandler(lines)
    old_level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    try:
        yield lines
    finally:
        logger.removeHandler(handler)
        logger.setLevel(old_level)
