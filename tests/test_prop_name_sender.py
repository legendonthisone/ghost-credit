from hypothesis import given, settings, strategies as st

from ghost_credit.parser import parse_sms_alert

_letters = st.characters(whitelist_categories=("Lu", "Ll", "Lt", "Lm", "Lo"))


@st.composite
def name_sender_ids(draw):
    """Sender ids with at least one letter, mixed with digits, spaces and symbols."""
    prefix = draw(st.text(max_size=20))
    letter = draw(_letters)
    suffix = draw(st.text(max_size=20))
    return prefix + letter + suffix


# Feature: alert-parser, Property 4: Name senders are not flagged
# **Validates: Requirements 4.2, 4.3, 4.4, 10.7**
@settings(max_examples=200)
@given(sender_id=name_sender_ids(), text=st.text(max_size=1000))
def test_name_sender_not_flagged(sender_id, text):
    assert any(ch.isalpha() for ch in sender_id)
    result = parse_sms_alert(text, sender_id)
    assert "SENDER_ID_MISMATCH" not in result.red_flags
