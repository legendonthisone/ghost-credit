"""Property test: contract dataclasses survive to_dict then from_dict."""

from __future__ import annotations

from hypothesis import given, settings

import pn_strategies as S


@settings(max_examples=100)
@given(S.any_valid)
def test_round_trip(obj) -> None:
    """Feature: pattern-network-hook, Property 1: Dataclass round trip.

    **Validates: Requirements 2.12, 2.14**
    """
    assert type(obj).from_dict(obj.to_dict()) == obj
