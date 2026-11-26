# Implementation Plan: alert-parser

## Overview

Implement `parse_sms_alert(text, sender_id) -> ParsedAlert` in `src/ghost_credit/parser.py` in Python, using only the standard library (`re`, `dataclasses`, `datetime`, `calendar`). Work follows the design's implementation order: scaffolding, types and skeleton, amount and balance logic, sender and pressure flags, dates, remaining extractors, then the tests. Requirement 10 requires at least 5 pytest example tests and one Hypothesis property test for each of design Properties 1 to 8.

## Tasks

- [x] 1. Project scaffolding
  - [x] 1.1 Create `pyproject.toml`, the package and the test directory
    - Add `pyproject.toml` with a `src` layout, pytest and hypothesis as dev dependencies, and pytest `testpaths = ["tests"]`
    - Create `src/ghost_credit/__init__.py` and an empty `tests/` directory
    - No runtime dependencies
    - _Requirements: 9.1, 9.2, 10.12_

- [x] 2. Core types and skeleton
  - [x] 2.1 Define `ParsedAlert`, `RED_FLAG_CODES`, named lists and the `parse_sms_alert` skeleton
    - Add the frozen `ParsedAlert` dataclass with the 10 fields and `red_flags` default via `field(default_factory=list)`
    - Add `RED_FLAG_CODES`, `PRESSURE_PHRASES` and `KNOWN_BANKS` as module-level named lists
    - Add `parse_sms_alert`: coerce a non-string `text` to `""`, truncate to 10,000 characters, keep `sender_id` unchanged, and wrap the body so an unexpected error returns a ParsedAlert with the sender-derived flags only
    - Add a flag collector that returns unique codes in `RED_FLAG_CODES` order
    - Document truncation in the docstring
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 9.1, 9.2, 9.3, 9.4, 9.5_

- [x] 3. Balance lines and amounts
  - [x] 3.1 Implement `_find_balance_lines` and balance extraction
    - Match the balance labels case-insensitively, with an optional `:` or `-`, an optional currency marker and a number
    - A label with no figure produces no Balance_Line
    - Set `available_balance_kobo` from the first Balance_Line, using integer arithmetic and accepting 0 to 2 decimal digits
    - Add `BALANCE_LINE_MISSING` when no Balance_Line exists, including empty and whitespace-only text
    - _Requirements: 3.4, 5.1, 5.2, 5.3, 5.4, 5.5_

  - [x] 3.2 Implement amount parsing and candidate scanning
    - Add `_parse_amount_token` using integer arithmetic only, with the `k` suffix and 1 to 2 decimal digits
    - Add `_find_amounts` for the marker form and the `CR` form, skipping Balance_Line spans, with the loose token capture, strict validation and the statuses `ok`, `odd_format` and `too_many_decimals`
    - Add `_extract_amount`: the first non-balance candidate decides `amount_kobo`, an odd candidate gives None, `currency` is `NGN` only for the marker form, and None when every amount is in a Balance_Line
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10_

  - [x] 3.3 Add `AMOUNT_FORMAT_ODD` detection and amount-in-words, and wire them in
    - Flag mixed comma and full-stop separators, decimals of 3 or more digits and bad comma groups, and clear `amount_kobo` for those
    - Add `_amount_words_kobo` and flag a mismatch with the digit amount while keeping the digit amount
    - Flag when any non-balance candidate is odd, even if an earlier clean candidate supplies `amount_kobo`
    - Wire the amount, balance and flag results into `parse_sms_alert`
    - _Requirements: 2.9, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

- [x] 4. Sender and pressure flags
  - [x] 4.1 Implement `_sender_is_phone` and wire `SENDER_ID_MISMATCH`
    - Phone_Number_Sender is digits, spaces, hyphens and an optional leading `+`, with 7 to 15 digits
    - Flag from `sender_id` alone, and never flag None, empty, whitespace-only, letter-containing or other non-matching values
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

  - [x] 4.2 Implement `_has_pressure` and wire `PRESSURE_LANGUAGE`
    - Lower-case the text, collapse whitespace runs, and match each phrase with word-boundary lookarounds
    - Flag once, with no flag for empty text or a match inside a longer word
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

- [x] 5. Date scanning
  - [x] 5.1 Implement `_scan_dates` and wire `DATE_ODD` and `alert_time`
    - Match the five Recognised_Date_Formats with `HH:MM[:SS]`, validating with `datetime(...)` in `try/except ValueError`, and set seconds to 0 when absent
    - Flag impossible values and unrecognised numeric date shapes (`\d{1,4}[/-]\d{1,2}[/-]\d{1,4}`), and ignore a lone time
    - Skip matches inside account, reference and balance spans
    - If any date is flagged, set `alert_time` to None and add `DATE_ODD` once
    - _Requirements: 3.3, 3.9, 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

- [x] 6. Remaining field extractors
  - [x] 6.1 Implement account, narration and reference extractors
    - `_extract_account`: `\b\d{3,4}\*{1,6}\d{3,4}\b`, returned as written
    - `_extract_narration`: label then text to end of line, stripped and capped at 200 characters
    - `_extract_reference`: try `Ref No` and `Session ID` before `Ref`, then an identifier of 4 to 50 characters from `[A-Za-z0-9/-]`
    - Return None for missing or malformed values, and compute these spans before the date scan so it can skip them
    - _Requirements: 3.1, 3.2, 3.5, 3.7, 3.8, 3.9_

  - [x] 6.2 Implement `_extract_bank` and finish wiring
    - Match `KNOWN_BANKS` aliases on word boundaries, case-insensitively, searching the text first and `sender_id` only if the text has no match
    - Earliest match wins and the canonical name is returned
    - Wire all extractors into `parse_sms_alert` so each runs independently of any bank layout
    - _Requirements: 3.6, 3.7, 3.8_

- [x] 7. Example tests
  - [x]* 7.1 Write example test for `N50,000.00`
    - File `tests/test_example_n_comma.py`, synthetic alert, assert `amount_kobo == 5000000` and `currency == "NGN"`
    - _Requirements: 10.1, 10.2_

  - [x]* 7.2 Write example test for `NGN50,000`
    - File `tests/test_example_ngn_no_space.py`, assert `amount_kobo == 5000000`
    - _Requirements: 10.1, 10.2_

  - [x]* 7.3 Write example test for `50,000.00 CR`
    - File `tests/test_example_cr_form.py`, assert `amount_kobo == 5000000` and `currency is None`
    - _Requirements: 10.1, 10.2, 2.6_

  - [x]* 7.4 Write example test for `NGN 50k`
    - File `tests/test_example_k_suffix.py`, assert `amount_kobo == 5000000`
    - _Requirements: 10.1, 10.2_

  - [x]* 7.5 Write example test for a multi-flag alert
    - File `tests/test_example_multi_flag.py`, phone-number sender, no balance line, `release now` text and the date `31/02/2026 10:15`
    - Assert `SENDER_ID_MISMATCH`, `BALANCE_LINE_MISSING`, `PRESSURE_LANGUAGE` and `DATE_ODD` are all in `red_flags`
    - _Requirements: 10.1, 10.3_

- [x] 8. Property tests and full run
  - [x]* 8.1 Write property test for amount round trip
    - File `tests/test_prop_amount_round_trip.py`, `@settings(max_examples=200)`, comment `# Feature: alert-parser, Property 1: Amount round trip`
    - Generate an integer from 1 to 10**13 and a random Supported_Amount_Format, building `k` forms only from exact values
    - **Property 1: Amount round trip**
    - **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.6, 2.7, 2.10, 6.5, 10.4**

  - [x]* 8.2 Write property test for totality, shape and determinism
    - File `tests/test_prop_never_raises.py`, text of 0 to 1,000 characters and sender_id None or 0 to 100 characters
    - Assert no exception, `sender_id` unchanged, unique known flags and equal results on a second call
    - **Property 2: Totality, shape and determinism**
    - **Validates: Requirements 1.1, 1.2, 1.5, 1.6, 9.3, 9.4, 9.5, 10.5**

  - [x]* 8.3 Write property test for phone-number senders
    - File `tests/test_prop_phone_sender.py`, composite strategy for `0`, `+234` and `234` prefixes with 7 to 15 digits and optional spaces or hyphens, and arbitrary text of 0 to 1,000 characters
    - Assert `SENDER_ID_MISMATCH` is in `red_flags`
    - **Property 3: Phone-number senders are flagged**
    - **Validates: Requirements 4.1, 4.5, 4.6, 10.6**

  - [x]* 8.4 Write property test for name senders
    - File `tests/test_prop_name_sender.py`, sender_id with at least one letter and arbitrary text of 0 to 1,000 characters
    - Assert `SENDER_ID_MISMATCH` is absent
    - **Property 4: Name senders are not flagged**
    - **Validates: Requirements 4.2, 4.3, 4.4, 10.7**

  - [x]* 8.5 Write property test for balance line flag and value
    - File `tests/test_prop_balance_line.py`, a Balance_Label in random letter case plus a figure in kobo, and text with no Balance_Label followed by a figure
    - Assert `BALANCE_LINE_MISSING` is absent and `available_balance_kobo` equals the figure for the first, and the flag is present for the second
    - **Property 5: Balance line decides BALANCE_LINE_MISSING**
    - **Validates: Requirements 3.4, 5.1, 5.2, 5.3, 5.4, 5.5, 10.8**

  - [x]* 8.6 Write property test for valid and invalid dates
    - File `tests/test_prop_dates.py`, date and time in each Recognised_Date_Format, with valid values and with one impossible month, day, hour, minute or second
    - Assert valid values give `alert_time` equal to the datetime (seconds 0 when omitted) with `DATE_ODD` absent, and impossible values give `alert_time` None with `DATE_ODD` present exactly once
    - **Property 6: Valid and invalid dates**
    - **Validates: Requirements 3.3, 7.1, 7.3, 7.5, 7.6, 10.9**

  - [x]* 8.7 Write property test for pressure phrases
    - File `tests/test_prop_pressure.py`, a phrase from `PRESSURE_PHRASES` with random letter case and whitespace runs, embedded as whole words and inside a longer word
    - Assert the flag is present for whole words, absent when only inside a longer word, and that adding a phrase changes no other `red_flags` entry
    - **Property 7: Pressure phrases**
    - **Validates: Requirements 8.1, 8.2, 8.3, 8.5, 8.6, 10.10**

  - [x]* 8.8 Write property test for odd amount formats
    - File `tests/test_prop_odd_amount.py`, amounts with 3 or more decimal digits, a comma group that is not 3 digits, or mixed comma and full stop separators, as the first non-balance amount
    - Assert `AMOUNT_FORMAT_ODD` is present and `amount_kobo` is None
    - **Property 8: Odd amount formats**
    - **Validates: Requirements 2.9, 6.1, 6.2, 6.3, 6.6, 10.11**

  - [x] 8.9 Run the full `pytest` suite and fix failures
    - Run a single `pytest` execution from the project root with no network, and fix any parser bug a test exposes
    - Ensure all tests pass, ask the user if questions arise.
    - _Requirements: 10.12, 10.13_

- [x] 9. TRANSFER_REQUEST_WORDING
  - [x] 9.1 Implement the detector, append the code to `RED_FLAG_CODES` and wire it in `parse_sms_alert`
    - In `src/ghost_credit/parser.py`, add `TRANSFER_REQUEST_PHRASES` (`transfer request successful`, `transfer request has been`) as a named list next to `PRESSURE_PHRASES`, plus the constants for `request successful`, `transfer` and the 40-character Near limit
    - Add `_has_transfer_request(text)`: normalise (curly quotes, case, whitespace runs) with the helper shared with `_has_pressure`, match whole words, and apply the phrase test and the proximity test
    - Append `TRANSFER_REQUEST_WORDING` as the last entry of `RED_FLAG_CODES`, after `SCREENSHOT_EDIT_SIGNS`, so the order is `SENDER_ID_MISMATCH`, `BALANCE_LINE_MISSING`, `AMOUNT_FORMAT_ODD`, `DATE_ODD`, `PRESSURE_LANGUAGE`, `SCREENSHOT_EDIT_SIGNS`, `TRANSFER_REQUEST_WORDING`
    - Wire the detector into `parse_sms_alert` and the flag collector, including the totality wrapper
    - _Requirements: 1.7, 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7, 11.8_

  - [x]* 9.2 Write example tests for `TRANSFER_REQUEST_WORDING`
    - File `tests/test_example_transfer_request.py`, synthetic alerts only
    - `Transfer Request Successful` in an alert flags it; a normal credit alert with a Balance_Line from a Bank_Sender_Name does not; curly quotes and odd whitespace such as `TRANSFER   request\tSUCCESSFUL` still flag it
    - Optional extras: 40 versus 41 characters between `request successful` and `transfer`, and `transferred` not matching
    - _Requirements: 10.14, 11.1, 11.2, 11.3, 11.4, 11.5_

  - [x]* 9.3 Write property test for the transfer request phrase
    - File `tests/test_prop_transfer_request.py`, `@settings(max_examples=200)`, comment `# Feature: alert-parser, Property 9: Transfer request phrase adds the flag exactly once`
    - Build Clean_Text lines, insert a phrase from `TRANSFER_REQUEST_PHRASES` (random case and whitespace runs) between lines at a random index, and assert the flag appears once and the other flags equal those of the Clean_Text
    - **Property 9: Transfer request phrase adds the flag exactly once**
    - **Validates: Requirements 11.1, 11.3, 11.7, 11.9, 10.15**

  - [x] 9.4 Run the full `pytest` suite and fix failures
    - Run a single `pytest` execution from the project root with `PATTERN_NETWORK=off` and no network, and confirm the original tests still pass
    - Ensure all tests pass, ask the user if questions arise.
    - _Requirements: 10.12, 10.13_

- [x] 10. Amount ignores account tokens
  - [x] 10.1 Implement account-token masking and amount ranking in `src/ghost_credit/parser.py`
    - Add `_find_account_tokens(text)` returning Account_Token spans: `_ACCOUNT_RE` matches, digit runs adjacent to `*` (with the asterisks), and an `Acct`, `A/C` or `Account` label (case-insensitive, optional colon and whitespace) with the digit and asterisk run after it
    - In `_parse_body`, pass the Balance_Line spans plus the Account_Token spans to `_extract_amount` as one `masked_spans` list (rename the `balance_spans` parameter)
    - Add `_AMOUNT_LABEL_RE` for a number after `Amt` or `Amount` with no Currency_Marker, as a candidate with `has_marker` False, dropped when it overlaps a marker candidate
    - In `_extract_amount`, let the first marker or label candidate decide `amount_kobo`, and use the CR-form candidate only when there is none
    - Leave `account_masked`, the date masks, kobo integer arithmetic and the odd-format rules unchanged
    - _Requirements: 2.11, 2.12, 2.13, 2.14, 2.15, 2.16_

  - [x]* 10.2 Write example test for the account-token bug
    - File `tests/test_example_account_token.py`: `parse_sms_alert("Acct:012****789 CR Amt: NGN 45,000.00", "GTBank")` gives `amount_kobo == 4500000`
    - _Requirements: 2.12, 10.16_

  - [x]* 10.3 Write property test for account line before the amount
    - File `tests/test_prop_account_token.py`, `@settings(max_examples=200)`, comment `# Feature: alert-parser, Property 10: Account line never changes the amount`
    - Generate an account line (`Acct`, `A/C` or `Account` label in random case, optional colon, any digits around 1 to 6 asterisks) and an amount line, put the account line first, and assert `amount_kobo` equals that of the amount text alone
    - **Property 10: Account line never changes the amount**
    - **Validates: Requirements 2.11, 2.14, 2.15, 10.17**

  - [x] 10.4 Run the full `pytest` suite and fix failures
    - Run a single `pytest` execution from the project root with `PATTERN_NETWORK=off` and no network, and confirm all earlier tests still pass
    - Ensure all tests pass, ask the user if questions arise.
    - _Requirements: 2.16, 10.12, 10.13_

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP. Requirement 10 expects all 5 example tests and all 8 property tests to exist, so skip them only deliberately.
- Each test lives in its own file so the 5 examples and 8 properties can run in parallel without file conflicts.
- The 10,000-character timing limit (Requirement 9.6) and bank matching (Requirement 3.6) have no automated test. The design uses bounded regexes with no nested quantifiers.
- All parser tasks edit `src/ghost_credit/parser.py`, so they run in separate waves.
- Task 9 is an addition made after the original build. The earlier limit of 8 tasks applied to the original build only.
- Task 10 is an addition (a bug fix for amounts read from account numbers). It keeps tasks 1 to 9 and their numbers unchanged.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["2.1"] },
    { "id": 2, "tasks": ["3.1"] },
    { "id": 3, "tasks": ["3.2"] },
    { "id": 4, "tasks": ["3.3"] },
    { "id": 5, "tasks": ["4.1"] },
    { "id": 6, "tasks": ["4.2"] },
    { "id": 7, "tasks": ["6.1"] },
    { "id": 8, "tasks": ["5.1"] },
    { "id": 9, "tasks": ["6.2"] },
    { "id": 10, "tasks": ["7.1", "7.2", "7.3", "7.4", "7.5", "8.1", "8.2", "8.3", "8.4", "8.5", "8.6", "8.7", "8.8"] },
    { "id": 11, "tasks": ["8.9"] },
    { "id": 12, "tasks": ["9.1"] },
    { "id": 13, "tasks": ["9.2", "9.3"] },
    { "id": 14, "tasks": ["9.4"] },
    { "id": 15, "tasks": ["10.1"] },
    { "id": 16, "tasks": ["10.2", "10.3"] },
    { "id": 17, "tasks": ["10.4"] }
  ]
}
```
