# Implementation Plan: Verdict Engine

## Overview

This plan builds `src/ghost_credit/verdict_engine.py` in Python, following the design's suggested implementation order: constants and `PaystackResult`, normalising helpers and reasons, `decide`, `Explainer` and `FakeExplainer`, `build_reply`, then tests and smoke checks. Tests use pytest and Hypothesis, matching the existing `tests/` files.

**Dependency:** this spec depends on the pattern-network-hook spec. `src/ghost_credit/pattern_network.py` (providing `Verdict` and `LookupResult`) must exist before task 1 starts. `ParsedAlert` and `RED_FLAG_CODES` already exist in `src/ghost_credit/parser.py`.

No AI model, client or call is added anywhere in this plan.

## Tasks

- [ ] 1. Create the module skeleton and PaystackResult
  - [ ] 1.1 Create `src/ghost_credit/verdict_engine.py` with imports, constants and PaystackResult
    - Import `Verdict` and `LookupResult` from `pattern_network.py` and `ParsedAlert` from `parser.py`; do not redefine them
    - Add constants `PAYSTACK_NOT_APPLICABLE`, `PAYSTACK_MATCHED`, `PAYSTACK_NOT_FOUND`, `CHECK_REMINDER` and the four verdict code strings
    - Add frozen dataclass `PaystackResult` with one field `state`; raise `ValueError` naming `state` for any other value
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 9.2, 9.4_

  - [ ]* 1.2 Write unit tests for PaystackResult
    - Accepts the three states, rejects another with `ValueError`, and is frozen
    - Use synthetic data only
    - _Requirements: 5.1, 5.2, 8.6_

- [ ] 2. Add normalising helpers and reason builders
  - [ ] 2.1 Implement `_state_of`, `_flags_of`, `_is_network_match` and the reason builders
    - `_state_of`: None, wrong type or unknown state gives `not_applicable`
    - `_flags_of`: None, missing attribute or non-list gives `[]`; return a new list
    - `_is_network_match`: True only when `network_available is True` and `matched is True`
    - Reason texts as in the design table; flag reason uses prefix `"Flags: "` with `","` separators, deduplicated and cut at 120 characters
    - _Requirements: 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 4.4, 4.5, 4.6, 4.7_

- [ ] 3. Implement `decide`
  - [ ] 3.1 Implement `decide(parsed, paystack_result, lookup_result)`
    - Apply the rule chain in order: matched, not_found, flags, network match, otherwise UNVERIFIED
    - Set `decided_by="rules"`, `owner_outcome="unknown"`, `paystack_checked` True only for matched and not_found
    - Wrap in one try/except that returns the fallback UNVERIFIED Verdict with reason "The check could not be completed."
    - No network, file, clock, random or AI calls
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, 2.5, 3.1, 3.2, 3.3, 4.1, 4.2, 4.3, 4.8_

  - [ ]* 3.2 Write property test for the rule table
    - File `tests/test_prop_verdict_rule_table.py`
    - **Property 1: Verdict code follows the rule table**
    - **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3**

  - [ ]* 3.3 Write property test that only Paystack can confirm
    - File `tests/test_prop_verdict_only_paystack_confirms.py`
    - **Property 2: Only Paystack can confirm**
    - Covers the required checks: not `matched` never gives CONFIRMED, and `matched` always gives CONFIRMED
    - **Validates: Requirements 2.4, 8.1, 8.2**

  - [ ]* 3.4 Write property test for an unavailable network
    - File `tests/test_prop_verdict_network_unavailable.py`
    - **Property 3: An unavailable network equals no network**
    - **Validates: Requirements 2.5**

  - [ ]* 3.5 Write property test for Verdict fields and reasons
    - File `tests/test_prop_verdict_fields.py`
    - **Property 4: Verdict fields and reasons are well formed**
    - Draw flag codes from the parser's `RED_FLAG_CODES`
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.4**

  - [ ]* 3.6 Write property test that reasons explain the verdict
    - File `tests/test_prop_verdict_reasons.py`
    - **Property 5: Reasons explain the verdict**
    - **Validates: Requirements 3.5, 3.6, 3.7, 3.8, 3.9**

  - [ ]* 3.7 Write property test for determinism and unchanged arguments
    - File `tests/test_prop_verdict_pure.py`
    - **Property 6: Decide is deterministic and leaves arguments unchanged**
    - **Validates: Requirements 4.2, 4.7**

  - [ ]* 3.8 Write property test for totality on junk input
    - File `tests/test_prop_verdict_total.py`
    - **Property 7: Decide is total and treats junk as defaults**
    - Include the check that code is one of four values and `decided_by` equals `"rules"` for any input including None
    - **Validates: Requirements 4.3, 4.4, 4.5, 4.6, 8.3**

  - [ ]* 3.9 Write example tests for the four rules and the network upgrade
    - File `tests/test_example_verdict_rules.py`
    - One example each for rules 1 to 4, one example where a Network_Match turns UNVERIFIED into SUSPICIOUS
    - Fallback Verdict forced by a `red_flags` object that raises when iterated
    - All six parser codes together give a reason of 120 characters or fewer
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 3.5, 4.8, 8.4_

- [ ] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Add Explainer and FakeExplainer
  - [ ] 5.1 Implement the `Explainer` abstract base class and `FakeExplainer`
    - `Explainer.explain(verdict, parsed) -> str` as an `abc.ABC` method
    - `FakeExplainer` returns a fixed string built from `verdict.code` and `verdict.reasons`; no external call, no reminder
    - _Requirements: 6.1, 6.2, 6.3_

- [ ] 6. Implement `build_reply`
  - [ ] 6.1 Implement `build_reply(verdict, parsed, explainer)`
    - Call the explainer inside try/except; on error, non-string or whitespace-only text, use `verdict.reasons` joined by a single space
    - CONFIRMED returns the text unchanged; any other code strips trailing whitespace and appends `CHECK_REMINDER` unless the text already ends with it
    - Never change the Verdict
    - _Requirements: 6.4, 6.5, 6.6, 7.1, 7.2, 7.3, 7.4_

  - [ ]* 6.2 Write property test for reply building and bad Explainers
    - File `tests/test_prop_reply_explainers.py`
    - **Property 8: Reply building never changes the verdict and survives bad Explainers**
    - **Validates: Requirements 6.2, 6.4, 6.5, 6.6**

  - [ ]* 6.3 Write property test for the Check_Reminder
    - File `tests/test_prop_reply_reminder.py`
    - **Property 9: Unconfirmed replies end with the reminder exactly once at the end**
    - Use FakeExplainer and an Explainer that returns arbitrary text
    - **Validates: Requirements 7.1, 7.2, 7.3, 7.4, 8.5**

  - [ ]* 6.4 Write property test for idempotence
    - File `tests/test_prop_reply_idempotent.py`
    - **Property 10: Reply building is idempotent**
    - **Validates: Requirements 7.5**

- [ ] 7. Add smoke checks and run the full suite
  - [ ]* 7.1 Write smoke tests for project conventions
    - File `tests/test_smoke_verdict_engine.py`
    - Module imports `Verdict`, `LookupResult` and `ParsedAlert` from their modules and defines none of them
    - Source text holds no AI model name, AI client import, HTTP library or secret
    - _Requirements: 6.3, 9.1, 9.2, 9.4_

- [ ] 8. Final checkpoint - Ensure all tests pass
  - Run the full suite with `PATTERN_NETWORK` unset. Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP.
- Each task references specific requirements for traceability.
- Property tests validate the universal properties in the design; example and smoke tests cover specific cases.
- Every test file uses synthetic data and makes no AI or network call.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "2.1"] },
    { "id": 2, "tasks": ["3.1"] },
    { "id": 3, "tasks": ["3.2", "3.3", "3.4", "3.5", "3.6", "3.7", "3.8", "3.9"] },
    { "id": 4, "tasks": ["5.1"] },
    { "id": 5, "tasks": ["6.1"] },
    { "id": 6, "tasks": ["6.2", "6.3", "6.4", "7.1"] }
  ]
}
```
