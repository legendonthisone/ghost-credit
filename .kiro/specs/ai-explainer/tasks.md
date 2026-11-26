# Implementation Plan: AI Explainer

## Overview

This plan builds `src/ghost_credit/ai_explainer.py` in Python 3.11 or newer: the prompt sanitiser, the output guard, `BedrockExplainer` and the `get_explainer` factory. `verdict.py` is not changed. Tests use pytest and Hypothesis with a fake client only. No task makes a real Bedrock call, and the whole suite passes without `boto3` and with `PATTERN_NETWORK=off`. Each of the 9 correctness properties in the design is its own test file, named `tests/test_ai_explainer_prop_NN_<name>.py`, tagged `Feature: ai-explainer, Property N: <property text>`, and runs at least 100 examples.

Dependencies that must exist before task 1 starts: `src/ghost_credit/verdict.py` (Explainer, TemplateExplainer, build_reply, CHECK_REMINDER, FLAG_REASONS), `src/ghost_credit/parser.py` (ParsedAlert, RED_FLAG_CODES) and `src/ghost_credit/pattern_network.py` (Verdict).

Cost note: this is the only paid call in the product. Ayobami must approve the cost before `EXPLAINER=bedrock` is used against real Bedrock. Nothing in this plan does that.

## Tasks

- [x] 1. Create the module skeleton, prompt sanitiser, packaging and test helpers
  - [x] 1.1 Create `src/ghost_credit/ai_explainer.py` with constants, the fixed instruction and the Prompt_Sanitiser
    - Add `MODEL_ID`, `DEFAULT_REGION`, `MAX_TOKENS`, `TIMEOUT_SECONDS`, `MAX_OUTPUT_CHARS`, `MAX_ITEM_CHARS` and `SYSTEM_INSTRUCTION` (no Verdict_Code, Red_Flag_Code or Owner_Label inside it)
    - Add `_sensitive_values`, `_is_clean` (including the 7-digit run check that ignores separators between digits) and `_prompt_items` (first 3 clean reasons, first 3 clean notes, each cut to 160 characters)
    - Import nothing from `boto3` or `botocore`; small functions with type hints and short plain-English docstrings
    - _Requirements: 2.5, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.8, 3.9, 8.2, 8.3_

  - [x] 1.2 Add the `aws` optional dependency and the env example line
    - In `pyproject.toml` add `aws = ["boto3"]` under `[project.optional-dependencies]`; leave required dependencies unchanged
    - Add `EXPLAINER=` (empty value) to `.env.example`, creating it with empty values if missing; do not touch `.env`
    - _Requirements: 8.1, 8.4_

  - [x] 1.3 Create shared test helpers in `tests/ai_explainer_helpers.py`
    - Add `FakeClient` with a `converse(**kwargs)` method that records each call and, by mode, returns a recorded reply, a wrong shape, a non-text value, or raises (including an exception class named `ReadTimeoutError`)
    - Add `make_verdict`, `make_parsed` (synthetic amount and account) and Hypothesis strategies for verdict codes, reasons seeded with sensitive text, and notes
    - _Requirements: 9.1, 9.3_

  - [x]* 1.4 Write example and smoke tests for the sanitiser and packaging in `tests/test_ai_explainer_sanitiser_examples.py`
    - Items with a code name, the account, the amount or a long digit run are dropped; clean items keep their order; the cap of 3 and 160 characters holds
    - `SYSTEM_INSTRUCTION` holds the required rules and no sensitive words; `pyproject.toml` lists `boto3` only under `aws`; `.env.example` has `EXPLAINER=`; the module source has no key-like strings
    - _Requirements: 3.2, 3.4, 3.5, 3.6, 3.8, 3.9, 8.1, 8.3, 8.4_

- [x] 2. Implement the Output_Guard
  - [x] 2.1 Add `_clean_text`, `_contradicts` and `guard_output` to `ai_explainer.py`
    - Reject non-strings and blank text; replace control characters (other than newline) with a space; squeeze newlines and spaces; cut to 600 characters at a sentence end, else a word boundary
    - Whole-word, case-insensitive deny-lists: wrong-verdict claims for non-CONFIRMED codes, negative words for CONFIRMED, other verdicts' Owner_Labels, accusation and legal words; reject a run of 7 or more digits; unknown code counts as UNVERIFIED
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9_

  - [x]* 2.2 Write property test for accepted text in `tests/test_ai_explainer_prop_07_guard_output.py`
    - **Property 7: Accepted model text is clean and short**
    - **Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.8**

  - [x]* 2.3 Write property test for rejected text in `tests/test_ai_explainer_prop_08_guard_rejects.py`
    - **Property 8: Contradicting text is rejected**
    - **Validates: Requirements 5.5, 5.6, 5.7, 5.9**

  - [x]* 2.4 Write example tests for the guard in `tests/test_ai_explainer_guard_examples.py`
    - "Your payment is real" for SUSPICIOUS is rejected; "unverified" alone is allowed; a 900-character text is cut at a sentence end at or before 600 characters; control characters become spaces
    - _Requirements: 5.2, 5.3, 5.5, 5.10_

- [x] 3. Implement BedrockExplainer
  - [x] 3.1 Add the `BedrockExplainer` class to `ai_explainer.py`
    - `__init__(client=None, region=DEFAULT_REGION, model_id=MODEL_ID)`; `_make_client` imports `boto3` and `botocore.config.Config` lazily and uses `read_timeout=5`, `connect_timeout=5`, retries off, `bedrock-runtime`, the configured region and no keys
    - `_request` builds `modelId`, one `system` block, one user message and `inferenceConfig` `{"maxTokens": 200}`; `_read_text` reads `output.message.content[0].text` and returns None on a bad shape
    - `explain`: compute the TemplateExplainer text first as the fallback; no clean items means no call; one `converse` call; guard the text; return Headline (first line of the fallback), a blank line, then the text; never add the Check_Reminder
    - One outer `try/except Exception` returns the fallback; log a single line with only the exception type name, `GuardRejected` or `NoUsableText`; never log the prompt, output, reasons or notes
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 3.7, 4.1, 4.2, 4.3, 4.6, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9, 8.5, 8.6_

  - [x]* 3.2 Write property test in `tests/test_ai_explainer_prop_01_never_raises.py`
    - **Property 1: Explain never raises and changes nothing**
    - **Validates: Requirements 1.3, 6.6**

  - [x]* 3.3 Write property test in `tests/test_ai_explainer_prop_02_prompt_privacy.py`
    - **Property 2: The Prompt holds only clean reasons and notes**
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 4.6**

  - [x]* 3.4 Write property test in `tests/test_ai_explainer_prop_03_fallback_exact.py`
    - **Property 3: Any failure returns exactly the template text**
    - **Validates: Requirements 3.7, 6.1, 6.2, 6.3, 6.4, 6.5, 6.9, 8.6**

  - [x]* 3.5 Write property test in `tests/test_ai_explainer_prop_05_request_settings.py`
    - **Property 5: The request has the fixed settings**
    - Use a fake `boto3` module placed in `sys.modules` (with `monkeypatch`) to check the region and `Config`
    - **Validates: Requirements 2.1, 2.2, 2.3, 2.7, 8.6**

  - [x]* 3.6 Write property test in `tests/test_ai_explainer_prop_06_success_layout.py`
    - **Property 6: Success layout is Headline, blank line, guarded text**
    - **Validates: Requirements 1.4, 1.5, 4.1, 4.2, 4.3**

  - [x]* 3.7 Write example tests for BedrockExplainer in `tests/test_ai_explainer_examples.py`
    - Success with a recorded Converse reply; fallback after a timeout-named error; guard rejection falls back; `boto3` blocked in `sys.modules` falls back while the module still imports; fake `boto3` records `Config(read_timeout=5, connect_timeout=5, retries off)` and the region; an injected client never triggers a `boto3` import
    - With `caplog`, a fallback logs only the exception type name and no text from reasons or model output
    - _Requirements: 2.4, 2.5, 2.6, 2.8, 4.1, 5.10, 6.1, 6.3, 6.7, 6.8_

- [x] 4. Add the factory and check the reply wiring
  - [x] 4.1 Add `get_explainer(env=None, client=None)` to `ai_explainer.py` and export the public names
    - Read `EXPLAINER` from `env` or `os.environ`; trimmed lower-case `bedrock` gives `BedrockExplainer(client=client)`; everything else (unset, empty, non-string, unknown, broken mapping) gives `TemplateExplainer()`; never raise; no `boto3` import, no network
    - Add `__all__` with `BedrockExplainer`, `get_explainer` and `guard_output`
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 8.5_

  - [x]* 4.2 Write property test in `tests/test_ai_explainer_prop_09_factory.py`
    - **Property 9: The factory defaults to template**
    - **Validates: Requirements 7.1, 7.2, 7.3, 7.5, 7.6**

  - [x]* 4.3 Write property test in `tests/test_ai_explainer_prop_04_reminder_and_code.py`
    - **Property 4: The reminder and the verdict survive the AI**
    - Run every case through `build_reply` with a BedrockExplainer and a Fake_Client
    - **Validates: Requirements 4.4, 4.5**

  - [x]* 4.4 Write example tests for the env switch in `tests/test_ai_explainer_factory_examples.py`
    - `{"EXPLAINER": "bedrock"}`, `" Bedrock "`, `"template"`, `""`, `"gpt"` and a mapping with no key; an injected client reaches the BedrockExplainer; with `EXPLAINER` unset the fake client records zero calls
    - _Requirements: 7.2, 7.3, 7.4, 8.5_

- [x] 5. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster first version
- Each task references specific requirements for traceability
- No task calls real Bedrock. Approval and a quoted cost from Ayobami are needed first
- Property tests validate universal correctness properties; example tests cover the concrete cases

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.3"] },
    { "id": 1, "tasks": ["1.4", "2.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "2.4", "3.1"] },
    { "id": 3, "tasks": ["3.2", "3.3", "3.4", "3.5", "3.6", "3.7", "4.1"] },
    { "id": 4, "tasks": ["4.2", "4.3", "4.4"] },
    { "id": 5, "tasks": ["5"] }
  ]
}
```
