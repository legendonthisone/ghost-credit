# Implementation Plan: paystack-verifier

## Overview

Build `src/ghost_credit/paystack.py` in small steps that follow the design's suggested implementation order. Each step adds a few pure helpers to `verify`, then tests them offline. Every test passes a fake Http_Function through `http=`, uses synthetic data, and builds Fake_Keys from two or more string pieces (for example `"sk_" + "test_" + "abc"`). Python 3.11+, standard library only, Hypothesis for properties (at least 100 examples each). `scripts/paystack_smoke.py` is not part of this plan.

## Tasks

- [x] 1. Create the module skeleton, shared test fakes, and the key and amount checks
  - [x] 1.1 Create `src/ghost_credit/paystack.py` with the result type, reasons and key/amount checks
    - Define the frozen `PaystackResult`, the `HttpFunction` type alias, the fixed reason constants, and the `_unavailable`, `_not_found` and `_confirmed` constructors
    - Import `ParsedAlert` from `src/ghost_credit/parser.py` without redefining it
    - Add `verify` with an outer `try/except Exception` returning `UNAVAILABLE` with `could not check Paystack`
    - Add `_key_problem`, `_is_int_amount` and `_usable_reference`. Check the key before reading any `parsed` field, using `getattr(..., None)`
    - Return `NOT_FOUND` unchecked for an unreadable amount, with no call
    - Create `tests/paystack_fakes.py` with a recording fake Http_Function (captures url, headers, timeout), a fake-key builder, and a ParsedAlert builder
    - Add short plain-English docstrings and type hints to every function
    - _Requirements: 1.1, 1.2, 1.4, 1.5, 1.6, 1.7, 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 6.6, 9.1, 9.3, 9.5, 9.6_

  - [x]* 1.2 Write property test for key handling
    - **Property 4: Only test keys reach Paystack**
    - Put it in `tests/test_prop_paystack_keys.py`
    - **Validates: Requirements 2.1, 2.2, 2.3**

  - [x]* 1.3 Write property test for unreadable amounts
    - **Property 6: Unreadable amounts make no call**
    - Put it in `tests/test_prop_paystack_amount.py`
    - **Validates: Requirements 3.1, 3.2**

  - [x]* 1.4 Write example tests for missing key, non-test key and unreadable amount
    - Check the exact status, `checked` value and reason string, and that the fake is never called
    - Put them in `tests/test_example_paystack_guards.py`
    - _Requirements: 2.1, 2.2, 3.1, 8.8_

- [x] 2. Add the time helpers
  - [x] 2.1 Add `_to_lagos`, `_search_window` and `_iso` to `paystack.py`
    - A naive datetime is Lagos time. An aware datetime is converted to `+01:00` before minutes are added or subtracted
    - With an alert time: `from` is 30 minutes before and `to` is 5 minutes after. Without one: `from` is 60 minutes before `now` and `to` is `now`
    - Write times as ISO 8601 with `+01:00`, for example `2026-11-20T10:02:11+01:00`
    - _Requirements: 5.2, 5.3, 5.4, 5.5, 9.2_

  - [x]* 2.2 Write property test for the search window
    - **Property 8: Search window**
    - Put it in `tests/test_prop_paystack_window.py`
    - **Validates: Requirements 5.2, 5.3, 5.4, 5.5, 9.2**

  - [x]* 2.3 Write example tests for naive and aware `alert_time`
    - Check one naive and one aware (for example UTC) alert time against the expected `from` and `to` text
    - Put them in `tests/test_example_paystack_window.py`
    - _Requirements: 5.2, 5.4, 5.5, 8.8_

- [x] 3. Add the request builders, the single http call and the default http function
  - [x] 3.1 Add `_verify_request`, `_list_request` and `default_http`, and make `verify` call `http` once
    - Verify URL uses `urllib.parse.quote(reference, safe="")`. List URL uses `urllib.parse.urlencode` with `status=success`, `from`, `to` and `perPage=100`
    - Send `Authorization: Bearer <key>` as the only place the key appears, with a 5-second timeout
    - Use the reference path when `_usable_reference` returns a value, otherwise the search path
    - `default_http` uses only `urllib.request`, returns `(status, body)`, and returns the code and body of an `HTTPError`. `http=None` selects it
    - Make at most one call and no retry
    - _Requirements: 1.3, 2.5, 4.1, 4.2, 4.7, 5.1, 6.4, 6.5, 9.3_

  - [x]* 3.2 Write property test for request building
    - **Property 7: Request building**
    - Put it in `tests/test_prop_paystack_request.py`
    - **Validates: Requirements 4.1, 4.2, 4.7, 5.1, 6.5**

  - [x]* 3.3 Write property test that the key never leaks
    - **Property 5: The key never leaks**
    - Capture log output with `caplog` and check the `repr` of the result and the recorded URL
    - Put it in `tests/test_prop_paystack_key_leak.py`
    - **Validates: Requirements 2.4, 2.5, 4.2, 8.9**

  - [x]* 3.4 Write example test for the exact recorded URL and Authorization header
    - Cover one reference request and one search request
    - Put it in `tests/test_example_paystack_request.py`
    - _Requirements: 4.1, 4.2, 5.1, 8.8_

- [x] 4. Add body parsing and the failure paths
  - [x] 4.1 Add `_parse_body` and the failure handling in `verify`
    - An exception from the Http_Function gives `UNAVAILABLE` with `could not reach Paystack`. A wrong-shaped return value gives the same result
    - A status other than 200 gives `UNAVAILABLE` with `Paystack did not answer normally`
    - A 200 body that is not UTF-8 JSON, not an object, or lacks a `data` field of the right type gives `UNAVAILABLE` with `Paystack reply could not be read`
    - All three results are unchecked and put no text from Paystack or exceptions in the reason
    - _Requirements: 6.1, 6.2, 6.3, 7.1, 7.6_

  - [x]* 4.2 Write property test for failures
    - **Property 11: Failures give UNAVAILABLE and are not confirmed**
    - Put it in `tests/test_prop_paystack_failures.py`
    - **Validates: Requirements 6.1, 6.2, 6.3**

  - [x]* 4.3 Write example tests for timeout, non-200 and malformed JSON
    - Use recorded fake bodies. Include a 404 from the verify endpoint
    - Put them in `tests/test_example_paystack_failures.py`
    - _Requirements: 6.1, 6.2, 6.3, 8.8_

- [x] 5. Add transaction matching and the reference decision
  - [x] 5.1 Add `_is_match`, `_parse_paid_at` and `_decide_by_reference`
    - A Matching_Transaction is a dict whose `status` is `"success"`, whose `currency` is `"NGN"` and whose `amount` is an int (not a bool) equal to the alert amount
    - A matching reference check returns `CONFIRMED` checked, with `matched_reference` set to the claimed reference and `amount_kobo` set to the matched amount
    - Any other readable reference reply returns `NOT_FOUND` checked with `Paystack has no matching payment`
    - Parse `paid_at` to a Lagos datetime, or None when missing or unreadable, keeping `CONFIRMED`
    - Read only the fields `data`, `status`, `amount`, `currency`, `reference` and `paid_at`
    - _Requirements: 4.3, 4.4, 4.5, 4.6, 7.1, 7.2, 7.3, 7.4, 7.5_

  - [x]* 5.2 Write property test for a matching reference payment
    - **Property 9: A matching reference payment is confirmed**
    - Put it in `tests/test_prop_paystack_reference.py`
    - **Validates: Requirements 4.3, 4.4**

  - [x]* 5.3 Write property test for paid_at handling
    - **Property 12: paid_at handling**
    - Put it in `tests/test_prop_paystack_paid_at.py`
    - **Validates: Requirements 7.3, 7.4**

  - [x]* 5.4 Write example tests for a confirmed reference check and a non-NGN currency
    - Use a recorded fake verify response for each. Also check that a bool amount is not confirmed
    - Put them in `tests/test_example_paystack_reference.py`
    - _Requirements: 4.3, 4.4, 4.5, 4.6, 8.8_

- [x] 6. Add the search decision
  - [x] 6.1 Add `_decide_by_search` and wire it into `verify`
    - Skip list items that are not JSON objects
    - Exactly one Matching_Transaction and fewer than 100 items gives `CONFIRMED`. `matched_reference` is the transaction `reference` when it is a string, otherwise None
    - Zero matches gives `NOT_FOUND` checked with `Paystack has no matching payment`
    - Two or more matches, or 100 items with at least one match, gives `NOT_FOUND` checked with `more than one payment of this amount, check manually`
    - _Requirements: 5.6, 5.7, 5.8, 5.9, 5.10, 5.11, 7.1, 7.2_

  - [x]* 6.2 Write property test for the search outcome
    - **Property 10: Search outcome depends on the match count**
    - Put it in `tests/test_prop_paystack_search.py`
    - **Validates: Requirements 5.6, 5.7, 5.8, 5.9, 5.10, 5.11, 4.5**

  - [x]* 6.3 Write example tests for the search cases
    - Cover a confirmed search with one match, zero matches, two matches, a full page of 100 with one match, and a non-object item in `data`
    - Put them in `tests/test_example_paystack_search.py`
    - _Requirements: 5.6, 5.8, 5.9, 5.10, 5.11, 8.8_

- [x] 7. Add the cross-cutting property tests
  - [x]* 7.1 Write property test that `verify` never raises
    - **Property 1: Never raises, always a valid result**
    - Generate ParsedAlert-like objects with None fields, non-ParsedAlert objects, any key including None and non-strings, any `now` including non-datetimes, and fake Http_Functions that raise or return arbitrary bytes, status codes or wrong shapes
    - Put it in `tests/test_prop_paystack_never_raises.py`
    - **Validates: Requirements 1.4, 1.5, 1.6, 6.6, 8.5**

  - [x]* 7.2 Write property test that a mismatched amount is never confirmed
    - **Property 2: A mismatched amount is never confirmed**
    - Include float, string and bool amounts, in both verify and list form
    - Put it in `tests/test_prop_paystack_amount_mismatch.py`
    - **Validates: Requirements 4.6, 5.11, 7.5, 8.6**

  - [x]* 7.3 Write property test that a non-success status is never confirmed
    - **Property 3: A non-success status is never confirmed**
    - Put it in `tests/test_prop_paystack_status.py`
    - **Validates: Requirements 5.11, 7.5, 8.7**

  - [x]* 7.4 Write property test that CONFIRMED needs every condition
    - **Property 13: CONFIRMED needs every condition**
    - Put it in `tests/test_prop_paystack_confirmed.py`
    - **Validates: Requirements 7.5**

  - [x]* 7.5 Write property test that reasons are fixed strings
    - **Property 14: Reasons are fixed strings**
    - Put arbitrary text in every response field and check the reason is one of the constants
    - Put it in `tests/test_prop_paystack_reasons.py`
    - **Validates: Requirements 7.6, 1.5**

- [x] 8. Add smoke checks and run the whole suite
  - [x]* 8.1 Write smoke tests for module conventions
    - Check that `http=None` selects `default_http`, that `paystack.py` imports `ParsedAlert` from `parser.py`, that the module imports only the standard library, and that `PATTERN_NETWORK` is `off` during the run
    - Do not call `default_http`. Run `tests/test_example_screenshot_secrets.py` as part of the suite to confirm no key-like literal appears
    - Put them in `tests/test_example_paystack_smoke.py`
    - _Requirements: 1.3, 1.7, 6.4, 8.1, 8.2, 8.3, 8.4, 9.3, 9.4, 9.5_

  - [x] 8.2 Checkpoint - Ensure all tests pass
    - Ensure all tests pass with `PATTERN_NETWORK=off`, ask the user if questions arise.

- [x] 9. Already-used payments (addition after the original plan)
  - This task group is an addition. It also holds the matching changes in `verdict.py` and `pipeline.py`, so one change can be built and tested in one place. The related requirements are verdict-engine Requirement 3.12 and check-pipeline Requirement 10.
  - [x] 9.1 Implement the already-used rule in `src/ghost_credit/paystack.py`
    - Add the constant `REASON_ALREADY_USED = "This payment was already used for an earlier check"`
    - Add the keyword-only parameter `is_used: Callable[[str], bool] | None = None` to `verify`, after `http`
    - Add `_apply_used_rule(result, is_used)`: with `is_used` None or a non-string `matched_reference`, return the result unchanged; call `is_used(reference)` once inside try/except; exactly `True` gives `NOT_FOUND` checked with `matched_reference` set and the constant reason; exactly `False` returns the result unchanged; a raise or any other value gives `UNAVAILABLE` unchecked with `could not check Paystack`
    - Pass the `CONFIRMED` result of `_decide_by_reference` and `_decide_by_search` through it. Change nothing else in those functions
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8, 10.9, 10.10_

  - [x]* 9.2 Write example tests for the already-used rule
    - A used reference gives `NOT_FOUND`, checked, `matched_reference` set and exactly `This payment was already used for an earlier check`
    - An unused reference gives `CONFIRMED`. No `is_used` gives `CONFIRMED`
    - An `is_used` that raises gives `UNAVAILABLE` unchecked with `could not check Paystack`
    - A used reference on the search path (one matching transaction with a string reference) gives the same `NOT_FOUND` result
    - Also check that `is_used` is not called for a non-matching response, and that the constant has 50 characters
    - Put them in `tests/test_example_paystack_used.py`
    - _Requirements: 10.3, 10.4, 10.5, 10.6, 10.8, 10.10, 10.11_

  - [x]* 9.3 Write property tests for the already-used rule
    - **Property 16: A used or unverifiable reference is never confirmed**
    - **Property 17: An unused reference or no ledger changes nothing**
    - Two Hypothesis tests in `tests/test_prop_paystack_used.py`, one per property (this is the one place where one task holds two properties, to keep the requested task list)
    - **Validates: Requirements 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8, 10.9, 10.10, 10.12**

  - [x] 9.4 Change the verdict engine for the already-used reason in `src/ghost_credit/verdict.py`
    - Import `REASON_ALREADY_USED` from `ghost_credit.paystack`
    - In `decide`, when the state is `no_match` and `paystack_result.reason` equals `REASON_ALREADY_USED`, use that sentence as the single NOT_FOUND reason instead of `REASON_NOT_FOUND`. The code stays `NOT_FOUND` and `paystack_checked` stays True
    - Leave `_HEADLINES` unchanged. Its GHOST headline still says "Paystack has no matching payment for this alert", which reads oddly beside the new reason. This is listed under Open Points in the verdict-engine design for the owner to decide
    - _Requirements: verdict-engine 3.12_

  - [x]* 9.5 Update the verdict tests
    - Add an example test: a checked `NOT_FOUND` result with the already-used reason gives code `NOT_FOUND` and the reasons list `["This payment was already used for an earlier check"]`; a checked `NOT_FOUND` with any other reason still gives `Paystack found no matching payment.`
    - Update the reasons-content property test (verdict-engine Property 8) so the NOT_FOUND case accepts either fixed reason, chosen by the Paystack reason
    - Put the example in `tests/test_verdict_used_reason_examples.py` and edit `tests/test_verdict_prop_08_reasons_content.py`
    - _Requirements: verdict-engine 3.9, 3.12_

  - [x] 9.6 Wire the used-payment ledger in `src/ghost_credit/pipeline.py`
    - Add the `UsedReferences` protocol (`is_used(reference) -> bool`, `mark_used(reference) -> None`) and the thread-safe `InMemoryUsedReferences` (a `set` guarded by a `threading.Lock`)
    - Give `make_paystack_verify` the optional `is_used` and pass it to `verify`
    - Add the keyword-only `used_references=None` to `run_check`. When given and no `paystack_verify` was injected, build the default callable with `make_paystack_verify(is_used=used_references.is_used)`. An injected `paystack_verify` is used as supplied. After a `CONFIRMED` verdict whose `paystack_result.matched_reference` is a string, call `mark_used` once, swallowing any error and logging only the step name and exception type
    - Document in the module docstring that `InMemoryUsedReferences` lasts only as long as one process
    - _Requirements: check-pipeline 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7_

  - [x]* 9.7 Write the pipeline tests for the ledger
    - Put them in `tests/test_pipeline_used_references_examples.py`: with no ledger, behaviour is unchanged; a first check with a matching payment is `CONFIRMED` and marks the reference once; a second check with the same reference is `NOT_FOUND` with the already-used reason and marks nothing; a `mark_used` that raises leaves the `CONFIRMED` result unchanged; an `is_used` that raises gives `UNAVAILABLE` and a non-CONFIRMED verdict; a non-CONFIRMED verdict never marks; `InMemoryUsedReferences` is safe to use from several threads
    - _Requirements: check-pipeline 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8_

  - [x] 9.8 Run the full suite
    - Run the whole test suite with `PATTERN_NETWORK=off` and fix any failure. Ensure all tests pass, ask the user if questions arise.
    - _Requirements: 8.4, 10.11, 10.12_

## Notes

- Task 9 is an addition made after tasks 1 to 8 were done. It leaves the earlier tasks unchanged.
- Tasks marked with `*` are optional test sub-tasks and can be skipped for a faster MVP
- Each task references specific requirements for traceability
- Each Hypothesis property is its own sub-task, runs at least 100 examples, and carries the tag **Feature: paystack-verifier, Property N: title**
- Tasks 1.1 to 6.1 all edit `paystack.py`, so they run in separate waves
- `scripts/paystack_smoke.py` is outside this spec

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "1.3", "1.4", "2.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "3.1"] },
    { "id": 3, "tasks": ["3.2", "3.3", "3.4", "4.1"] },
    { "id": 4, "tasks": ["4.2", "4.3", "5.1"] },
    { "id": 5, "tasks": ["5.2", "5.3", "5.4", "6.1"] },
    { "id": 6, "tasks": ["6.2", "6.3", "7.1", "7.2", "7.3", "7.4", "7.5", "8.1"] },
    { "id": 7, "tasks": ["9.1"] },
    { "id": 8, "tasks": ["9.2", "9.3", "9.4", "9.6"] },
    { "id": 9, "tasks": ["9.5", "9.7"] },
    { "id": 10, "tasks": ["9.8"] }
  ]
}
```
