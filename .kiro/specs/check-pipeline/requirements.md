# Requirements Document

## Introduction

The Check_Pipeline is the one function the app calls to check a credit alert from start to finish. It reads the alert text and/or a screenshot, merges what each source found, asks Paystack, asks the pattern network, lets the rules decide the verdict, builds the reply for the shop owner and reports the pattern to the network. It lives in `src/ghost_credit/pipeline.py`.

The pipeline only wires existing parts together. It holds no rules of its own, and it contains no AI call. Every dependency is passed in, so tests run with fakes and no network.

Parts it uses, with the spec that owns each:
- `alert-parser`: `parse_sms_alert`, `ParsedAlert` and `RED_FLAG_CODES` from `src/ghost_credit/parser.py`.
- `screenshot-reader`: the `ScreenshotReader` interface and `FakeScreenshotReader` from `src/ghost_credit/screenshot.py`.
- `paystack-verifier`: `verify(parsed, secret_key, now, *, http=None)` and its `PaystackResult` from `src/ghost_credit/paystack.py`. That `PaystackResult` has fields `status`, `checked`, `matched_reference`, `amount_kobo`, `paid_at` and `reason`.
- `pattern-network-hook` (being built): `src/ghost_credit/pattern_network.py` with `PatternNetwork`, `NoopPatternNetwork`, `Signals`, `Verdict`, `LookupResult`, `ReportReceipt`, `safe_lookup(network, signals)` and `safe_report(network, verdict, signals)`, plus the builder that fills Signals with privacy-safe hash fields.
- `verdict-engine`: `src/ghost_credit/verdict.py` with `decide(parsed, paystack_result, lookup_result)`, `risk_notes(parsed, *, alert_text, large_amount_kobo)`, `decide_with_notes(parsed, paystack_result, lookup_result, *, alert_text, large_amount_kobo)` returning a frozen `Decision` (fields `verdict` and `risk_notes`), `Explainer`, `TemplateExplainer` and `build_reply(verdict, parsed, explainer, risk_notes=None)`. The engine uses the `PaystackResult` of `src/ghost_credit/paystack.py` directly and defines no second type.

Two decisions made here, where the existing specs leave a gap:
- **One PaystackResult type.** The pipeline passes the `PaystackResult` from `paystack.py` straight to the engine, with no conversion. The engine already treats an UNAVAILABLE result, an unchecked result and an unreadable amount as no Paystack check, so the pipeline only passes such a result on.
- **One Paystack callable shape.** The pipeline calls `paystack_verify(parsed, now)`. The secret key is never a parameter of `run_check`. A helper builds that callable from the real `verify` and reads the key from the environment variable `PAYSTACK_SECRET_KEY` (Requirement 3).

Out of scope: any AI model or vision reader, HTTP routes, WhatsApp or SMS delivery, storing results, owner follow-up answers ("fake" or "real"), and the contents of the verdict rules. The pipeline never writes to disk.

## Glossary

- **Check_Pipeline**: The module `src/ghost_credit/pipeline.py`.
- **Run_Check**: The function `run_check(text, sender_id, image_bytes, merchant_category, now, *, reader, paystack_verify, network, explainer)` that returns a Check_Result.
- **Check_Result**: A frozen dataclass with fields `check_id`, `parsed`, `paystack_result`, `verdict`, `reply` and `risk_notes`. Its `paystack_result` holds the Paystack_Result.
- **Check_Id**: A UUID version 4 written as a string, made once per Run_Check call.
- **Alert_Text**: The `text` argument, usable only when it is a string with at least one non-whitespace character.
- **Alert_Image**: The `image_bytes` argument, usable only when it is non-empty `bytes`.
- **Parsed_Alert**: The `ParsedAlert` dataclass from `alert-parser`.
- **Merged_Alert**: The Parsed_Alert produced by the Merge_Rule from the text-derived and screenshot-derived alerts.
- **Merge_Rule**: The rule in Requirement 2 for combining two Parsed_Alert values.
- **Reader**: An object with `read(image_bytes) -> ParsedAlert`, the `ScreenshotReader` interface.
- **Paystack_Callable**: A function with the shape `Callable[[ParsedAlert, datetime], paystack.PaystackResult]`. It holds the secret key inside itself.
- **Paystack_Result**: The `ghost_credit.paystack.PaystackResult` dataclass, with fields `status` (`CONFIRMED`, `NOT_FOUND` or `UNAVAILABLE`), `checked`, `matched_reference`, `amount_kobo`, `paid_at` and `reason`. The pipeline and the verdict-engine both use this one type.
- **Unavailable_Paystack_Result**: A fixed Paystack_Result with `status` "UNAVAILABLE", `checked` False and `reason` "could not check Paystack", with the other fields None.
- **Decision**: The frozen dataclass returned by `decide_with_notes`, with fields `verdict` and `risk_notes`.
- **Red_Flag_Code**: An entry of `RED_FLAG_CODES` in `src/ghost_credit/parser.py`: SENDER_ID_MISMATCH, BALANCE_LINE_MISSING, AMOUNT_FORMAT_ODD, DATE_ODD, PRESSURE_LANGUAGE, SCREENSHOT_EDIT_SIGNS and TRANSFER_REQUEST_WORDING.
- **Network**: An object that implements `PatternNetwork`. The default is `NoopPatternNetwork`.
- **Explainer**: The verdict-engine interface that writes the wording of a reply. The default is `TemplateExplainer`.
- **Verdict**: The dataclass from `pattern-network-hook`. Its `code` is `CONFIRMED`, `NOT_FOUND`, `SUSPICIOUS` or `UNVERIFIED`.
- **Check_Reminder**: The exact sentence `Check your own bank app before releasing goods.`
- **Safe_Fallback_Result**: The Check_Result returned when the check cannot be completed, defined in Requirement 7.
- **Fallback_Reason**: The fixed sentence `The check could not be completed.`
- **Secret_Key**: The Paystack secret key read from the environment variable `PAYSTACK_SECRET_KEY`.
- **Kobo**: The integer money unit. NGN 45,000 equals 4500000 kobo.
- **Used_References**: A ledger object with two methods: `is_used(reference: str) -> bool` and `mark_used(reference: str) -> None`. It records which Paystack payment references were already used for an earlier check. It is passed to Run_Check as the optional keyword-only parameter `used_references`.
- **InMemoryUsedReferences**: The small Used_References implementation in `pipeline.py`. It keeps the references in a set guarded by a lock. It lasts only as long as one process (for example one serverless container) and is empty again when the process restarts.
- **Already_Used_Reason**: The constant `REASON_ALREADY_USED` of `src/ghost_credit/paystack.py`, equal to `"This payment was already used for an earlier check"`.

## Requirements

### Requirement 1: Entry point and result

**User Story:** As a developer, I want one function that runs a whole check, so that every channel of the app gets the same answer from the same steps.

#### Acceptance Criteria

1. THE Check_Pipeline SHALL provide Run_Check with the parameters `text`, `sender_id`, `image_bytes`, `merchant_category` and `now`, followed by the keyword-only parameters `reader`, `paystack_verify`, `network` and `explainer`.
2. THE Run_Check SHALL return a Check_Result with the fields `check_id`, `parsed`, `paystack_result`, `verdict`, `reply` and `risk_notes`.
3. THE Run_Check SHALL set `check_id` to a new Check_Id on every call.
4. THE Run_Check SHALL set `parsed` to the Merged_Alert, `paystack_result` to the Paystack_Result passed to the verdict-engine, `verdict` to the `verdict` of the Decision returned by `decide_with_notes`, and `reply` to the string returned by `build_reply`.
5. THE Run_Check SHALL set `risk_notes` to the `risk_notes` of the same Decision, as a list of strings, and to an empty list when the Decision holds none.
6. WHERE a keyword-only parameter is not supplied, THE Run_Check SHALL use `FakeScreenshotReader()` for `reader`, the Paystack_Callable from the helper in Requirement 3 for `paystack_verify`, `NoopPatternNetwork()` for `network`, and `TemplateExplainer()` for `explainer`.
7. THE Run_Check SHALL call the steps in this order: read and merge, Paystack check, network lookup, `decide_with_notes`, `build_reply`, network report.
8. THE Check_Pipeline SHALL contain no AI model name, AI client or AI call, and THE Run_Check SHALL reach an AI model only through an injected Reader or Explainer.

### Requirement 2: Read the alert and merge the sources

**User Story:** As a shop owner, I want the app to use both the SMS text and the screenshot when I send both, so that nothing either one shows is lost.

#### Acceptance Criteria

1. WHEN the Alert_Text is usable, THE Run_Check SHALL call `parse_sms_alert(text, sender_id)` once to produce the text-derived alert.
2. WHEN the Alert_Image is usable, THE Run_Check SHALL call `reader.read(image_bytes)` once to produce the screenshot-derived alert.
3. WHEN both sources are usable, THE Run_Check SHALL build the Merged_Alert so that each field found in both sources takes the text-derived value, and each field found only in the screenshot-derived alert takes the screenshot-derived value.
4. THE Run_Check SHALL treat a field as found when its value is not None.
5. THE Run_Check SHALL set `screenshot_phash` of the Merged_Alert to the value from the screenshot-derived alert, or None when no screenshot was read.
6. THE Run_Check SHALL set `red_flags` of the Merged_Alert to the union of both sources, with each code once, in the order of `RED_FLAG_CODES`, so that SCREENSHOT_EDIT_SIGNS and TRANSFER_REQUEST_WORDING are kept when either source reports them.
7. THE Run_Check SHALL set `sender_id` of the Merged_Alert to the `sender_id` argument when the argument is a string, and to None otherwise.
8. WHEN only one source is usable, THE Run_Check SHALL use that source as the Merged_Alert, with `sender_id` set as in criterion 7.
9. WHEN neither the Alert_Text nor the Alert_Image is usable, THE Run_Check SHALL return a Check_Result with verdict code `UNVERIFIED` and reply built from the Fallback_Reason (the Safe_Fallback_Result in Requirement 7), and SHALL make no Paystack, network or explainer call.
10. IF `reader.read` raises an error or returns a value that is not a Parsed_Alert, THEN THE Run_Check SHALL treat the screenshot-derived alert as an empty Parsed_Alert and continue the check.
11. WHEN `reader.read` has returned or failed, THE Run_Check SHALL keep no reference to the Alert_Image, so that only the `screenshot_phash` text outlives the read.
12. WHEN a text-derived alert and a screenshot-derived alert are merged, THE Run_Check SHALL leave both input alerts unchanged.

### Requirement 3: Paystack check

**User Story:** As a shop owner, I want the app to look for the payment in my own Paystack account, so that a matching payment can turn the answer into ALIVE.

#### Acceptance Criteria

1. THE Run_Check SHALL call `paystack_verify(merged_alert, now)` exactly once per check, with no secret key in the call.
2. THE Check_Pipeline SHALL provide a helper `make_paystack_verify(http=None)` that returns a Paystack_Callable wrapping `paystack.verify`.
3. WHEN the Paystack_Callable made by the helper is called, THE helper SHALL read the Secret_Key from the environment variable `PAYSTACK_SECRET_KEY` at that moment and pass it to `paystack.verify` together with the optional `http` function.
4. IF `PAYSTACK_SECRET_KEY` is unset or empty, THEN THE Paystack_Callable made by the helper SHALL pass None as the key, so that `paystack.verify` answers UNAVAILABLE without any network call.
5. THE Check_Pipeline SHALL write the Secret_Key to no log message, error message, Check_Result field or exception text.
6. WHEN the Paystack_Callable returns a Paystack_Result, THE Run_Check SHALL pass that Paystack_Result unchanged to `decide_with_notes` and store it in `Check_Result.paystack_result`.
7. WHEN the Paystack_Result has `status` "UNAVAILABLE", has `checked` False, or follows an unreadable alert amount, THE Run_Check SHALL pass it on unchanged, because the verdict-engine treats it as no Paystack check.
8. IF the Paystack_Callable raises an error, THEN THE Run_Check SHALL use the Unavailable_Paystack_Result in its place and continue the check.
9. IF the Paystack_Callable returns a value that is not a Paystack_Result, THEN THE Run_Check SHALL use the Unavailable_Paystack_Result in its place and continue the check.
10. THE Run_Check SHALL pass `now` to the Paystack_Callable unchanged.

### Requirement 4: Network lookup

**User Story:** As a shop owner, I want the app to ask the pattern network about the alert without leaking my customer's details, so that known scams can make my verdict stricter.

#### Acceptance Criteria

1. WHEN the Merged_Alert has an `amount_kobo` that is an integer, THE Run_Check SHALL build one Signals value for the check using the privacy-aware Signals builder of `pattern-network-hook`.
2. THE Run_Check SHALL fill the Signals fields as follows: `check_id` from the Check_Id; `checked_at` from `now` as ISO 8601 text with the Lagos offset `+01:00`, treating a naive `now` as Lagos time; `amount_kobo`, `claimed_bank`, `sender_id`, `claimed_reference`, `screenshot_phash` and `red_flags` from the Merged_Alert; `currency` "NGN"; and `merchant_category` from the argument.
3. WHEN the Alert_Text is usable, THE Run_Check SHALL set the Signals `channel` to "sms".
4. WHEN only the Alert_Image is usable, THE Run_Check SHALL set the Signals `channel` to "screenshot".
5. THE Run_Check SHALL pass no raw payer name, phone number or account number to the Signals builder, so that the three payer hash fields are None.
6. IF `merchant_category` is not a string or is empty after trimming, THEN THE Run_Check SHALL use the category "other".
7. THE Run_Check SHALL call `safe_lookup(network, signals)` once per check and SHALL pass the returned LookupResult to `decide_with_notes`.
8. IF the Merged_Alert has no integer `amount_kobo`, THEN THE Run_Check SHALL build no Signals, SHALL call neither `safe_lookup` nor `safe_report`, and SHALL pass a LookupResult with `network_available` False, `matched` False and an empty `matches` list to `decide_with_notes`.
9. IF building the Signals fails, THEN THE Run_Check SHALL continue as in criterion 8.
10. THE Run_Check SHALL use the Verdict code from `decide_with_notes` and SHALL NOT change it using the LookupResult or any Network value.

### Requirement 5: Decide and explain

**User Story:** As a shop owner, I want a short reply that tells me what to do, so that I know whether to release my goods.

#### Acceptance Criteria

1. THE Run_Check SHALL call `decide_with_notes(merged_alert, paystack_result, lookup_result, alert_text=text)` once per check, passing `text` only when it is a string and None otherwise, and use the returned Decision unchanged.
2. THE Run_Check SHALL call `build_reply(decision.verdict, merged_alert, explainer, decision.risk_notes)` once per check and use the returned string as `reply`.
3. THE Run_Check SHALL leave the verdict code, `decided_by` and `reasons` of the Verdict unchanged after `decide_with_notes` returns.
4. WHEN the Verdict code is `NOT_FOUND`, `SUSPICIOUS` or `UNVERIFIED`, THE Check_Result `reply` SHALL end with the Check_Reminder.
5. THE Check_Result SHALL have the Verdict code `CONFIRMED` if and only if `decide_with_notes` returns `CONFIRMED` for the same Paystack_Result, and SHALL have a Verdict code other than `CONFIRMED` whenever the Paystack_Result does not have `status` "CONFIRMED".
6. WHEN the Paystack_Result is not a checked result, the Merged_Alert has no red flags and the LookupResult has `network_available` True and `matched` True, THE Check_Result SHALL have the Verdict code `SUSPICIOUS`.
7. WHEN the Paystack_Result is not a checked result, the Merged_Alert has no red flags and the LookupResult is not a network match, THE Check_Result SHALL have the Verdict code `UNVERIFIED`.

### Requirement 6: Report to the network

**User Story:** As a shop owner, I want suspicious alerts reported in the background, so that other checks can learn from them without slowing down my reply.

#### Acceptance Criteria

1. WHEN the Verdict code is `NOT_FOUND`, `SUSPICIOUS` or `UNVERIFIED` and Signals were built, THE Run_Check SHALL call `safe_report(network, verdict, signals)` once, after the reply has been built.
2. WHEN the Verdict code is `CONFIRMED`, THE Run_Check SHALL make no report call.
3. THE Run_Check SHALL make no report call on the Safe_Fallback_Result path.
4. THE Run_Check SHALL NOT wait for the report to finish, so that the report call never delays the return of the Check_Result.
5. IF `safe_report` raises an error, THEN THE Run_Check SHALL discard the error and return the Check_Result unchanged.
6. THE Run_Check SHALL pass the Verdict to `safe_report` with `owner_outcome` "unknown".
7. THE Run_Check SHALL call `safe_report` with the same Signals, including the same `check_id`, that it passed to `safe_lookup`.

### Requirement 7: Safe failure

**User Story:** As a shop owner, I want the app to give me a cautious answer whenever something goes wrong, so that a software fault never tells me money is real.

#### Acceptance Criteria

1. THE Run_Check SHALL return a Check_Result for every input, including `None` or a non-string `text`, a non-string `sender_id`, non-bytes `image_bytes`, any `merchant_category`, any `now`, and injected dependencies that raise errors.
2. IF any step raises an error that this document does not handle by a specific rule, THEN THE Run_Check SHALL return the Safe_Fallback_Result.
3. THE Safe_Fallback_Result SHALL have a Verdict with code `UNVERIFIED`, `decided_by` "rules", `paystack_checked` False, `owner_outcome` "unknown" and `reasons` equal to a list holding the Fallback_Reason.
4. THE Safe_Fallback_Result SHALL have a `reply` equal to the Fallback_Reason, one space and the Check_Reminder, so that the reply ends with the Check_Reminder.
5. THE Safe_Fallback_Result SHALL hold the Merged_Alert when it was built before the failure, and an empty Parsed_Alert otherwise.
6. THE Safe_Fallback_Result SHALL have the Unavailable_Paystack_Result as `paystack_result` and an empty `risk_notes` list.
7. THE Safe_Fallback_Result SHALL be built from fixed values in `pipeline.py` that depend on no injected object.
8. THE Run_Check SHALL leave the Explainer unable to change the Verdict code, because THE Run_Check SHALL read the Verdict code only from the Decision returned by `decide_with_notes`.

### Requirement 8: Privacy, secrets and money

**User Story:** As a shop owner, I want my customers' screenshots and my keys kept private, so that using Ghost Credit puts nothing at risk.

#### Acceptance Criteria

1. THE Check_Pipeline SHALL write no image bytes, alert text, sender value, Secret_Key, hash or Signals value to any log.
2. WHERE the Check_Pipeline logs a failure, THE Check_Pipeline SHALL log only the name of the failed step and the exception type name.
3. THE Check_Pipeline SHALL store no image bytes in a file, a module-level variable, a Check_Result field or a cache.
4. THE Check_Pipeline SHALL write no file to disk.
5. THE Check_Pipeline SHALL carry every money amount as an integer in kobo and SHALL perform no float arithmetic on money.
6. THE Check_Pipeline SHALL contain no code from Fake Alert Shield, Meko, `fake-alert-eval` or any other external project.
7. THE Check_Pipeline SHALL hold no secret, token or key in source code, tests or documentation.

### Requirement 9: Tests

**User Story:** As a developer, I want automated tests for the pipeline, so that a later change cannot weaken a safety rule.

#### Acceptance Criteria

1. THE Check_Pipeline test suite SHALL use only fakes for the Reader, Paystack_Callable, Network and Explainer, and SHALL make no network call, no AI call and no live Paystack call.
2. THE Check_Pipeline test suite SHALL include a Hypothesis property test that, for any `text`, `sender_id`, `image_bytes`, `merchant_category` and `now` values (including None and wrong types), and for dependencies that either succeed or raise, Run_Check returns a Check_Result whose Verdict code is one of the four allowed codes and never raises.
3. THE Check_Pipeline test suite SHALL include a Hypothesis property test that, for any Paystack_Result, the Verdict code is `CONFIRMED` if and only if `decide_with_notes` returns `CONFIRMED` for that same Paystack_Result (a model-based check), that the Verdict code is never `CONFIRMED` without `status` "CONFIRMED", and that `Check_Result.paystack_result` is the same object that the Paystack_Callable returned.
4. THE Check_Pipeline test suite SHALL include a Hypothesis property test that, for any two Parsed_Alert values, the Merge_Rule gives the text value for each field found in the text-derived alert, the screenshot value for each field found only in the screenshot-derived alert, and a `red_flags` list that holds each code once in `RED_FLAG_CODES` order.
5. THE Check_Pipeline test suite SHALL include a Hypothesis property test that, for any Verdict code other than `CONFIRMED`, the reply ends with the Check_Reminder.
6. THE Check_Pipeline test suite SHALL include one example test for each of these paths: the CONFIRMED path with no report call, the NOT_FOUND path, the SUSPICIOUS path with red flags, the UNVERIFIED path, a screenshot and text merge, and a network match that turns UNVERIFIED into SUSPICIOUS.
7. THE Check_Pipeline test suite SHALL include an example test showing that `safe_report` is called for each Verdict code other than `CONFIRMED` and is not called for `CONFIRMED`.
8. THE Check_Pipeline test suite SHALL include one example test that runs the whole check with `PATTERN_NETWORK=off`, the default `NoopPatternNetwork` and the default `TemplateExplainer`, and gets a valid Check_Result.
9. THE Check_Pipeline test suite SHALL include example tests for the Safe_Fallback_Result (an injected dependency that raises), for the case with no usable text and no usable image, for an unreadable screenshot, for a Paystack_Callable that raises (giving the Unavailable_Paystack_Result and a continued check), for an UNAVAILABLE Paystack_Result passed on unchanged, for `risk_notes` filled from a Friday-afternoon alert and from an `alert_text` mentioning a rider, for red flags SCREENSHOT_EDIT_SIGNS and TRANSFER_REQUEST_WORDING surviving the merge, and for `make_paystack_verify` reading `PAYSTACK_SECRET_KEY` with a fake `http` function and no real key.
10. THE Check_Pipeline test suite SHALL include an example test that the Secret_Key does not appear in the Check_Result, in captured log output or in an error message.
11. THE Check_Pipeline test suite SHALL use synthetic data only, with no real customer data, no real key and no personal email address.

### Requirement 10: Count a payment once

**User Story:** As a shop owner, I want one real Paystack payment to confirm only one check, so that a customer cannot reuse one payment to collect goods twice.

This requirement is an addition. It adds one optional keyword-only parameter after those listed in Requirement 1.1. A durable store for Used_References (for example a DynamoDB table) is out of scope: it needs approval and IAM changes first.

#### Acceptance Criteria

1. THE Run_Check SHALL accept the optional keyword-only parameter `used_references`, after `explainer`, with the default None.
2. WHERE `used_references` is None, THE Run_Check SHALL behave exactly as it does under Requirements 1 to 9 and SHALL make no ledger call.
3. WHERE `used_references` is given and no `paystack_verify` is supplied, THE Run_Check SHALL build the default Paystack_Callable so that it passes `used_references.is_used` to `paystack.verify`.
4. WHEN `used_references` is given and the Verdict code is `CONFIRMED` and `paystack_result.matched_reference` is a string, THE Run_Check SHALL call `used_references.mark_used(paystack_result.matched_reference)` once, after the reply has been built.
5. IF `used_references.mark_used` raises an error, THEN THE Run_Check SHALL discard the error, log only the step name and the exception type name, and return the Check_Result unchanged.
6. WHEN the Verdict code is not `CONFIRMED`, or `matched_reference` is not a string, or the Run_Check returns the Safe_Fallback_Result, THE Run_Check SHALL make no `mark_used` call.
7. WHEN the Paystack_Result is `NOT_FOUND` with the Already_Used_Reason, THE Run_Check SHALL pass it on unchanged, so that the Verdict code is `NOT_FOUND`, and SHALL make no `mark_used` call.
8. THE Check_Pipeline SHALL provide InMemoryUsedReferences, whose `is_used` returns True for exactly the references passed earlier to `mark_used`, and whose methods are safe to call from several threads at once.
9. THE Check_Pipeline SHALL document that InMemoryUsedReferences lasts only as long as one process, so that a restart or a second container starts with an empty ledger.
10. THE Check_Pipeline test suite SHALL include example tests for each of the following: no ledger leaves behaviour unchanged, a first matching payment gives `CONFIRMED` and one `mark_used` call, a second check with the same reference gives `NOT_FOUND` with the Already_Used_Reason and no `mark_used` call, a `mark_used` that raises leaves the `CONFIRMED` result unchanged, an `is_used` that raises gives a Verdict code other than `CONFIRMED`, and InMemoryUsedReferences used from several threads.
