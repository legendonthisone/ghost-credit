"""Property test: fields the contract does not define are ignored."""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

import pn_strategies as S

_extras = st.dictionaries(
    st.text(min_size=1, max_size=12).map(lambda s: "zz_extra_" + s),
    st.one_of(st.none(), st.integers(), st.text(max_size=10)),
    max_size=4,
)


@settings(max_examples=100)
@given(S.any_valid, _extras)
def test_unknown_fields_ignored(obj, extras) -> None:
    """Feature: pattern-network-hook, Property 2: Unknown fields are ignored.

    **Validates: Requirements 2.13**
    """
    base = obj.to_dict()
    assert type(obj).from_dict({**base, **extras}) == type(obj).from_dict(base)
