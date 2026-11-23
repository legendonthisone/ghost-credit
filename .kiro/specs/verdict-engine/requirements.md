# Requirements Document

## Introduction

The Verdict_Engine turns a parsed credit alert, a Paystack result and a pattern-network lookup into one verdict, then builds the reply the shop owner reads. The verdict comes from fixed rules, in the order written in `.kiro/steering/payments-nigeria.md` ("How the verdict is chosen"). A network match can only make an UNVERIFIED verdict stricter (SUSPICIOUS), as in safety rule 1 of `docs/pattern-network-contract.md`. A separate Explainer writes the wording of the reply and can never change the verdict.

The `decide` function lives in `src/ghost_credit/verdict.py`. It is pure: no network, file, clock or AI calls.

Inputs and outputs come from other specs and modules:
- `ParsedAlert` comes from `alert-parser` (`src/ghost_credit/parser.py`). This spec reads `red_flags`, `amount_kobo` and `alert_time`.
- `PaystackResult` is the existing dataclass in `src/ghost_credit/paystack.py`, with the fields `status`, `checked`, `matched_reference`, `amount_kobo`, `paid_at` and `reason`. This spec imports it and does not define a second type with that name. Calling Paystack is out of scope.
- `Verdict` and `LookupResult` come from `pattern-network-hook` (`src/ghost_credit/pattern_network.py`), with the fields named in the contract. This spec reads `matched` and `network_available` from `LookupResult` and fills `code`, `decided_by`, `paystack_checked`, `owner_outcome` and `reasons` of `Verdict`. The `Verdict` dataclass is not extended.

Output shape. `decide(parsed, paystack_result, lookup_result)` keeps its signature and returns a `Verdict` exactly as in the contract. `risk_notes(parsed, *, alert_text, large_amount_kobo)` returns a list of plain-English caution strings. `decide_with_notes(...)` returns a small frozen `Decision` that holds the `Verdict` and the `risk_notes`. Risk notes live only on `Decision`. They never change the verdict code or the red flags.

Out of scope: calling Paystack, calling the pattern network, parsing alerts, screenshots, sending messages to the owner, and any AI model. No AI model is named and no AI call is made, because the cost must be approved first. The Explainer is an interface with a fixed-template implementation (TemplateExplainer) and a FakeExplainer for tests.

## Glossary

- **Verdict_Engine**: The module `src/ghost_credit/verdict.py`, holding Decide_Function, Risk_Notes_Function, Decide_With_Notes, Decision, Explainer, TemplateExplainer, FakeExplainer and Reply_Builder.
- **Decide_Function**: The function `decide(parsed, paystack_result, lookup_result)` that returns a Verdict.
- **Risk_Notes_Function**: The function `risk_notes(parsed, *, alert_text=None, large_amount_kobo=50000000)` that returns a list of Risk_Note strings.
- **Decide_With_Notes**: The function `decide_with_notes(parsed, paystack_result, lookup_result, *, alert_text=None, large_amount_kobo=50000000)` that returns a Decision.
- **Decision**: A frozen dataclass with two fields, `verdict` (a Verdict) and `risk_notes` (a list of Risk_Note strings).
- **Verdict**: The dataclass from `pattern-network-hook` with fields `code`, `decided_by`, `paystack_checked`, `owner_outcome` and `reasons`.
- **Verdict_Code**: One of the four strings `CONFIRMED`, `NOT_FOUND`, `SUSPICIOUS`, `UNVERIFIED`.
- **Owner_Label**: The word shown to the owner for a Verdict_Code: `ALIVE` for CONFIRMED, `GHOST` for NOT_FOUND, `SUSPICIOUS` for SUSPICIOUS and `UNVERIFIED` for UNVERIFIED.
- **ParsedAlert**: The dataclass from `alert-parser`. Its `red_flags` field is a list of Red_Flag_Code strings. It has no field for the raw alert text.
- **Red_Flag_Code**: A string in `red_flags`. The known codes are the entries of `RED_FLAG_CODES` in `src/ghost_credit/parser.py`: SENDER_ID_MISMATCH, BALANCE_LINE_MISSING, AMOUNT_FORMAT_ODD, DATE_ODD, PRESSURE_LANGUAGE, SCREENSHOT_EDIT_SIGNS and, as the last entry, TRANSFER_REQUEST_WORDING (added by `alert-parser`).
- **PaystackResult**: The existing dataclass `ghost_credit.paystack.PaystackResult` with fields `status` (`CONFIRMED`, `NOT_FOUND` or `UNAVAILABLE`), `checked`, `matched_reference`, `amount_kobo`, `paid_at` and `reason`.
- **Paystack_Confirmed**: A PaystackResult whose `status` equals `CONFIRMED`.
- **Paystack_No_Match**: A PaystackResult whose `status` equals `NOT_FOUND` and whose `checked` is True.
- **No_Paystack_Check**: Any Paystack input that is neither Paystack_Confirmed nor Paystack_No_Match. This covers a PaystackResult with `status` `NOT_FOUND` and `checked` False, a PaystackResult with `status` `UNAVAILABLE`, None, and any value that is not a PaystackResult or has an unreadable `status` or `checked`.
- **LookupResult**: The dataclass from `pattern-network-hook` with fields including `network_available` and `matched`, both booleans.
- **Network_Match**: A LookupResult whose `network_available` is True and whose `matched` is True.
- **Risk_Note**: A plain-English caution string produced by Risk_Notes_Function. A Risk_Note is advice only and is not a reason.
- **Alert_Text**: The optional keyword argument `alert_text` (a string or None) that carries the text of the alert, because ParsedAlert has no raw text field.
- **Large_Amount_Threshold**: The keyword argument `large_amount_kobo`, an integer number of kobo. The default is 50000000 (NGN 500,000).
- **Lagos_Time**: Time at offset +01:00. A naive `alert_time` is Lagos_Time. An aware `alert_time` is converted to +01:00.
- **Explainer**: An interface with one method, `explain(verdict, parsed, risk_notes)`, that returns the explanation text of the reply as a string.
- **TemplateExplainer**: The Explainer that builds the reply from fixed templates, with no AI call and no network call.
- **FakeExplainer**: A test implementation of Explainer that returns a fixed, deterministic string and makes no external call.
- **Reply_Builder**: The function `build_reply(verdict, parsed, explainer, risk_notes=None)` that returns the final reply string for the owner.
- **Check_Reminder**: The exact sentence `Check your own bank app before releasing goods.`

## Requirements

### Requirement 1: Choose the verdict from Paystack and red flags

**User Story:** As a shop owner, I want the verdict to follow fixed rules, so that the same alert always gets the same answer.

#### Acceptance Criteria

1. WHEN the Paystack input is Paystack_Confirmed, THE Decide_Function SHALL return a Verdict with code `CONFIRMED`.
2. WHEN the Paystack input is Paystack_No_Match, THE Decide_Function SHALL return a Verdict with code `NOT_FOUND`.
3. WHEN the Paystack input is No_Paystack_Check and the ParsedAlert `red_flags` list holds one or more entries, THE Decide_Function SHALL return a Verdict with code `SUSPICIOUS`.
4. WHEN the Paystack input is No_Paystack_Check and the ParsedAlert `red_flags` list is empty and the LookupResult is not a Network_Match, THE Decide_Function SHALL return a Verdict with code `UNVERIFIED`.
5. THE Decide_Function SHALL apply rules 1 to 4 of "How the verdict is chosen" in `.kiro/steering/payments-nigeria.md` in that order and stop at the first rule that applies.
6. THE Decide_Function SHALL count any non-empty `red_flags` list as one or more red flags, including a list that holds a code outside the known Red_Flag_Code values.

### Requirement 2: Limit the effect of the pattern network

**User Story:** As a shop owner, I want a network match to only make a verdict stricter, so that a shared database can never approve a fake alert.

#### Acceptance Criteria

1. WHEN the Paystack input is No_Paystack_Check and the ParsedAlert `red_flags` list is empty and the LookupResult is a Network_Match, THE Decide_Function SHALL return a Verdict with code `SUSPICIOUS`.
2. WHEN the Paystack input is Paystack_Confirmed, THE Decide_Function SHALL return code `CONFIRMED` for every LookupResult value.
3. WHEN the Paystack input is Paystack_No_Match, THE Decide_Function SHALL return code `NOT_FOUND` for every LookupResult value.
4. THE Decide_Function SHALL return code `CONFIRMED` only when the Paystack input is Paystack_Confirmed.
5. WHERE the LookupResult has `network_available` False, THE Decide_Function SHALL return the same Verdict code as it returns for a LookupResult of None.

### Requirement 3: Fill the Verdict fields and reasons

**User Story:** As a shop owner, I want short plain-English reasons, so that I understand why I got this answer.

#### Acceptance Criteria

1. THE Decide_Function SHALL set `decided_by` to `"rules"` in every Verdict.
2. THE Decide_Function SHALL set `owner_outcome` to `"unknown"` in every Verdict.
3. THE Decide_Function SHALL set `paystack_checked` to True when the Paystack input is Paystack_Confirmed or Paystack_No_Match, and to False otherwise.
4. THE Decide_Function SHALL set `reasons` to a non-empty list of strings written in plain English, each string of 1 to 120 characters.
5. IF a reason is longer than 120 characters, THEN THE Decide_Function SHALL cut the reason to its first 120 characters, so that the limit holds for every reason whatever its source.
6. WHEN the Verdict code is `SUSPICIOUS` because of red flags, THE Decide_Function SHALL include one reason for each entry of `red_flags`, written in everyday words and naming no Red_Flag_Code.
7. WHEN the Verdict code is `SUSPICIOUS` because of a Network_Match, THE Decide_Function SHALL include one reason stating that the pattern network has seen a similar alert.
8. WHEN the Verdict code is `CONFIRMED`, THE Decide_Function SHALL include one reason stating that Paystack found a matching payment.
9. WHEN the Verdict code is `NOT_FOUND`, THE Decide_Function SHALL include one reason stating that Paystack found no matching payment.
10. WHEN the Verdict code is `UNVERIFIED`, THE Decide_Function SHALL include one reason stating that no Paystack check was possible and no red flags were found.
11. THE Decide_Function SHALL leave every Risk_Note out of `reasons`.

### Requirement 4: Keep the decision pure and total

**User Story:** As a developer, I want the decision to be a safe, side-effect-free function, so that it can sit on the money path without failing.

#### Acceptance Criteria

1. THE Decide_Function, Risk_Notes_Function and Decide_With_Notes SHALL perform no network, file, clock, random or AI calls.
2. WHEN called twice with equal arguments, THE Decide_Function SHALL return equal Verdict values.
3. THE Decide_Function SHALL return a Verdict whose code is one of the four Verdict_Code values for every input, including None for any argument.
4. IF the Paystack input is None, is not a PaystackResult, or has an unreadable `status` or `checked`, THEN THE Decide_Function SHALL treat the input as No_Paystack_Check.
5. IF the ParsedAlert is None or its `red_flags` value is not a list, THEN THE Decide_Function SHALL treat `red_flags` as empty.
6. IF the LookupResult is None or lacks a boolean `matched` or `network_available` value, THEN THE Decide_Function SHALL treat the LookupResult as not a Network_Match.
7. THE Decide_Function SHALL leave its three arguments unchanged.
8. IF an unexpected error occurs inside the Decide_Function, THEN THE Decide_Function SHALL return a Verdict with code `UNVERIFIED`, `decided_by` `"rules"` and one reason stating that the check could not be completed.

### Requirement 5: Add risk notes that never change the verdict

**User Story:** As a shop owner, I want extra cautions about risky timing, large amounts and rushed collection, so that I take more care even when the verdict is the same.

#### Acceptance Criteria

1. THE Decide_With_Notes SHALL return a Decision whose `verdict` equals the Verdict that the Decide_Function returns for the same ParsedAlert, Paystack input and LookupResult.
2. THE Decide_With_Notes SHALL leave the `red_flags` of the ParsedAlert unchanged.
3. WHEN the `alert_time` of the ParsedAlert, read as Lagos_Time, falls on a Friday at or after 14:00, or on a Saturday, or on a Sunday, THE Risk_Notes_Function SHALL include the note `Sent late on a Friday or at the weekend, a common time for fake alerts.`
4. WHEN the `amount_kobo` of the ParsedAlert is an integer at or above the Large_Amount_Threshold, THE Risk_Notes_Function SHALL include the note `Large amount. Take extra care before releasing goods.`
5. WHEN the Alert_Text contains the word rider, dispatch or driver, or the phrase "pick up now" or "pickup now", THE Risk_Notes_Function SHALL include the note `Someone is coming to collect at once. Do not release goods until the money shows in your bank app.`
6. THE Risk_Notes_Function SHALL match the words and phrases of criterion 5 as whole words, ignoring letter case, treating each run of whitespace as one space and replacing curly quotes with straight quotes before matching.
7. THE Risk_Notes_Function SHALL take the Alert_Text as the optional keyword argument `alert_text`, and WHEN `alert_text` is None or not a string, THE Risk_Notes_Function SHALL add no note under criterion 5.
8. THE Risk_Notes_Function SHALL take the Large_Amount_Threshold as the keyword argument `large_amount_kobo`, as an integer number of kobo with the default 50000000, and SHALL use no floating-point value for money.
9. IF `large_amount_kobo` is not an integer, or is a boolean, THEN THE Risk_Notes_Function SHALL use the default 50000000.
10. IF the `alert_time` is None, THEN THE Risk_Notes_Function SHALL add no note under criterion 3, and IF the `amount_kobo` is None or not an integer, THEN THE Risk_Notes_Function SHALL add no note under criterion 4.
11. THE Risk_Notes_Function SHALL return each note at most once, in the order of criteria 3, 4 and 5, and SHALL return an empty list when no note applies.
12. IF an unexpected error occurs inside the Risk_Notes_Function, THEN THE Risk_Notes_Function SHALL return an empty list.
13. THE Risk_Notes_Function SHALL leave its ParsedAlert argument unchanged.

### Requirement 6: Build the reply through an Explainer

**User Story:** As a shop owner, I want a clear, short reply written for me, so that I know what to do next.

#### Acceptance Criteria

1. THE Verdict_Engine SHALL define Explainer as an interface with the method `explain(verdict, parsed, risk_notes)` that returns a string.
2. THE TemplateExplainer SHALL build its reply from fixed templates, with no AI call and no network call.
3. THE TemplateExplainer SHALL start the reply with the Owner_Label of the Verdict code, followed by a short instruction to release (CONFIRMED), hold (NOT_FOUND and SUSPICIOUS) or check first (UNVERIFIED).
4. THE TemplateExplainer SHALL write at most three short sentences before the list of reasons.
5. THE TemplateExplainer SHALL list at most the first 3 `reasons` of the Verdict, then each Risk_Note, then, where Requirement 7 applies, the Check_Reminder as the last line.
6. THE TemplateExplainer SHALL use plain English and name no Red_Flag_Code or other code name.
7. THE Verdict_Engine SHALL provide FakeExplainer, which returns the same string for equal arguments and makes no external call.
8. THE Verdict_Engine SHALL contain no AI model name, no AI client and no AI call.
9. WHEN Reply_Builder is called, THE Reply_Builder SHALL pass the Verdict, the ParsedAlert and the risk notes to the Explainer and return a reply built from the returned text.
10. THE Reply_Builder SHALL leave the Verdict code unchanged, and THE Explainer SHALL receive no means to change the Verdict code.
11. IF the Explainer raises an error or returns a value that is not a non-empty string, THEN THE Reply_Builder SHALL build the reply from the Verdict `reasons` joined with a single space, followed by each Risk_Note.

### Requirement 7: Enforce the check reminder in every reply

**User Story:** As a shop owner, I want every unconfirmed reply to tell me to check my own bank app, so that I never release goods on a fake alert.

#### Acceptance Criteria

1. THE Reply_Builder SHALL enforce the Check_Reminder for any Explainer, including TemplateExplainer, FakeExplainer and a future AI Explainer, and no Explainer carries a duty for it.
2. WHEN the Verdict code is `NOT_FOUND`, `SUSPICIOUS` or `UNVERIFIED`, THE Reply_Builder SHALL return a reply that ends with the Check_Reminder exactly as written in the Glossary, with no characters after it.
3. WHEN the text from the Explainer already ends with the Check_Reminder, THE Reply_Builder SHALL return a reply with the Check_Reminder appearing once.
4. WHEN the Verdict code is `CONFIRMED`, THE Reply_Builder SHALL return the Explainer text without adding the Check_Reminder.
5. THE Reply_Builder SHALL place the Risk_Notes after the reasons and before the Check_Reminder, and SHALL never place a Risk_Note in `reasons`.
6. FOR ALL Explainer texts and all four Verdict codes, passing a reply returned by Reply_Builder through an Explainer that returns that same reply SHALL produce an identical reply (idempotence property).

### Requirement 8: Test the engine with properties and examples

**User Story:** As a developer, I want automated tests for the safety rules, so that a later change cannot weaken them.

#### Acceptance Criteria

1. THE Verdict_Engine test suite SHALL include a Hypothesis property test that, for any LookupResult, including any Network_Match, and any Paystack input that is not Paystack_Confirmed, the returned code is not `CONFIRMED`.
2. THE Verdict_Engine test suite SHALL include a Hypothesis property test that, for any ParsedAlert, any LookupResult and a Paystack_Confirmed input, the returned code equals `CONFIRMED`.
3. THE Verdict_Engine test suite SHALL include a Hypothesis property test that, for any ParsedAlert that carries a `screenshot_phash` and an empty `red_flags` list, any LookupResult and any Paystack input that is not Paystack_Confirmed, the returned code is not `CONFIRMED`.
4. THE Verdict_Engine test suite SHALL include a Hypothesis property test that, for any ParsedAlert, Paystack input, LookupResult, `alert_text` and `large_amount_kobo`, the Verdict code of Decide_With_Notes equals the code returned by the Decide_Function and the `red_flags` of the ParsedAlert are unchanged.
5. THE Verdict_Engine test suite SHALL include a Hypothesis property test that, for any inputs including None, the returned code is one of the four Verdict_Code values and `decided_by` equals `"rules"`.
6. THE Verdict_Engine test suite SHALL include a Hypothesis property test that, for any `red_flags` list, including codes outside the known values and long strings, every string in `reasons` has at most 120 characters.
7. THE Verdict_Engine test suite SHALL include one example test for each of rules 1 to 4, and one example test for a Network_Match turning UNVERIFIED into SUSPICIOUS.
8. THE Verdict_Engine test suite SHALL include example tests for the Paystack mapping: `NOT_FOUND` with `checked` False, `UNAVAILABLE`, None and an unreadable value each give No_Paystack_Check.
9. THE Verdict_Engine test suite SHALL include example tests for each Risk_Note, covering Friday at 13:59 (no note), Friday at 14:00 (note), Saturday, Sunday, an aware `alert_time` in another offset, an amount one kobo below and exactly at the threshold, and an `alert_text` with curly quotes and mixed letter case.
10. THE Verdict_Engine test suite SHALL include a Hypothesis property test that every reply for a verdict other than `CONFIRMED` ends with the Check_Reminder, using TemplateExplainer, FakeExplainer and an Explainer that returns arbitrary text.
11. THE Verdict_Engine test suite SHALL include example tests that TemplateExplainer shows the Owner_Label first, at most 3 reasons, the Risk_Notes after the reasons and before the Check_Reminder, and makes no network or AI call.
12. THE Verdict_Engine test suite SHALL use synthetic data only, with no secrets and no real personal data, and SHALL pass with PATTERN_NETWORK set to `off`.

### Requirement 9: Follow the project conventions

**User Story:** As a maintainer, I want the engine to follow the project steering rules, so that it fits the rest of Ghost Credit.

#### Acceptance Criteria

1. THE Verdict_Engine SHALL contain no code from Fake Alert Shield or any other external service.
2. THE Verdict_Engine SHALL hold no secret, token or key in source, tests or logs.
3. WHERE a money amount appears in a reason or reply, THE Verdict_Engine SHALL write it as an integer in kobo.
4. THE Verdict_Engine SHALL import `Verdict` and `LookupResult` from `src/ghost_credit/pattern_network.py`, `ParsedAlert` from `src/ghost_credit/parser.py` and `PaystackResult` from `src/ghost_credit/paystack.py`, without redefining them.
