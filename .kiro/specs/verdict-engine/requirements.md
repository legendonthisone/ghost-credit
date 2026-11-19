# Requirements Document

## Introduction

The Verdict_Engine turns a parsed credit alert, a Paystack outcome and a pattern-network lookup into one verdict, then builds the reply the shop owner reads. The verdict comes from fixed rules, in the order written in `.kiro/steering/payments-nigeria.md` ("How the verdict is chosen"). A network match can only make an UNVERIFIED verdict stricter (SUSPICIOUS), as in safety rule 1 of `docs/pattern-network-contract.md`. A separate Explainer writes the wording of the reply and can never change the verdict.

The `decide` function lives in `src/ghost_credit/verdict_engine.py`. It is pure: no network, file, clock or AI calls.

Inputs and outputs come from other specs:
- `ParsedAlert` comes from `alert-parser` (`src/ghost_credit/parser.py`). This spec reads only its `red_flags` field.
- `Verdict` and `LookupResult` come from `pattern-network-hook` (`src/ghost_credit/pattern_network.py`), with the fields named in the contract. This spec reads `matched` and `network_available` from `LookupResult` and fills `code`, `decided_by`, `paystack_checked`, `owner_outcome` and `reasons` of `Verdict`.
- `PaystackResult` is defined here as a small value type. The Paystack integration that produces it is out of scope.

Out of scope: calling Paystack, calling the pattern network, parsing alerts, screenshots, sending messages to the owner, and any AI model. No AI model is named and no AI call is made, because the cost must be approved first. The Explainer is an interface only, with a FakeExplainer for tests.

## Glossary

- **Verdict_Engine**: The module `src/ghost_credit/verdict_engine.py`, holding Decide_Function, PaystackResult, Explainer, FakeExplainer and Reply_Builder.
- **Decide_Function**: The function `decide(parsed, paystack_result, lookup_result)` that returns a Verdict.
- **Verdict**: The dataclass from `pattern-network-hook` with fields `code`, `decided_by`, `paystack_checked`, `owner_outcome` and `reasons`.
- **Verdict_Code**: One of the four strings `CONFIRMED`, `NOT_FOUND`, `SUSPICIOUS`, `UNVERIFIED`.
- **ParsedAlert**: The dataclass from `alert-parser`. Its `red_flags` field is a list of Red_Flag_Code strings.
- **Red_Flag_Code**: A string in `red_flags`, such as `SENDER_ID_MISMATCH` or `BALANCE_LINE_MISSING`.
- **PaystackResult**: A value type defined by this spec with one field, `state`, holding one of three values: `not_applicable` (no Paystack check is possible for this payment), `matched` (Paystack holds a payment matching the alert) or `not_found` (a Paystack check was made and found no matching payment).
- **LookupResult**: The dataclass from `pattern-network-hook` with fields including `network_available` and `matched`, both booleans.
- **Network_Match**: A LookupResult whose `network_available` is True and whose `matched` is True.
- **Explainer**: An interface with one method, `explain(verdict, parsed)`, that returns the explanation text of the reply as a string.
- **FakeExplainer**: A test implementation of Explainer that returns a fixed, deterministic string and makes no external call.
- **Reply_Builder**: The function `build_reply(verdict, parsed, explainer)` that returns the final reply string for the owner.
- **Check_Reminder**: The exact sentence `Check your own bank app before releasing goods.`

## Requirements

### Requirement 1: Choose the verdict from Paystack and red flags

**User Story:** As a shop owner, I want the verdict to follow fixed rules, so that the same alert always gets the same answer.

#### Acceptance Criteria

1. WHEN the PaystackResult state is `matched`, THE Decide_Function SHALL return a Verdict with code `CONFIRMED`.
2. WHEN the PaystackResult state is `not_found`, THE Decide_Function SHALL return a Verdict with code `NOT_FOUND`.
3. WHEN the PaystackResult state is `not_applicable` and the ParsedAlert `red_flags` list holds one or more entries, THE Decide_Function SHALL return a Verdict with code `SUSPICIOUS`.
4. WHEN the PaystackResult state is `not_applicable` and the ParsedAlert `red_flags` list is empty and the LookupResult is not a Network_Match, THE Decide_Function SHALL return a Verdict with code `UNVERIFIED`.
5. THE Decide_Function SHALL apply rules 1 to 4 of "How the verdict is chosen" in `.kiro/steering/payments-nigeria.md` in that order and stop at the first rule that applies.

### Requirement 2: Limit the effect of the pattern network

**User Story:** As a shop owner, I want a network match to only make a verdict stricter, so that a shared database can never approve a fake alert.

#### Acceptance Criteria

1. WHEN the PaystackResult state is `not_applicable` and the ParsedAlert `red_flags` list is empty and the LookupResult is a Network_Match, THE Decide_Function SHALL return a Verdict with code `SUSPICIOUS`.
2. WHEN the PaystackResult state is `matched`, THE Decide_Function SHALL return code `CONFIRMED` for every LookupResult value.
3. WHEN the PaystackResult state is `not_found`, THE Decide_Function SHALL return code `NOT_FOUND` for every LookupResult value.
4. THE Decide_Function SHALL return code `CONFIRMED` only when the PaystackResult state is `matched`.
5. WHERE the LookupResult has `network_available` False, THE Decide_Function SHALL return the same Verdict code as it returns for a LookupResult of None.

### Requirement 3: Fill the Verdict fields and reasons

**User Story:** As a shop owner, I want short plain-English reasons, so that I understand why I got this answer.

#### Acceptance Criteria

1. THE Decide_Function SHALL set `decided_by` to `"rules"` in every Verdict.
2. THE Decide_Function SHALL set `owner_outcome` to `"unknown"` in every Verdict.
3. THE Decide_Function SHALL set `paystack_checked` to True when the PaystackResult state is `matched` or `not_found`, and to False otherwise.
4. THE Decide_Function SHALL set `reasons` to a non-empty list of strings, each string of 1 to 120 characters.
5. WHEN the Verdict code is `SUSPICIOUS` because of red flags, THE Decide_Function SHALL include one reason that names every Red_Flag_Code present in `red_flags`.
6. WHEN the Verdict code is `SUSPICIOUS` because of a Network_Match, THE Decide_Function SHALL include one reason stating that the pattern network has seen a similar alert.
7. WHEN the Verdict code is `CONFIRMED`, THE Decide_Function SHALL include one reason stating that Paystack found a matching payment.
8. WHEN the Verdict code is `NOT_FOUND`, THE Decide_Function SHALL include one reason stating that Paystack found no matching payment.
9. WHEN the Verdict code is `UNVERIFIED`, THE Decide_Function SHALL include one reason stating that no Paystack check was possible and no red flags were found.

### Requirement 4: Keep the decision pure and total

**User Story:** As a developer, I want the decision to be a safe, side-effect-free function, so that it can sit on the money path without failing.

#### Acceptance Criteria

1. THE Decide_Function SHALL perform no network, file, clock, random or AI calls.
2. WHEN called twice with equal arguments, THE Decide_Function SHALL return equal Verdict values.
3. THE Decide_Function SHALL return a Verdict whose code is one of the four Verdict_Code values for every input, including None for any argument.
4. IF the PaystackResult is None or its state is not one of the three defined values, THEN THE Decide_Function SHALL treat the state as `not_applicable`.
5. IF the ParsedAlert is None or its `red_flags` value is not a list, THEN THE Decide_Function SHALL treat `red_flags` as empty.
6. IF the LookupResult is None or lacks a boolean `matched` or `network_available` value, THEN THE Decide_Function SHALL treat the LookupResult as not a Network_Match.
7. THE Decide_Function SHALL leave its three arguments unchanged.
8. IF an unexpected error occurs inside the Decide_Function, THEN THE Decide_Function SHALL return a Verdict with code `UNVERIFIED`, `decided_by` `"rules"` and one reason stating that the check could not be completed.

### Requirement 5: Define PaystackResult

**User Story:** As a developer, I want a small, fixed Paystack outcome type, so that the verdict logic does not depend on how Paystack is called.

#### Acceptance Criteria

1. THE Verdict_Engine SHALL define PaystackResult as a frozen value type with one field, `state`.
2. THE PaystackResult SHALL accept exactly the `state` values `not_applicable`, `matched` and `not_found`.
3. THE PaystackResult SHALL carry no secret, API key or customer personal data.
4. THE Verdict_Engine SHALL leave Paystack calls, Paystack authentication and the matching of an alert to a Paystack payment to a separate spec.

### Requirement 6: Build the reply through an Explainer

**User Story:** As a shop owner, I want a clear reply written for me, so that I know what to do next.

#### Acceptance Criteria

1. THE Verdict_Engine SHALL define Explainer as an interface with the method `explain(verdict, parsed)` that returns a string.
2. THE Verdict_Engine SHALL provide FakeExplainer, which returns the same string for equal arguments and makes no external call.
3. THE Verdict_Engine SHALL contain no AI model name, no AI client and no AI call.
4. WHEN Reply_Builder is called, THE Reply_Builder SHALL pass the Verdict to the Explainer and return a reply built from the returned text.
5. THE Reply_Builder SHALL leave the Verdict code unchanged, and THE Explainer SHALL receive no means to change the Verdict code.
6. IF the Explainer raises an error or returns a value that is not a non-empty string, THEN THE Reply_Builder SHALL build the reply from the Verdict `reasons` joined with a single space.

### Requirement 7: Enforce the check reminder in every reply

**User Story:** As a shop owner, I want every unconfirmed reply to tell me to check my own bank app, so that I never release goods on a fake alert.

#### Acceptance Criteria

1. THE Reply_Builder SHALL enforce the Check_Reminder, so that the rule holds for every Explainer, including a future AI Explainer, and FakeExplainer carries no special duty for it.
2. WHEN the Verdict code is `NOT_FOUND`, `SUSPICIOUS` or `UNVERIFIED`, THE Reply_Builder SHALL return a reply that ends with the Check_Reminder exactly as written in the Glossary, with no characters after it.
3. WHEN the text from the Explainer already ends with the Check_Reminder, THE Reply_Builder SHALL return a reply with the Check_Reminder appearing once.
4. WHEN the Verdict code is `CONFIRMED`, THE Reply_Builder SHALL return the Explainer text without adding the Check_Reminder.
5. FOR ALL Explainer texts and all four Verdict codes, passing a reply returned by Reply_Builder through an Explainer that returns that same reply SHALL produce an identical reply (idempotence property).

### Requirement 8: Test the engine with properties and examples

**User Story:** As a developer, I want automated tests for the safety rules, so that a later change cannot weaken them.

#### Acceptance Criteria

1. THE Verdict_Engine test suite SHALL include a Hypothesis property test that, for any ParsedAlert red flags, any PaystackResult not in state `matched` and any LookupResult, the returned code is not `CONFIRMED`.
2. THE Verdict_Engine test suite SHALL include a Hypothesis property test that, for any ParsedAlert, any LookupResult and a PaystackResult in state `matched`, the returned code equals `CONFIRMED`.
3. THE Verdict_Engine test suite SHALL include a Hypothesis property test that, for any inputs including None, the returned code is one of the four Verdict_Code values and `decided_by` equals `"rules"`.
4. THE Verdict_Engine test suite SHALL include one example test for each of rules 1 to 4, and one example test for a Network_Match turning UNVERIFIED into SUSPICIOUS.
5. THE Verdict_Engine test suite SHALL include a Hypothesis property test that every reply for a verdict other than `CONFIRMED` ends with the Check_Reminder, using FakeExplainer and an Explainer that returns arbitrary text.
6. THE Verdict_Engine test suite SHALL use synthetic data only, with no secrets and no real personal data.

### Requirement 9: Follow the project conventions

**User Story:** As a maintainer, I want the engine to follow the project steering rules, so that it fits the rest of Ghost Credit.

#### Acceptance Criteria

1. THE Verdict_Engine SHALL contain no code from Fake Alert Shield or any other external service.
2. THE Verdict_Engine SHALL hold no secret, token or key in source, tests or logs.
3. WHERE a money amount appears in a reason or reply, THE Verdict_Engine SHALL write it as an integer in kobo.
4. THE Verdict_Engine SHALL import `Verdict` and `LookupResult` from `src/ghost_credit/pattern_network.py` and `ParsedAlert` from `src/ghost_credit/parser.py`, without redefining them.
