# Implementation Plan: Verdict Engine

## Overview

This plan builds `src/ghost_credit/verdict.py` in Python 3.11 or newer, following the order in the design's "Suggested Implementation Order": module skeleton and Paystack mapping, `decide` and reasons, risk notes, `Decision` and `decide_with_notes`, the Explainers, `build_reply`, then a final checkpoint. Tests use pytest and Hypothesis. Each of the 20 correctness properties in the design is its own test file, named `tests/test_verdict_prop_NN_<name>.py`, and each carries the tag `Feature: verdict-engine, Property N: <property text>` and runs at least 100 examples. Example tests and smoke checks live in separate files.

**Dependencies that must exist before task 1 starts:**

- `src/ghost_credit/pattern_network.py` from the pattern-network-hook spec, which provides `Verdict` and `LookupResult`.
- The `TRANSFER_REQUEST_WORDING` flag appended as the last entry of `RED_FLAG_CODES` in `src/ghost_credit/parser.py`, which is alert-parser task 9.

`ParsedAlert` comes from `src/ghost_credit/parser.py`, and `PaystackResult` is the existing dataclass in `src/ghost_credit/paystack.py`. This plan imports all four types and defines none of them.

The stale docstring in `src/ghost_credit/paystack.py` that mentions a verdict-engine `PaystackResult` is fixed in task 1 (task 1.2, a one-line docstring change only, no code change).

No AI model, client or call is added anywhere in this plan. All tests use synthetic data, no secrets and no network, and pass with `PATTERN_NETWORK=off`.

## Tasks

- [x] 1. Create the module skeleton, Paystack mapping and shared test helpers
  - [x] 1.1 Create `src/ghost_credit/verdict.py` with imports, constants and the first helpers
    - Import `Verdict` and `LookupResult` from `ghost_credit.pattern_network`, `ParsedAlert` from `ghost_credit.parser` and `PaystackResult` plus its status strings from `ghost_credit.paystack`; define none of them
    - Add the four code constants, `CHECK_REMINDER`, `MAX_REASON_LENGTH` (120), `DEFAULT_LARGE_AMOUNT_KOBO` (50000000) and the owner labels table
    - Add `_paystack_state` (returns `confirmed`, `no_match` or `no_check`; `checked` compared with `is True`), `_flags_of` (always a new list), `_is_network_match` and `_cut`
    - Small functions with type hints and short plain-English docstrings
    - _Requirements: 1.6, 2.5, 3.5, 4.4, 4.5, 4.6, 9.4_

  - [x] 1.2 Fix the stale docstring in `src/ghost_credit/paystack.py`
    - Change only the sentence that says the verdict-engine has its own `PaystackResult`, so it says the verdict engine imports this `PaystackResult`
    - One-line docstring change only; no code, import or behaviour change
    - _Requirements: 9.4_

  - [x]* 1.3 Create shared test helpers in `tests/verdict_helpers.py`
    - Hypothesis strategies for `red_flags` (known codes including `TRANSFER_REQUEST_WORDING`, arbitrary text, long strings, non-strings), Paystack input (`CONFIRMED`, `NOT_FOUND` with `checked` True and False, `UNAVAILABLE`, unknown status, None, junk objects), LookupResult (two booleans, None, junk) and a small `ParsedAlert` builder
    - Synthetic data only; each property file adds its own extra strategies and does not edit this file
    - _Requirements: 8.12_

  - [x]* 1.4 Write example tests for the Paystack mapping in `tests/test_verdict_paystack_mapping_examples.py`
    - `NOT_FOUND` with `checked` False, `UNAVAILABLE`, None and an unreadable value each map to no check
    - `NOT_FOUND` with `checked` True maps to no match, and a hand-built `CONFIRMED` with `checked` False maps to confirmed
    - _Requirements: 8.8, 4.4_

- [x] 2. Implement `decide` and the reasons
  - [x] 2.1 Add the flag sentence table, reason builders, `decide` and the fallback Verdict to `verdict.py`
    - Apply the rule chain in order: confirmed, no match, red flags, network match, otherwise UNVERIFIED
    - Fill `decided_by="rules"`, `owner_outcome="unknown"` and `paystack_checked` as in the design; pass every reason through `_cut`; never leave `reasons` empty
    - One reason per `red_flags` entry from the fixed sentence table, with a generic sentence for unknown or non-string entries
    - One outer try/except returns UNVERIFIED with the reason "The check could not be completed."
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.1, 2.2, 2.3, 2.4, 2.5, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10, 3.11, 4.1, 4.2, 4.3, 4.7, 4.8_

  - [x]* 2.2 Write example tests for the rules in `tests/test_verdict_rules_examples.py`
    - One example for each of rules 1 to 4, and one example for a Network_Match turning UNVERIFIED into SUSPICIOUS
    - Fallback Verdict forced by a `red_flags` object that raises when copied
    - _Requirements: 8.7, 4.8_

  - [x]* 2.3 Write property test for the rule table in `tests/test_verdict_prop_01_rule_table.py`
    - **Property 1: Verdict code follows the rule table**
    - **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.1**

  - [x]* 2.4 Write property test in `tests/test_verdict_prop_02_paystack_beats_network.py`
    - **Property 2: A Paystack result beats the network**
    - **Validates: Requirements 2.2, 2.3, 8.2**

  - [x]* 2.5 Write property test in `tests/test_verdict_prop_03_only_paystack_confirms.py`
    - **Property 3: Only Paystack can confirm**
    - **Validates: Requirements 2.4, 8.1**

  - [x]* 2.6 Write property test in `tests/test_verdict_prop_04_screenshot_never_confirms.py`
    - **Property 4: A screenshot never confirms by itself**
    - **Validates: Requirements 2.4, 8.3**

  - [x]* 2.7 Write property test in `tests/test_verdict_prop_05_network_unavailable.py`
    - **Property 5: An unavailable network equals no network**
    - **Validates: Requirements 2.5**

  - [x]* 2.8 Write property test in `tests/test_verdict_prop_06_fixed_fields.py`
    - **Property 6: Verdict fields are fixed by the rules**
    - **Validates: Requirements 3.1, 3.2, 3.3**

  - [x]* 2.9 Write property test in `tests/test_verdict_prop_07_reason_length.py`
    - **Property 7: Every reason is 1 to 120 characters**
    - **Validates: Requirements 3.4, 3.5, 8.6**

  - [x]* 2.10 Write property test in `tests/test_verdict_prop_08_reasons_content.py`
    - **Property 8: Reasons explain the verdict and hold no notes**
    - **Validates: Requirements 3.6, 3.7, 3.8, 3.9, 3.10, 3.11**

  - [x]* 2.11 Write property test in `tests/test_verdict_prop_09_deterministic.py`
    - **Property 9: Decide is deterministic and leaves arguments unchanged**
    - **Validates: Requirements 4.2, 4.7**

  - [x]* 2.12 Write property test in `tests/test_verdict_prop_10_total.py`
    - **Property 10: Decide is total and treats junk as defaults**
    - **Validates: Requirements 4.3, 4.4, 4.5, 4.6, 4.8, 8.5**

- [x] 3. Implement the risk notes
  - [x] 3.1 Add `COLLECTION_TERMS`, `_normalise_text`, the Lagos time helper, `_threshold` and `risk_notes` to `verdict.py`
    - `_LAGOS = timezone(timedelta(hours=1))`; a naive `alert_time` is Lagos time, an aware one is converted with `astimezone`
    - Notes in the fixed order Friday-or-weekend (Friday at 14:00 or later, Saturday, Sunday), large amount (integer `>=` threshold, bools rejected, default 50000000), collection word (whole-word regex after curly-quote, lower-case and whitespace normalisation)
    - Keyword-only `alert_text` and `large_amount_kobo`; each note at most once; return `[]` on any error; never change `parsed`; no floats for money
    - _Requirements: 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9, 5.10, 5.11, 5.12, 5.13, 9.3_

  - [x]* 3.2 Write example tests for each risk note in `tests/test_verdict_risk_notes_examples.py`
    - Friday 13:59 (no note), Friday 14:00 (note), Saturday, Sunday, an aware `alert_time` in another offset that falls on a different weekday in Lagos
    - An amount one kobo below and exactly at the threshold, and an `alert_text` with curly quotes and mixed letter case
    - _Requirements: 8.9, 5.3, 5.4, 5.5, 5.6_

  - [x]* 3.3 Write property test in `tests/test_verdict_prop_12_friday_weekend_note.py`
    - **Property 12: Friday and weekend note follows Lagos time**
    - **Validates: Requirements 5.3, 5.10**

  - [x]* 3.4 Write property test in `tests/test_verdict_prop_13_large_amount_note.py`
    - **Property 13: Large amount note follows an integer threshold**
    - **Validates: Requirements 5.4, 5.8, 5.9, 5.10**

  - [x]* 3.5 Write property test in `tests/test_verdict_prop_14_collection_note.py`
    - **Property 14: Collection note follows whole-word matching**
    - **Validates: Requirements 5.5, 5.6, 5.7**

  - [x]* 3.6 Write property test in `tests/test_verdict_prop_15_note_list.py`
    - **Property 15: The note list is ordered, unique and safe**
    - **Validates: Requirements 5.11, 5.12, 5.13**

- [x] 4. Add Decision and decide_with_notes
  - [x] 4.1 Add the frozen `Decision` dataclass and `decide_with_notes` to `verdict.py`
    - `Decision` holds `verdict` and `risk_notes` (a list)
    - `decide_with_notes` calls `decide` once and `risk_notes` once, shares no state between them, and returns `Decision`
    - _Requirements: 5.1, 5.2_

  - [x]* 4.2 Write property test in `tests/test_verdict_prop_11_notes_keep_verdict.py`
    - **Property 11: Notes never change the verdict or the red flags**
    - **Validates: Requirements 5.1, 5.2, 8.4**

  - [x]* 4.3 Write example test for Decision in `tests/test_verdict_decision_example.py`
    - `Decision` is frozen, holds the verdict and the notes, and its verdict equals the `decide` result
    - _Requirements: 5.1, 5.2_

- [x] 5. Implement the Explainers
  - [x] 5.1 Add `Explainer` (abstract), `FakeExplainer` and `TemplateExplainer` to `verdict.py`
    - `Explainer` is an `abc.ABC` with `explain(verdict, parsed, risk_notes) -> str`
    - `FakeExplainer` returns a fixed string built only from the code, reasons and notes, with no external call
    - `TemplateExplainer` uses the fixed headline per code (unknown code uses the UNVERIFIED headline), a "Why:" list of at most 3 reasons, then every Risk_Note, then the Check_Reminder as the last line for every code except CONFIRMED; no code names, no accusation of a customer, no AI or network call
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8_

  - [x]* 5.2 Write example tests for TemplateExplainer in `tests/test_verdict_template_examples.py`
    - One example for each of the four codes: Owner_Label first, at most 3 reasons, notes after the reasons and before the reminder, no network or AI call
    - _Requirements: 8.11, 6.3, 6.4, 6.5_

  - [x]* 5.3 Write property test in `tests/test_verdict_prop_16_template_text.py`
    - **Property 16: TemplateExplainer text is short, plain and ordered**
    - **Validates: Requirements 6.3, 6.4, 6.5, 6.6**

  - [x]* 5.4 Write property test in `tests/test_verdict_prop_17_fake_explainer.py`
    - **Property 17: FakeExplainer is deterministic**
    - **Validates: Requirements 6.7**

- [x] 6. Implement build_reply and the smoke checks
  - [x] 6.1 Add `build_reply(verdict, parsed, explainer, risk_notes=None)` to `verdict.py`
    - Read the code once from the original Verdict; call the Explainer with a deep copy of the Verdict and a copy of the notes inside try/except
    - On an error, a non-string or blank text, build the fallback from the reasons joined with a single space, then each Risk_Note
    - CONFIRMED returns the text unchanged; any other or unreadable code strips trailing whitespace and appends the Check_Reminder on a new line unless the text already ends with it
    - _Requirements: 6.9, 6.10, 6.11, 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

  - [x]* 6.2 Write example tests for replies in `tests/test_verdict_reply_examples.py`
    - A reply for each code ends as expected: reminder last for NOT_FOUND, SUSPICIOUS and UNVERIFIED, none added for CONFIRMED
    - Failing Explainer falls back to the reasons and notes
    - _Requirements: 7.2, 7.4, 6.11_

  - [x]* 6.3 Write property test in `tests/test_verdict_prop_18_reply_survives_bad_explainers.py`
    - **Property 18: build_reply keeps the verdict and survives bad Explainers**
    - **Validates: Requirements 6.9, 6.10, 6.11**

  - [x]* 6.4 Write property test in `tests/test_verdict_prop_19_reminder_enforced.py`
    - **Property 19: Replies for unconfirmed verdicts end with the reminder**
    - **Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5, 8.10**

  - [x]* 6.5 Write property test in `tests/test_verdict_prop_20_reply_idempotent.py`
    - **Property 20: Reply building is idempotent**
    - **Validates: Requirements 7.6**

  - [x]* 6.6 Write smoke checks in `tests/test_verdict_smoke.py`
    - The module imports `Verdict`, `LookupResult`, `ParsedAlert` and `PaystackResult` from their modules and defines none of them
    - The source holds no AI model name, AI client import, HTTP library, socket, `open(` call, clock or random import, and no secret
    - `Explainer` is abstract and exposes `explain(verdict, parsed, risk_notes)`
    - _Requirements: 4.1, 6.1, 6.8, 9.1, 9.2, 9.4_

- [x] 7. Final checkpoint - Ensure all tests pass
  - Run the full test suite with `PATTERN_NETWORK=off` and fix any failure
  - Ensure all tests pass, ask the user if questions arise.
  - _Requirements: 8.12_

## Notes

- Tasks marked with `*` are optional test sub-tasks and can be skipped for a faster MVP; this plan includes all of them.
- Each property has its own test file and its own task, tagged with its property number and the requirements it checks.
- Only `verdict.py` is edited by tasks 1.1, 2.1, 3.1, 4.1, 5.1 and 6.1, and they sit in separate waves.
- Task 1.2 changes one docstring line in `paystack.py` and nothing else.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.3"] },
    { "id": 1, "tasks": ["1.4", "2.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "2.4", "2.5", "2.6", "2.7", "2.8", "2.9", "2.10", "2.11", "2.12"] },
    { "id": 3, "tasks": ["3.1"] },
    { "id": 4, "tasks": ["3.2", "3.3", "3.4", "3.5", "3.6", "4.1"] },
    { "id": 5, "tasks": ["4.2", "4.3", "5.1"] },
    { "id": 6, "tasks": ["5.2", "5.3", "5.4", "6.1"] },
    { "id": 7, "tasks": ["6.2", "6.3", "6.4", "6.5", "6.6"] }
  ]
}
```
