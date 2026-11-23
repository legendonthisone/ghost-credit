# Implementation Plan: check-pipeline

## Overview

Implement `src/ghost_credit/pipeline.py` in Python 3.11 or newer. It holds `run_check`, `merge_alerts`, `make_paystack_verify`, `CheckResult` and small private helpers. The module only wires existing parts together. It holds no verdict rules and no AI call. Work follows the design's implementation order: skeleton and fixed pieces, read and merge, Paystack and network steps, wiring `run_check`, smoke checks and secrets, then a final checkpoint.

### Dependencies that must exist first

Do not start this plan until these parts exist and their tests pass:

- **`src/ghost_credit/pattern_network.py`**, built by the `pattern-network-hook` tasks. It must export `PatternNetwork`, `NoopPatternNetwork`, `Signals`, `Verdict`, `LookupResult`, `ReportReceipt`, `safe_lookup` and `safe_report`. It must also export the public Signals builder named `build_signals`, which is `pattern-network-hook` task 5.2. `build_signals` takes the keyword-only arguments listed in the "Signals builder contract" of `design.md`. If task 5.2 uses a different name or argument list, change the one import and the one call in `pipeline.py` to match.
- **`src/ghost_credit/verdict.py`**, built by the `verdict-engine` tasks. It must export `decide_with_notes`, `Decision`, `Explainer`, `TemplateExplainer`, `build_reply` and `CHECK_REMINDER`.
- **The `TRANSFER_REQUEST_WORDING` flag in `src/ghost_credit/parser.py`.** `RED_FLAG_CODES` must hold this code (the parser currently lists six codes). Until it does, `pipeline.py` keeps the code through its own `FLAG_ORDER`, so the merge loses nothing, but the parser change is still a dependency of this plan.

Already built and used as they are: `parser.py` (`parse_sms_alert`, `ParsedAlert`, `RED_FLAG_CODES`), `screenshot.py` (`ScreenshotReader`, `FakeScreenshotReader`) and `paystack.py` (`verify`, `PaystackResult`).

### Test files

Each correctness property has its own test file, named `tests/test_pipeline_property_NN_<short_name>.py`. Shared fakes live in `tests/pipeline_fakes.py`. All tests use synthetic data, make no network call, no AI call and no live Paystack call, and run with `PATTERN_NETWORK=off`.

## Tasks

- [x] 1. Skeleton and fixed pieces of `pipeline.py`
  - [x] 1.1 Create `src/ghost_credit/pipeline.py` with constants, types and fixed helpers
    - Add imports, the constants `FALLBACK_REASON`, `UNAVAILABLE_REASON`, `DEFAULT_CATEGORY` and `LAGOS`, and import `CHECK_REMINDER` from `ghost_credit.verdict`
    - Add the frozen `CheckResult` dataclass with the fields `check_id`, `parsed`, `paystack_result`, `verdict`, `reply` and `risk_notes`
    - Add the `_UNAVAILABLE` module constant, `_log_failure(step, exc)` (logs only the step name and the exception type name), and `_safe_fallback(check_id, parsed)` built from fixed values with a new `Verdict` and `reasons` list on each call
    - Add `make_paystack_verify(http=None)`, which reads `PAYSTACK_SECRET_KEY` at call time, turns an empty value into None and calls `paystack.verify`
    - Add `_lagos_iso(now)` and `_clean_category(value)`
    - Add short plain-English docstrings and type hints
    - _Requirements: 3.2, 3.3, 3.4, 3.5, 4.2, 4.6, 7.3, 7.4, 7.5, 7.6, 7.7, 8.1, 8.2, 8.4, 8.5_

  - [x]* 1.2 Create the shared test fakes in `tests/pipeline_fakes.py`
    - Add `RecordingReader` (counts calls, returns a given `ParsedAlert`, raises or returns junk), `FakePaystack` (returns a given object or raises, records its arguments), `RecordingNetwork` (records Signals from `lookup_patterns` and calls to `report_pattern`, returns a given `LookupResult`, can raise) and small explainers that return text, return a non-string or raise
    - Add a helper that waits for the background report thread with a short `threading.Event`
    - Add Hypothesis generators for `ParsedAlert`, text, sender, bytes, `now`, `merchant_category` and `PaystackResult` shapes that `paystack.verify` can return
    - Use synthetic data only and obviously fake test keys
    - _Requirements: 9.1, 9.11_

  - [x]* 1.3 Write example tests for the fallback shape and `make_paystack_verify`
    - Create `tests/test_pipeline_fallback_examples.py`: the fallback has code `UNVERIFIED`, `decided_by` "rules", `paystack_checked` False, `owner_outcome` "unknown", `reasons` equal to `[FALLBACK_REASON]`, the reply `FALLBACK_REASON + " " + CHECK_REMINDER`, the unavailable `paystack_result` and empty `risk_notes`; two calls return separate `Verdict` and `reasons` objects
    - Create `tests/test_pipeline_paystack_helper_examples.py`: with a fake `http` function and a fake test key set through `monkeypatch`, the Authorization header carries the key; with the variable unset or empty, no `http` call is made and the result is UNAVAILABLE
    - _Requirements: 3.2, 3.3, 3.4, 7.3, 7.4, 7.5, 7.6, 7.7, 9.9_

  - [x]* 1.4 Write property test for the merchant category
    - Create `tests/test_pipeline_property_10_merchant_category.py`
    - **Property 10: Merchant category is trimmed or defaults to "other"**
    - **Validates: Requirements 4.6**

- [x] 2. Read the sources and merge them
  - [x] 2.1 Add the source helpers and `merge_alerts` to `pipeline.py`
    - Add `_text_usable`, `_image_usable`, `_read_text` and `_read_image` (one call each; `_read_image` returns an empty `ParsedAlert` when the reader raises or returns a non-`ParsedAlert`, logs only the step name and exception type, and keeps no reference to the bytes)
    - Add the pure `merge_alerts(text_alert, image_alert, sender_id)` that uses `dataclasses.fields(ParsedAlert)`, takes the text value first, fills gaps from the screenshot, sets `screenshot_phash` from the screenshot alert and sets `sender_id` from the argument when it is a string
    - Add `_merge_flags(a, b)` and `FLAG_ORDER` (`RED_FLAG_CODES` plus `TRANSFER_REQUEST_WORDING` when missing), keeping each code once, known codes first, other string codes in first-seen order, and ignoring non-strings
    - Leave both input alerts and their `red_flags` lists unchanged
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.10, 2.11, 2.12, 8.3_

  - [x]* 2.2 Write property test for the merge
    - Create `tests/test_pipeline_property_06_merge_alerts.py`
    - **Property 6: Merge keeps text values first, fills gaps from the screenshot**
    - **Validates: Requirements 2.3, 2.4, 2.5, 2.7, 2.8, 2.12, 9.4**

  - [x]* 2.3 Write property test for merged red flags
    - Create `tests/test_pipeline_property_07_merge_flags.py`
    - **Property 7: Merged red flags are the ordered union**
    - **Validates: Requirements 2.6, 9.4**

  - [x]* 2.4 Write example tests for reading and merging
    - Create `tests/test_pipeline_merge_examples.py`: a text and screenshot merge with known values, an unreadable screenshot (reader raises, reader returns junk) giving an empty screenshot alert and a continued check, and `SCREENSHOT_EDIT_SIGNS` and `TRANSFER_REQUEST_WORDING` surviving the merge
    - _Requirements: 2.3, 2.6, 2.10, 9.6, 9.9_

- [x] 3. Paystack and network steps
  - [x] 3.1 Add `_check_paystack` to `pipeline.py`
    - Call `paystack_verify(parsed, now)` once with `now` unchanged and no secret key
    - Return `_UNAVAILABLE` when the callable raises (log step name and exception type) or returns a non-`PaystackResult`
    - Otherwise return the same object unchanged, including UNAVAILABLE and unchecked results
    - _Requirements: 3.1, 3.6, 3.7, 3.8, 3.9, 3.10_

  - [x] 3.2 Add `_build_signals`, the empty lookup constant and `_report` to `pipeline.py`
    - Add `_EMPTY_LOOKUP` as `LookupResult(network_available=False, matched=False, matches=[])`, built fresh or treated as read-only
    - Add `_build_signals(check_id, merged, text, image_bytes, merchant_category, now)` that returns None when `amount_kobo` is not an integer (a `bool` does not count), sets `channel` "sms" when the text is usable and "screenshot" otherwise, fills the fields as the design says and passes no payer values to `build_signals`
    - Return None after a log line (step name and exception type only) when building fails
    - Add `_report(network, verdict, signals)` that wraps `safe_report` in try/except and discards any error
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.8, 4.9, 6.5, 6.6, 6.7_

  - [x]* 3.3 Write property test for the Signals fields
    - Create `tests/test_pipeline_property_09_signals_fields.py`
    - **Property 9: Signals carry the merged alert and no payer data**
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5**

  - [x]* 3.4 Write property test for no network traffic without an amount
    - Create `tests/test_pipeline_property_12_no_amount_no_network.py`
    - **Property 12: No amount means no network traffic**
    - **Validates: Requirements 4.8, 4.9**

  - [x]* 3.5 Write example tests for Paystack and Signals failures
    - Create `tests/test_pipeline_paystack_network_examples.py`: a Paystack callable that raises gives the Unavailable_Paystack_Result and a continued check; a callable that returns junk does the same; an UNAVAILABLE `PaystackResult` is passed on unchanged; the callable receives the merged alert and the same `now` object; a `build_signals` that raises gives an empty `LookupResult`, no lookup and no report
    - _Requirements: 3.1, 3.7, 3.8, 3.9, 3.10, 4.8, 4.9, 9.9_

- [x] 4. Wire `run_check`
  - [x] 4.1 Add `run_check` to `pipeline.py`
    - Use the signature `run_check(text, sender_id, image_bytes, merchant_category, now, *, reader=None, paystack_verify=None, network=None, explainer=None)` and set `check_id` to a new UUID version 4 string
    - Replace each None keyword argument with its default: `FakeScreenshotReader()`, `make_paystack_verify()`, `NoopPatternNetwork()` and `TemplateExplainer()`
    - Put the steps inside one outer try: sources, merge, Paystack, Signals and `safe_lookup`, `decide_with_notes(merged, paystack_result, lookup, alert_text=text if isinstance(text, str) else None)`, `build_reply(decision.verdict, merged, explainer, decision.risk_notes)`
    - Return `_safe_fallback` with no Paystack, network or explainer call when neither source is usable, and from the `except` branch for any other unhandled error
    - Call `_report` once, after the reply is built, when Signals were built and the verdict code is not `CONFIRMED`, inside its own try so a report failure never replaces the result
    - Read the verdict code only from the Decision, and copy `risk_notes` as a list of strings
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 2.9, 4.7, 4.10, 5.1, 5.2, 5.3, 5.4, 5.5, 6.1, 6.2, 6.3, 6.4, 7.1, 7.2, 7.8_

  - [x]* 4.2 Write property test for totality
    - Create `tests/test_pipeline_property_01_total.py`
    - **Property 1: Run_Check is total and returns a valid result**
    - **Validates: Requirements 1.2, 1.3, 7.1, 7.2, 9.2**

  - [x]* 4.3 Write property test for CONFIRMED matching the engine
    - Create `tests/test_pipeline_property_02_confirmed_matches_engine.py`
    - **Property 2: CONFIRMED matches the engine, and the result passes through**
    - **Validates: Requirements 3.6, 3.7, 5.5, 9.3**

  - [x]* 4.4 Write property test for dependency failures
    - Create `tests/test_pipeline_property_03_dependency_failures.py`
    - **Property 3: Dependency failures never produce CONFIRMED or an error**
    - **Validates: Requirements 3.8, 3.9, 5.5**

  - [x]* 4.5 Write property test for the verdict coming only from the engine
    - Create `tests/test_pipeline_property_04_verdict_from_engine.py`
    - **Property 4: The verdict comes only from the engine (model-based)**
    - **Validates: Requirements 1.4, 1.5, 4.10, 5.1, 5.2, 5.3, 7.8**

  - [x]* 4.6 Write property test for the reminder on unconfirmed replies
    - Create `tests/test_pipeline_property_05_reminder.py`
    - **Property 5: Replies for unconfirmed verdicts end with the reminder**
    - **Validates: Requirements 5.4, 7.4, 9.5**

  - [x]* 4.7 Write property test for reading sources once
    - Create `tests/test_pipeline_property_08_sources_read_once.py`
    - **Property 8: Sources are read once when, and only when, usable**
    - **Validates: Requirements 2.1, 2.2, 2.9**

  - [x]* 4.8 Write property test for reports
    - Create `tests/test_pipeline_property_11_reports.py`
    - **Property 11: Reports follow the verdict and reuse the lookup Signals**
    - **Validates: Requirements 6.1, 6.2, 6.3, 6.6, 6.7**

  - [x]* 4.9 Write example tests for the verdict paths
    - Create `tests/test_pipeline_verdict_examples.py`: the CONFIRMED path with no report call; the NOT_FOUND path; the SUSPICIOUS path with red flags; the UNVERIFIED path; a screenshot and text merge through `run_check`; a network match that turns UNVERIFIED into SUSPICIOUS (5.6) and the same alert without a match giving UNVERIFIED (5.7)
    - Show that `safe_report` is called once for each non-CONFIRMED code and not for CONFIRMED
    - _Requirements: 5.4, 5.6, 5.7, 6.1, 6.2, 9.6, 9.7_

  - [x]* 4.10 Write example tests for order, failures, reports and risk notes
    - Create `tests/test_pipeline_run_examples.py`: call order is read, Paystack, lookup, report; a raising dependency reaches the fallback; no usable text or image gives the fallback with no Paystack, network or explainer call; a slow `report_pattern` does not delay the return; a `report_pattern` that raises leaves the result unchanged; `risk_notes` filled from a Friday-afternoon alert and from an `alert_text` mentioning a rider
    - _Requirements: 1.7, 2.9, 6.4, 6.5, 7.2, 9.9_

  - [x]* 4.11 Write the full `PATTERN_NETWORK=off` example test
    - Create `tests/test_pipeline_pattern_network_off.py`: set `PATTERN_NETWORK=off` through `monkeypatch`, call `run_check` with no keyword arguments (default reader, default Paystack callable with no key, `NoopPatternNetwork`, `TemplateExplainer`) and check that a valid `CheckResult` comes back with no network call
    - _Requirements: 1.6, 9.1, 9.8_

- [x] 5. Smoke checks and secrets
  - [x]* 5.1 Write smoke checks for `pipeline.py`
    - Create `tests/test_pipeline_smoke.py`: the source holds no AI model name, AI client import, HTTP library or socket import, `open(` call, float arithmetic on money or secret; `run_check` has the parameter order in Requirement 1.1; no module-level name holds image bytes
    - _Requirements: 1.1, 1.8, 8.3, 8.4, 8.5, 8.7_

  - [x]* 5.2 Write the secret-key example test
    - Create `tests/test_pipeline_secret_key.py`: with an obviously fake test key set through `monkeypatch`, the key text is absent from the `CheckResult` (as text), from `caplog` output and from the text of an error raised by a failing dependency
    - _Requirements: 3.5, 8.1, 8.2, 9.10_

- [x] 6. Final checkpoint - Ensure all tests pass
  - Run the whole suite with `PATTERN_NETWORK=off` and fix any failure. Ensure all tests pass, ask the user if questions arise.
  - _Requirements: 9.1, 9.8_

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP. The user asked for every test sub-task to be listed, so each test file is its own sub-task.
- Each task references specific requirements for traceability.
- Property tests use Hypothesis with at least 100 examples and carry the tag comment `Feature: check-pipeline, Property N: <property text>`.
- Tasks 1.1, 2.1, 3.1, 3.2 and 4.1 all edit `pipeline.py`, so the dependency graph puts them in separate waves.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["1.3", "1.4", "2.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "2.4", "3.1"] },
    { "id": 3, "tasks": ["3.2"] },
    { "id": 4, "tasks": ["3.3", "3.4", "3.5", "4.1"] },
    { "id": 5, "tasks": ["4.2", "4.3", "4.4", "4.5", "4.6", "4.7", "4.8", "4.9", "4.10", "4.11", "5.1", "5.2"] }
  ]
}
```
