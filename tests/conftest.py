"""Shared test setup: no test may reach the network."""

from __future__ import annotations

import socket
from typing import Any

import pytest


@pytest.fixture(autouse=True)
def _block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make creating a socket fail, so a test can never make a network call."""

    def _refuse(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("network access is blocked in tests")

    monkeypatch.setattr(socket, "socket", _refuse)
