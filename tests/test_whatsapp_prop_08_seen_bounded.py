"""Feature: whatsapp-webhook, Property 8: The Seen_Set stays bounded and forgets the oldest."""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from ghost_credit.whatsapp import SEEN_CAPACITY, SeenSet


@settings(max_examples=150, deadline=None)
@given(st.integers(min_value=1, max_value=12),
       st.lists(st.integers(min_value=0, max_value=30).map(str), max_size=80))
def test_seen_set_matches_oldest_first_model(capacity, ids) -> None:
    """**Validates: Requirements 7.5**"""
    seen = SeenSet(capacity)
    model: list[str] = []
    for message_id in ids:
        was_new = message_id not in model
        assert seen.add_if_new(message_id) is was_new
        if was_new:
            model.append(message_id)
            if len(model) > capacity:
                model.pop(0)
        assert len(seen) <= capacity
    assert all(m in seen for m in model)
    assert len(seen) == len(model)


def test_default_capacity_is_1000_and_first_id_is_forgotten() -> None:
    """**Validates: Requirements 7.5**"""
    seen = SeenSet()
    for number in range(SEEN_CAPACITY + 1):
        seen.add_if_new(str(number))
    assert SEEN_CAPACITY == 1000
    assert len(seen) == 1000
    assert "0" not in seen and "1" in seen and "1000" in seen
