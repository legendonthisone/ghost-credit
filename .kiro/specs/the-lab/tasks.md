# Implementation Plan: the-lab

## Overview

Build `lab.py` (storage, sanitiser, record builder, rate limiter, page template) first since every other piece depends on it, then `lab_router.py` on top of it, then wire both into `lambda_handler.py` and `whatsapp.py`, then update the deploy script and `PRIVACY.md`. Python 3.11+, FastAPI/pytest conventions already in the repo are not needed here since the Lambda stays a plain function; Hypothesis is used for property tests. The whole suite passes with `PATTERN_NETWORK=off` and no live AWS, Paystack or AI call.

### Dependencies

Already built and used as-is: `pipeline.py` (`run_check`, `CheckResult`, `FLAG_ORDER`, `make_paystack_verify`, `LAGOS`), `verdict.py` (`Verdict`, `OWNER_LABELS`, `TemplateExplainer`, `FLAG_REASONS`), `pattern_network.py` (`NoopPatternNetwork`), `whatsapp.py` (`handle_webhook`), `lambda_handler.py`, `scripts/deploy_lambda.py` (`permissions_policy`, `select_lambda_variables`, `build_zip`).

### Test files

Property tests are named `tests/test_lab_prop_NN_<short_name>.py` and `tests/test_deploy_prop_NN_<short_name>.py` (continuing the existing deploy numbering). Shared fakes live in `tests/lab_fakes.py`. Property tests use Hypothesis with at least 100 examples and carry the tag comment `Feature: the-lab, Property N: <property text>`. No test imports `boto3` eagerly or calls AWS.

## Tasks

- [x] 1. Build `src/ghost_credit/lab.py`: storage, sanitiser, record builder, rate limiter
  - [x] 1.1 Implement `CheckStore` Protocol, `InMemoryCheckStore`, constants and `sanitise_record`
    - Add `ALLOWED_FIELDS`, `TTL_SECONDS`, `MAX_LIST_ITEMS`, `MAX_TEXT_FIELD_CHARS`, `MAX_BANK_CHARS`, `MAX_TRY_TEXT_CHARS`, `RATE_LIMIT_PER_MINUTE`
    - Implement the `CheckStore` Protocol and `InMemoryCheckStore.save`/`newest`
    - Implement `sanitise_record(record)`: keep only `ALLOWED_FIELDS`, mask every run of 7+ digits (digits optionally separated by spaces, hyphens, dots or commas) with `[removed]` in every string field except `check_id`, cut `reasons`/`risk_notes` to 10 items of 120 characters each, cut `claimed_bank` to 60 characters
    - _Requirements: 2.1, 2.2, 3.6, 3.7, 3.8, 3.9_

  - [x]* 1.2 Write property tests for the sanitiser and InMemoryCheckStore
    - **Property 2: InMemoryCheckStore round-trips saved records** — **Validates: Requirements 2.2**
    - **Property 6: The Sanitiser enforces its field and length invariants** — **Validates: Requirements 3.6, 3.8, 3.9**
    - **Property 7: The Sanitiser removes every long digit run except in check_id** — **Validates: Requirements 3.7**

  - [x] 1.3 Implement `record_check`, `DynamoCheckStore` and `get_store`
    - Implement `record_check(store, check_result, channel, now)`: build the Check_Record (all `ALLOWED_FIELDS`, `checked_at` as Lagos ISO 8601, `owner_label` from `OWNER_LABELS`, `expires_at` as `checked_at` + 2,592,000 seconds), pass it through `sanitise_record`, call `store.save` inside a try/except that logs only the exception type name, do nothing when `store` is `None`
    - Implement `DynamoCheckStore.__init__/save/newest` with `boto3` imported lazily inside `save`/`newest`, table name from `CHECKS_TABLE` env var defaulting to `ghost-credit-checks`; `save` does exactly one `PutItem`; `newest` does one `Scan`, sorts by `checked_at` descending, returns at most `min(limit, 50)`
    - Implement `get_store()`: returns `DynamoCheckStore()` when `CHECKS_TABLE` is set in the environment, else `None`
    - _Requirements: 2.3, 2.4, 2.5, 2.6, 2.7, 3.1, 3.2, 3.3, 3.4, 3.5, 3.10, 3.11, 3.12_

  - [x]* 1.4 Write property and example tests for record_check and DynamoCheckStore
    - **Property 5: Record_Check builds a complete, correctly derived Check_Record** — **Validates: Requirements 3.3, 3.4**
    - **Property 8: Record_Check never raises and never changes the reply** — **Validates: Requirements 3.10, 3.11, 3.12**
    - **Property 3: DynamoCheckStore.save sends exactly one well-shaped PutItem** — **Validates: Requirements 2.5**
    - **Property 4: DynamoCheckStore.newest sorts and limits a Scan** — **Validates: Requirements 2.6**
    - Example tests: `get_store()` returns `None`/`DynamoCheckStore` depending on `CHECKS_TABLE`
    - _Requirements: 2.3, 2.4, 2.7_

  - [x] 1.5 Implement the rate limiter, naira formatting, flag mapping and the HTML page template
    - Implement `SlidingWindowLimiter.allow(now)`: in-memory sliding window, 20 calls per 60 seconds
    - Implement `format_naira(amount_kobo)` using only integer division/modulo, and `plain_english_flags(codes)` mapping to `verdict.FLAG_REASONS` sentences
    - Implement `render_page()`: one self-contained HTML string with inline CSS and JS, a viewport meta tag, a verdict filter control, a sample-data toggle (client JS computes "default on when records is empty"), ghost/solid styling hooks keyed by owner label, a form posting to `/lab/check`, and client JS that fetches `/lab/data` and renders every value with `textContent`/`createElement` only (no `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `document.write`)
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 5.3, 6.1, 6.2, 6.3_

  - [x]* 1.6 Write property and example tests for the limiter, formatting and page source
    - **Property 12 (limiter half): the limiter enforces a 20-per-60-second window** — **Validates: Requirements 7.5**
    - Example tests: page has no external `src`/`href`, inline-only, viewport tag present, fetches `/lab/data`; JS source has none of `innerHTML`/`outerHTML`/`insertAdjacentHTML`/`document.write`; `format_naira` examples (0, 4500000, 50); `plain_english_flags` examples for every code in `FLAG_ORDER`
    - _Requirements: 4.1, 4.2, 4.3, 8.2_

- [x] 2. Build `src/ghost_credit/lab_router.py` and `lab_sample.json`
  - [x] 2.1 Implement `route()`, `_lab_headers`, `_handle_data`, `_handle_check`, `_escape`
    - Implement `route(method, path, query, headers, raw_body, *, now, store, limiter, run_check_fn=run_check)` dispatching `/lab`, `/lab/data`, `/lab/check`; unknown path 404, wrong method 405, every response passed through `_lab_headers` (CSP, `X-Content-Type-Options: nosniff`, `Cache-Control: no-store`)
    - `/lab/data`: JSON `{"records": store.newest(50) or [], "sample": <six records from lab_sample.json>}`; a `newest` failure falls back to `[]`
    - `/lab/check`: parse JSON body, require `text` string; reject (413) text over 2000 characters without calling `run_check_fn`; enforce `limiter.allow(now)`, returning 429 without calling `run_check_fn` when denied; otherwise call `run_check_fn` with `TemplateExplainer()`, `make_paystack_verify()`, `NoopPatternNetwork()`; call `record_check(store, result, "lab", now)`; return the JSON result fields; never echo the submitted text into any HTML
    - Wrap the whole function body in a top-level try/except returning a safe fallback response (never raises)
    - _Requirements: 4.1, 5.1, 5.2, 5.4, 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 8.1, 8.3, 8.4_

  - [x] 2.2 Create `src/ghost_credit/lab_sample.json`
    - Six synthetic Check_Records: one `CONFIRMED`/ALIVE, one `NOT_FOUND`/GHOST with "no matching payment" reasons, one `NOT_FOUND`/GHOST with "already used" reasons, one `SUSPICIOUS`, one `UNVERIFIED`, one `SUSPICIOUS` or `UNVERIFIED` with `TRANSFER_REQUEST_WORDING` in its red flags
    - Only synthetic values: no real phone numbers, account digits or names
    - _Requirements: 6.4, 6.5_

  - [x]* 2.3 Write property and example tests for the router
    - **Property 1: The router is a total, correct passthrough for non-Lab paths** — **Validates: Requirements 1.1, 1.2, 1.4**
    - **Property 9: GET /lab/data always returns both arrays, records from the store, within the allowed fields** — **Validates: Requirements 5.1, 5.2, 5.4**
    - **Property 10: Try_Form's response fields come from the CheckResult it ran** — **Validates: Requirements 7.1**
    - **Property 11: Over-length Try_Form text is always rejected before running a check** — **Validates: Requirements 7.2**
    - **Property 12 (full): the rate limiter enforces its window end to end at the router** — **Validates: Requirements 7.5, 7.6**
    - **Property 13: No executable, unescaped or reflected content ever appears in Lab HTML** — **Validates: Requirements 7.4, 8.1, 8.4**
    - **Property 14: Every Lab response carries the required security headers** — **Validates: Requirements 8.3**
    - Example tests: the literal 21st-call-in-one-minute returns 429; `GET /lab/data` sample array equals the six `lab_sample.json` records with the required verdict mix; a digit-run scan of `lab_sample.json` finds nothing to mask; a Try_Form call with a fake store calls `record_check` once with channel `"lab"`
    - _Requirements: 6.4, 6.5, 7.3_

- [x] 3. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Wire The Lab into `lambda_handler.py` and `whatsapp.py`
  - [x] 4.1 Add path-based routing to `lambda_handler.py`
    - Add `_path(event)` reading `rawPath`, defaulting to `"/"`
    - Add a module-level `_LIMITER = SlidingWindowLimiter()`
    - When the path starts with `/lab`, call `lab_router.route(...)` with `get_store()`, `_LIMITER` and `datetime.now(LAGOS)`, and build the Lambda response dict from its result; otherwise call `handle_webhook` exactly as today
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [x] 4.2 Add an optional `store` parameter to `handle_webhook` and call `record_check` after a WhatsApp reply
    - Add `store: CheckStore | None = None` to `handle_webhook`'s signature, defaulting to `get_store()` when not supplied
    - In the text-message branch of `_process_message`, after `_send_reply` returns, call `record_check(store, result, "whatsapp", clock())`
    - _Requirements: 3.1_

  - [x]* 4.3 Write example tests for the wiring
    - A non-`/lab` Function URL event still reaches `handle_webhook` unchanged (existing `whatsapp-webhook` tests keep passing)
    - A `/lab` Function URL event is routed to `lab_router.route`
    - A WhatsApp text check with an injected fake store calls `record_check` once with channel `"whatsapp"`
    - _Requirements: 1.1, 1.4, 3.1_

- [x] 5. Update `scripts/deploy_lambda.py` for the Checks_Table and reserved concurrency
  - [x] 5.1 Add the pure helpers and extend `permissions_policy`/`select_lambda_variables`
    - Add `CHECKS_TABLE_NAME = "ghost-credit-checks"` and `RESERVED_CONCURRENCY = 5`
    - Add `checks_table_permissions_statement(account_id, region)` and `lab_url(function_url)`
    - Extend `permissions_policy(account_id)` with the new DynamoDB statement (exactly `dynamodb:PutItem`, `dynamodb:Scan`) alongside the existing Bedrock and logs statements
    - Add `CHECKS_TABLE` to `LAMBDA_VARIABLE_NAMES`, defaulting to `CHECKS_TABLE_NAME` in `select_lambda_variables` when unset
    - _Requirements: 9.2, 9.3, 9.5_

  - [x]* 5.2 Write property tests for the new pure helpers
    - **Property 15: The permissions policy grants exactly the right DynamoDB actions on the right resource** — **Validates: Requirements 9.2**
    - **Property 16: lab_url always appends "lab" as a path segment** — **Validates: Requirements 9.5**
    - _Requirements: 9.2, 9.5_

  - [x] 5.3 Add `_ensure_checks_table` and `_set_reserved_concurrency`, wire them into `_deploy` and `main`
    - `_ensure_checks_table(client)`: create the table if missing (`PAY_PER_REQUEST`, key `check_id` S), then call `update_time_to_live` enabling TTL on `expires_at`; an existing table is left as is
    - `_set_reserved_concurrency(client)`: call `put_function_concurrency`; catch `InvalidParameterValueException` and `LimitExceededException` (and any other exception), print a warning naming the exception type, and continue
    - Call both from `_deploy`; have `main` print the Lab URL (via `lab_url`) after the existing Function URL line
    - _Requirements: 9.1, 9.4, 9.6, 9.7_

  - [x]* 5.4 Write property and example tests for the new AWS-calling helpers
    - **Property 17: A reserved-concurrency failure is reported and never stops the deploy** — **Validates: Requirements 9.7**
    - Example tests with a fake DynamoDB client: `_ensure_checks_table` call shape (CreateTable args, TTL call) when the table is missing and when it already exists; `lab_sample.json` is present in the real package zip (`build_zip`)
    - _Requirements: 9.1, 9.4_

- [x] 6. Update `PRIVACY.md`
  - [x] 6.1 Add The Lab's retention statement
    - Add a bullet under "What we keep": check results (verdict, amount, red flags, reasons) are kept 30 days for The Lab; message text and phone numbers are never stored
    - _Requirements: 10.1, 10.2_

  - [x]* 6.2 Write example tests for the privacy document
    - Read `PRIVACY.md` and assert it states the 30-day Lab retention and the never-stores-text-or-numbers facts
    - _Requirements: 10.1, 10.2_

- [x] 7. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster path through the checklist; they are not implemented as part of executing this plan unless separately requested.
- `/lab` ships with no authentication in this spec; it is reachable by anyone with the Function URL, guarded only by the Rate_Limiter and the Lambda's reserved concurrency of 5. Adding a shared secret or Cognito gate is an open point that needs Ayobami's approval before it is built (see requirements.md "Open Points").
- Each task references specific requirements for traceability; property tests reference their design document property number.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "1.3"] },
    { "id": 2, "tasks": ["1.4", "1.5"] },
    { "id": 3, "tasks": ["1.6", "2.1", "2.2"] },
    { "id": 4, "tasks": ["2.3"] },
    { "id": 5, "tasks": ["3"] },
    { "id": 6, "tasks": ["4.1", "4.2", "5.1"] },
    { "id": 7, "tasks": ["4.3", "5.2", "5.3"] },
    { "id": 8, "tasks": ["5.4", "6.1"] },
    { "id": 9, "tasks": ["6.2"] },
    { "id": 10, "tasks": ["7"] }
  ]
}
```
