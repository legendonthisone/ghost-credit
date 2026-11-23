"""Shared Hypothesis strategies for the pattern-network tests (synthetic data only)."""

from __future__ import annotations

from hypothesis import strategies as st

from ghost_credit.pattern_network import (
    LookupResult,
    Match,
    ReportReceipt,
    Signals,
    Verdict,
)

text = st.text(max_size=20)
opt_text = st.none() | text

signals = st.builds(
    Signals,
    check_id=text,
    checked_at=text,
    channel=st.sampled_from(["sms", "screenshot", "whatsapp_text"]),
    amount_kobo=st.integers(min_value=0, max_value=10**12),
    currency=st.just("NGN"),
    claimed_bank=opt_text,
    sender_id=opt_text,
    claimed_reference=opt_text,
    payer_name_hash=opt_text,
    payer_account_hash=opt_text,
    payer_phone_hash=opt_text,
    screenshot_phash=opt_text,
    red_flags=st.lists(text, max_size=4),
    merchant_ref=opt_text,
    merchant_category=text,
)

verdicts = st.builds(
    Verdict,
    code=st.sampled_from(["CONFIRMED", "NOT_FOUND", "SUSPICIOUS", "UNVERIFIED"]),
    paystack_checked=st.booleans(),
    owner_outcome=st.sampled_from(["unknown", "fake", "real"]),
    reasons=st.lists(text, max_size=4),
)

matches = st.builds(
    Match,
    pattern_id=text,
    matched_on=st.lists(text, max_size=3),
    first_seen=opt_text,
    times_seen=st.integers(min_value=0, max_value=1000),
    shops_seen=st.integers(min_value=0, max_value=1000),
    last_verdict=opt_text,
    confidence=st.floats(min_value=0, max_value=1, allow_nan=False),
    summary=opt_text,
)

lookup_results = st.builds(
    LookupResult,
    network_available=st.booleans(),
    matched=st.booleans(),
    matches=st.lists(matches, max_size=3),
    trace_url=opt_text,
)

receipts = st.builds(
    ReportReceipt,
    accepted=st.booleans(),
    status=st.sampled_from(["disabled", "queued", "rejected"]),
    pattern_id=opt_text,
    trace_url=opt_text,
)

any_valid = st.one_of(signals, verdicts, matches, lookup_results, receipts)
