# Implementation Plan: whatsapp-webhook

## Overview

Part A builds `src/ghost_credit/whatsapp.py` (standard library only) in two steps: first the request gate (GET verification, size limit, signature check, totality), then message processing (payload parsing, `run_check`, reply, dedupe, privacy). Part B makes the image imports in `screenshot.py` lazy, adds the Lambda adapter, the deploy script, the deploy guide and `.env.example`. The work is in Python 3.11 or newer. Every test uses synthetic data, fakes and no live call, and the whole suite passes with `PATTERN_NETWORK=off`.

### Dependencies

Already built and used as they are: `pipeline.py` (`run_check`, `make_paystack_verify`, `LAGOS`), `verdict.py` (`TemplateExplainer`), `screenshot.py` (`FakeScreenshotReader`), `pattern_network.py` (`get_network`) and `paystack.py` (the injectable `http` pattern).

Not built here: `ghost_credit.ai_explainer` (the `ai-explainer` spec). The webhook falls back to `TemplateExplainer` while that module is missing.

### Test files

Property tests are named `tests/test_whatsapp_prop_NN_<short_name>.py` and `tests/test_deploy_prop_NN_<short_name>.py`. Shared fakes live in `tests/whatsapp_fakes.py` (task 2.2) and a script loader in `tests/deploy_helpers.py` (task 6.1). Property tests use Hypothesis with at least 100 examples and carry the tag comment `Feature: whatsapp-webhook, Property N: <property text>`. No test imports `boto3`.

## Tasks

- [x] 1. Make the image libraries lazy in `screenshot.py`
  - [x] 1.1 Move the `PIL` and `imagehash` imports into `_compute_phash`
    - Remove the top-level `import imagehash` and `from PIL import Image`
    - Import both inside the existing `try` of `_compute_phash`, after the type and size guards, so a missing library returns None
    - Add a module-level `__getattr__(name)` that returns `PIL.Image` for `"Image"` and the `imagehash` module for `"imagehash"`, and raises `AttributeError` for any other name
    - Keep every other line of the file unchanged
    - _Requirements: 10.1, 10.2, 10.4, 10.5_

  - [x]* 1.2 Write example tests for the lazy imports
    - Create `tests/test_whatsapp_lazy_imports.py`
    - Run a subprocess with an import blocker for `PIL`, `imagehash`, `numpy` and `scipy` that imports `ghost_credit.pipeline` and checks it succeeds
    - With the blocker active in a subprocess, check `_compute_phash(b"abc")` returns None
    - Check `screenshot.Image` and `screenshot.imagehash` are readable and that `monkeypatch.setattr(screenshot.Image, "open", ...)` still works
    - Check the source has no top-level `PIL` or `imagehash` import
    - Run the existing screenshot tests and confirm they pass unchanged
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

- [x] 2. Webhook request gate in `whatsapp.py`
  - [x] 2.1 Create `src/ghost_credit/whatsapp.py` with constants, types, the gate and totality
    - Add the module docstring (best-effort dedupe, one process or container, standard library only) and the constants `GRAPH_API_VERSION = "v21.0"`, `GRAPH_URL_TEMPLATE`, `MAX_BODY_BYTES`, `MAX_TEXT_CHARS`, `MAX_REPLY_CHARS`, `SEND_TIMEOUT_SECONDS`, `SEEN_CAPACITY`, `USER_AGENT` and `ASK_FOR_SMS_REPLY`
    - Add the frozen dataclasses `WebhookResponse` and `IncomingMessage`, and the `SeenSet` class with `add_if_new` (an `OrderedDict`, oldest removed first)
    - Add `verify_subscription(query, verify_token)` and `verify_signature(raw_body, header, app_secret)` using `hmac.compare_digest` on bytes, with an unset or empty secret or token never matching
    - Add the helpers `_env`, `_normalise_headers` and `_as_bytes`
    - Add `handle_webhook(method, query, headers, body, *, send, clock, check, reader, paystack_verify, network, explainer, seen)` with the `authenticated` flag: GET handling, 405 for other methods, 413 over 256 KB, signature check, then a placeholder that returns 200 `ok` for a signed POST
    - Wrap everything in one try so an unexpected error returns 200 after the signature check and 403 before it, logging only an event name and the exception type name
    - Add short plain-English docstrings and type hints
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 7.5, 7.6, 7.7, 8.1, 9.1, 9.2, 9.3_

  - [x]* 2.2 Create the shared test helpers in `tests/whatsapp_fakes.py`
    - Add `sign(body, secret)`, payload builders for a text message, an image message, a status update and a payload with several messages, `RecordingSend`, `FakeCheck` (counts calls, records arguments, returns a given reply or raises), a fixed Lagos clock and a fake explainer
    - Add Hypothesis strategies for sender numbers, message ids, texts, headers, queries, arbitrary bodies and distinctive fake secrets
    - Use synthetic data and obviously fake secrets only
    - _Requirements: 16.1, 16.3_

  - [x]* 2.3 Write property test for totality
    - Create `tests/test_whatsapp_prop_01_total.py`
    - **Property 1: The handler is total**
    - **Validates: Requirements 3.1, 9.1, 9.3**

  - [x]* 2.4 Write property test for unproven requests
    - Create `tests/test_whatsapp_prop_02_unsigned.py`
    - **Property 2: Unproven requests are never processed**
    - **Validates: Requirements 2.2, 2.3, 2.4, 2.5, 2.7**

  - [x]* 2.5 Write property test for GET verification
    - Create `tests/test_whatsapp_prop_06_get_verify.py`
    - **Property 6: GET verification matches the token**
    - **Validates: Requirements 1.1, 1.3, 1.4**

  - [x]* 2.6 Write property test for the Seen_Set bound
    - Create `tests/test_whatsapp_prop_08_seen_bounded.py`
    - **Property 8: The Seen_Set stays bounded and forgets the oldest**
    - **Validates: Requirements 7.5**

  - [x]* 2.7 Write example tests for the gate
    - Create `tests/test_whatsapp_gate_examples.py`: 413 at the limit plus one byte and 200 at the limit; 405 for `PUT`; token and secret read at request time; a bad signature example; a signature over non-UTF-8 bytes; an unexpected error before the signature passes gives 403 (inject a failing helper)
    - _Requirements: 1.5, 2.1, 2.4, 2.6, 2.7, 2.8, 2.9, 16.6_

- [x] 3. Message processing in `whatsapp.py`
  - [x] 3.1 Add payload parsing, the check, the reply and dedupe to `whatsapp.py`
    - Add `extract_messages(payload)` that reads `entry[].changes[].value.messages[]` defensively, accepts only a `from` of 1 to 20 digits, and returns `IncomingMessage` items with kind `text` or `other`
    - Add `build_reply_request(...)` and `default_send(...)` (urllib, HTTP error status returned, one attempt, 5 second timeout)
    - Add `_resolve_explainer` (lazy `get_explainer` from `ghost_credit.ai_explainer`, falling back to `TemplateExplainer`), `_send_reply` (checks the token and the phone number id, logs `send_skipped`, `webhook_send_failed`) and `_process_message` (runs inside its own try)
    - Replace the placeholder in `handle_webhook`: parse JSON (invalid JSON gives 200 and nothing sent), skip status updates, dedupe by message id, call `check(text, None, None, category, now, reader=..., paystack_verify=..., network=..., explainer=...)` with text cut to 2000 characters, cut the reply to 4096 characters, send it to the same number, and send `ASK_FOR_SMS_REPLY` for non-text messages with no media request
    - Use defaults `FakeScreenshotReader()`, `make_paystack_verify()`, `get_network()`, `run_check` and the Lagos clock when nothing is injected, and read `MERCHANT_CATEGORY` at request time with default `other`
    - Log only event names, exception type names and status codes
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 4.10, 5.1, 5.2, 5.3, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 7.1, 7.2, 7.3, 7.4, 8.1, 8.2, 8.3, 8.4, 8.5, 9.2_

  - [x]* 3.2 Write property test for a signed text message
    - Create `tests/test_whatsapp_prop_03_signed_text.py`
    - **Property 3: A signed text message gets one check and one reply to the same number**
    - **Validates: Requirements 4.1, 4.3, 4.9, 4.10, 6.1, 6.2, 6.3, 6.4, 7.1**

  - [x]* 3.3 Write property test for long text
    - Create `tests/test_whatsapp_prop_04_long_text.py`
    - **Property 4: Long text is cut to 2000 characters**
    - **Validates: Requirements 4.2**

  - [x]* 3.4 Write property test for non-text messages
    - Create `tests/test_whatsapp_prop_05_non_text.py`
    - **Property 5: A signed non-text message gets the fixed ask and no check**
    - **Validates: Requirements 5.1, 5.2, 5.3**

  - [x]* 3.5 Write property test for dedupe
    - Create `tests/test_whatsapp_prop_07_dedupe.py`
    - **Property 7: A repeated message is processed once**
    - **Validates: Requirements 7.3, 7.4**

  - [x]* 3.6 Write property test for failure isolation
    - Create `tests/test_whatsapp_prop_09_failure_isolation.py`
    - **Property 9: One failing message does not stop the rest**
    - **Validates: Requirements 3.5, 7.1, 7.2, 9.2**

  - [x]* 3.7 Write property test for privacy
    - Create `tests/test_whatsapp_prop_10_privacy.py`
    - **Property 10: Logs, responses and replies hold no secret or customer data**
    - **Validates: Requirements 8.1, 8.2, 8.3**

  - [x]* 3.8 Write example tests for recorded payloads and wiring
    - Create `tests/test_whatsapp_examples.py`: a recorded text payload, an image payload, a status-update payload, a duplicate message id and an over-long text; invalid JSON; a message with a bad `from`; two messages in order
    - Default wiring with no injected parts, `PATTERN_NETWORK=off` and no Paystack key, making no network call
    - Explainer choice with a fake `ghost_credit.ai_explainer` module in `sys.modules`, with the module missing and with a raising `get_explainer`
    - Send timeout of 5 seconds with one attempt, a raising send, a non-2xx status, and `send_skipped` when the token or phone number id is missing or malformed
    - _Requirements: 3.2, 3.3, 3.4, 3.5, 4.4, 4.5, 4.6, 4.7, 4.8, 6.4, 6.5, 6.6, 16.1, 16.2, 16.5, 16.6_

  - [x]* 3.9 Write smoke checks for `whatsapp.py`
    - Create `tests/test_whatsapp_smoke.py`: the module imports only the standard library and `ghost_credit` modules, uses `hmac.compare_digest`, has no `open(` call and no AI model name, defines `GRAPH_API_VERSION` once, passes `sender_id` as None to the check, and its docstring says dedupe is best effort
    - _Requirements: 1.2, 2.3, 6.7, 6.8, 7.7, 8.4, 8.5_

- [x] 4. Checkpoint - Ensure all tests pass
  - Run the whole suite with `PATTERN_NETWORK=off`, including the existing screenshot tests. Ensure all tests pass, ask the user if questions arise.
  - _Requirements: 10.5, 16.2_

- [x] 5. Lambda adapter
  - [x] 5.1 Create `src/ghost_credit/lambda_handler.py`
    - Add `lambda_handler(event, context)` that reads `requestContext.http.method`, `queryStringParameters`, `headers` (names lowercased) and `body`, decodes base64 when `isBase64Encoded` is true, and encodes text as UTF-8 otherwise (empty bytes when missing)
    - Call `handle_webhook` with all defaults and return `{"statusCode", "headers", "body"}`
    - Return 403 `forbidden` for a non-dict event, an undecodable body or any unexpected error, and never raise
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7_

  - [x]* 5.2 Write property test for body decoding
    - Create `tests/test_whatsapp_prop_11_lambda_body.py`
    - **Property 11: Lambda body decoding keeps the raw bytes**
    - **Validates: Requirements 11.2, 11.3**

  - [x]* 5.3 Write property test for adapter totality
    - Create `tests/test_whatsapp_prop_12_lambda_total.py`
    - **Property 12: The Lambda adapter is total and well shaped**
    - **Validates: Requirements 11.4, 11.5, 11.6**

  - [x]* 5.4 Write example tests for the Lambda adapter
    - Create `tests/test_lambda_handler_examples.py`: a v2.0 GET verification event, a signed POST with a base64 body and a fake send, an unsigned POST, a non-dict event, and an import of the module with `PIL` and `imagehash` blocked
    - _Requirements: 11.1, 11.2, 11.4, 11.5, 10.3_

- [x] 6. Deploy script
  - [x] 6.1 Create `scripts/deploy_lambda.py` and `tests/deploy_helpers.py`
    - Add the constants and the pure helpers `parse_env_text`, `select_lambda_variables`, `missing_whatsapp_names`, `is_test_key` (prefix built from `"sk_"` and `"test_"`), `build_zip` (only `ghost_credit/` paths; no tests, `.env`, `__pycache__`, `.pyc` or `.hypothesis`), `trust_policy`, `permissions_policy(account_id)` and `format_plan`
    - Add `main(argv)` with `--dry-run` and `--env-file`: read the env file, run the test-key gate and the missing-name check before any AWS call, build the zip in memory, and print only names, counts and the Function URL
    - Add the AWS step functions that import `boto3` only when called: STS account id, create or update the role and inline policy, create or update the function code and configuration (python3.12, handler `ghost_credit.lambda_handler.lambda_handler`, 30 seconds, 256 MB, the selected variables), create or update the Function URL with auth type `NONE`, add the two permissions (an existing permission counts as success)
    - Print only an exception type name and the AWS error code on failure, never a value
    - Add `tests/deploy_helpers.py` with a loader that imports `scripts/deploy_lambda.py` by file path
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7, 12.8, 12.9, 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, 13.7, 13.8, 13.9, 14.1, 14.2, 14.3, 14.4, 14.5, 14.6_

  - [x]* 6.2 Write property test for env parsing
    - Create `tests/test_deploy_prop_13_env_round_trip.py`
    - **Property 13: Env file parsing round trips**
    - **Validates: Requirements 12.3**

  - [x]* 6.3 Write property test for variable selection
    - Create `tests/test_deploy_prop_14_select_variables.py`
    - **Property 14: Variable selection keeps only the allowed names**
    - **Validates: Requirements 12.4, 12.5, 12.6**

  - [x]* 6.4 Write property test for hidden values
    - Create `tests/test_deploy_prop_15_plan_hides_values.py`
    - **Property 15: The printed plan and errors hold no values**
    - **Validates: Requirements 12.7, 14.4, 14.6**

  - [x]* 6.5 Write property test for the test-key gate
    - Create `tests/test_deploy_prop_16_test_key_gate.py`
    - **Property 16: Only test keys pass the gate**
    - **Validates: Requirements 14.1, 14.2**

  - [x]* 6.6 Write example tests and smoke checks for the script
    - Create `tests/test_deploy_examples.py`: the permission actions are exactly `bedrock:InvokeModel`, `logs:CreateLogGroup`, `logs:CreateLogStream` and `logs:PutLogEvents` with the resources from Requirement 13; the trust policy names only `lambda.amazonaws.com`; the zip built from a temporary tree with decoy `.env`, `tests`, `__pycache__`, `.pyc` and `.hypothesis` entries holds none of them and every name starts with `ghost_credit/`; a dry run with a temporary env file makes no AWS call and prints names only; a live-looking Paystack key stops the run before any AWS call; the script imports with `boto3` blocked; the source has no literal holding the whole test-key prefix
    - _Requirements: 12.1, 12.2, 12.9, 13.1, 13.2, 13.3, 13.4, 14.1, 14.3, 14.4, 14.5, 16.4_

- [x] 7. Deploy guide and `.env.example`
  - [x] 7.1 Write `docs/deploy.md` and update `.env.example`
    - Write short numbered steps with exact PowerShell commands: prerequisites (AWS CLI credentials, `python -m pip install boto3`, `.env` filled), dry run, deploy, paste the Function URL and the verify token into the Meta webhook settings, subscribe to `messages`, test, update (run the script again) and delete (the AWS CLI commands for the function URL, function, role policy, role and log group)
    - State that Lambda ships `boto3` so no layer is needed, that the in-memory dedupe and any in-memory used-payments ledger last only as long as one container so a durable store needs approval, and that deploying needs Ayobami's approval and is run by the user
    - Add the new variable names with empty values to `.env.example` (create the file if it does not exist), with no real value and no personal email address
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 15.6, 15.7_

  - [x]* 7.2 Write a smoke check for the guide and the example file
    - Create `tests/test_deploy_docs_smoke.py`: `docs/deploy.md` holds numbered steps, the dry-run and deploy commands, the `boto3` and durable-store notes, no `@` email address and no key-like value; `.env.example` lists every Lambda variable name with an empty value
    - _Requirements: 15.1, 15.3, 15.4, 15.6, 15.7_

- [x] 8. Final checkpoint - Ensure all tests pass
  - Run the whole suite with `PATTERN_NETWORK=off` and fix any failure. Ensure all tests pass, ask the user if questions arise.
  - _Requirements: 10.5, 16.1, 16.2, 16.4, 16.5_

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP. The user asked for every test sub-task to be listed, so each test file is its own sub-task. Skipping 2.2 breaks the tests that import `tests/whatsapp_fakes.py`.
- Each task references specific requirements for traceability.
- Property tests use Hypothesis with at least 100 examples. Unit tests cover specific examples and edge cases.
- Tasks 2.1 and 3.1 both edit `whatsapp.py`, so the dependency graph puts them in separate waves.
- The AWS calls in task 6.1 are not run by any test. The user runs the dry run and the deploy.
- This workflow only creates the spec. No code has been written.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "2.1"] },
    { "id": 1, "tasks": ["1.2", "2.2", "3.1"] },
    { "id": 2, "tasks": ["2.3", "2.4", "2.5", "2.6", "2.7", "3.2", "3.3", "3.4", "3.5", "3.6", "3.7", "3.8", "3.9"] },
    { "id": 3, "tasks": ["4"] },
    { "id": 4, "tasks": ["5.1", "6.1", "7.1"] },
    { "id": 5, "tasks": ["5.2", "5.3", "5.4", "6.2", "6.3", "6.4", "6.5", "6.6", "7.2"] },
    { "id": 6, "tasks": ["8"] }
  ]
}
```
