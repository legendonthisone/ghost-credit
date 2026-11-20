# Requirements Document

## Introduction

The Paystack_Verifier checks whether the money named in a parsed credit alert exists in the shop's own Paystack account. It is one function, `verify`, in `src/ghost_credit/paystack.py`. It makes one read-only call to the Paystack API (test mode only), compares the result with the alert, and returns a PaystackResult. Only Paystack can confirm money, so this module is the only place in Ghost Credit that can produce a CONFIRMED outcome.

Inputs and outputs come from other specs:
- `ParsedAlert` comes from `alert-parser` (`src/ghost_credit/parser.py`). This spec reads only `amount_kobo`, `claimed_reference` and `alert_time`.
- The `verdict-engine` spec defines its own small `PaystackResult` with states `not_applicable`, `matched` and `not_found`. This spec's PaystackResult is the Paystack-facing result: it has the statuses `CONFIRMED`, `NOT_FOUND` and `UNAVAILABLE` and carries details. The verdict-engine will map this result to its own states later (for example `CONFIRMED` to `matched`, `NOT_FOUND` with `checked` True to `not_found`, and `UNAVAILABLE` or `checked` False to `not_applicable`). This spec does not change the verdict-engine spec and does not implement the mapping. The two types share a name only, so a later task must keep them in separate modules or give one an import alias.

Decisions made where the brief was silent (conservative choices):
- The reference is URL-encoded with `urllib.parse.quote(reference, safe="")`.
- The time window is sent as the `from` and `to` query parameters in ISO 8601 with the Lagos offset, plus `perPage=100`.
- A naive datetime is treated as Lagos time (`+01:00`). A timezone-aware datetime is converted to `+01:00`.
- `checked` is True only when Paystack was reached and answered with HTTP 200 and readable JSON. It is False whenever no Paystack call was made, including the NOT_FOUND result for an unreadable amount.
- Malformed JSON, or JSON of the wrong shape, from Paystack gives UNAVAILABLE.
- A response is untrusted data. Only the fields named in this document are read, and each is type-checked.
- A full page of 100 transactions with no single clear match is NOT_FOUND with a "check manually" reason, because a second page could hold another payment of the same amount.
- An HTTP 404 from the verify endpoint (unknown reference) is a non-200 response, so it gives UNAVAILABLE, as the brief requires.

Out of scope: Paystack live keys, webhooks, writing to Paystack, retries, caching, the verdict mapping, reply wording, and any AI model.

## Glossary

- **Paystack_Verifier**: The module `src/ghost_credit/paystack.py`, holding Verify_Function, PaystackResult and the default Http_Function.
- **Verify_Function**: The function `verify(parsed, secret_key, now, *, http=None)` that returns a PaystackResult.
- **ParsedAlert**: The dataclass from `alert-parser`. Its `amount_kobo` is an int or None, its `claimed_reference` is a string or None, and its `alert_time` is a naive datetime or None.
- **PaystackResult**: A frozen dataclass with the fields `status`, `checked`, `matched_reference`, `amount_kobo`, `paid_at` and `reason`. It is the Paystack-facing result and is distinct from the verdict-engine's PaystackResult.
- **Status**: One of the three strings `CONFIRMED`, `NOT_FOUND` or `UNAVAILABLE`.
- **Checked**: The boolean `checked` field. It is True only when Paystack answered with HTTP 200 and readable JSON.
- **Reason**: A short plain-English string in the `reason` field. It never contains the secret key.
- **Secret_Key**: The Paystack secret key string passed to Verify_Function, or None.
- **Test_Key**: A Secret_Key that starts with the test-mode prefix, which is the letters `sk`, an underscore, the word `test` and an underscore.
- **Http_Function**: A callable with the signature `(url, headers, timeout_seconds)` that performs one GET request and returns a pair of the HTTP status code (int) and the body (bytes). It raises an exception on a timeout or network error. The default is a urllib implementation.
- **Verify_Endpoint**: `GET https://api.paystack.co/transaction/verify/{reference}`.
- **List_Endpoint**: `GET https://api.paystack.co/transaction`, called with the query parameters `status=success`, `from`, `to` and `perPage=100`.
- **Lagos_Offset**: The fixed timezone offset `+01:00`.
- **Search_Window**: The `from` and `to` times sent to the List_Endpoint.
- **Matching_Transaction**: A transaction object in a Paystack response whose `status` is `"success"`, whose `currency` is `"NGN"` and whose `amount` is an int (not a bool) equal to `parsed.amount_kobo`.
- **Fake_Key**: A synthetic key used by tests. Tests and source build it from two pieces, for example `"sk_" + "test_" + "abc"`, so that the full key prefix never appears as one literal.

## Requirements

### Requirement 1: Define the result and the function signature

**User Story:** As a developer, I want one small function with a fixed result type, so that the verdict engine can use it without knowing how Paystack is called.

#### Acceptance Criteria

1. THE Paystack_Verifier SHALL define PaystackResult as a frozen dataclass with the fields `status` (str), `checked` (bool), `matched_reference` (str or None), `amount_kobo` (int or None), `paid_at` (datetime or None) and `reason` (str).
2. THE Paystack_Verifier SHALL define Verify_Function with the signature `verify(parsed: ParsedAlert, secret_key: str | None, now: datetime, *, http: Http_Function | None = None) -> PaystackResult`.
3. WHEN `http` is None, THE Verify_Function SHALL use the default urllib-based Http_Function.
4. THE Verify_Function SHALL return a PaystackResult whose `status` is one of `CONFIRMED`, `NOT_FOUND` or `UNAVAILABLE`.
5. THE Verify_Function SHALL return a non-empty `reason` of at most 120 characters in every PaystackResult.
6. WHEN the `status` is `NOT_FOUND` or `UNAVAILABLE`, THE Verify_Function SHALL return `matched_reference`, `amount_kobo` and `paid_at` as None.
7. THE Paystack_Verifier SHALL import ParsedAlert from `src/ghost_credit/parser.py` without redefining it.

### Requirement 2: Refuse missing and non-test keys before any call

**User Story:** As the product owner, I want only test keys accepted during the hackathon, so that no live money account is ever touched.

#### Acceptance Criteria

1. IF the Secret_Key is None, empty, or not a string, THEN THE Verify_Function SHALL return `UNAVAILABLE` with `checked` False and the reason `"no Paystack key set"`, without calling the Http_Function.
2. IF the Secret_Key is a string that is not a Test_Key, THEN THE Verify_Function SHALL return `UNAVAILABLE` with `checked` False and the reason `"test keys only during the hackathon"`, without calling the Http_Function.
3. THE Verify_Function SHALL apply the key checks in Acceptance Criteria 1 and 2 before it reads any field of the ParsedAlert.
4. THE Verify_Function SHALL leave the Secret_Key out of every Reason, log line, exception text and returned value.
5. THE Paystack_Verifier SHALL send the Secret_Key only in the header `Authorization: Bearer <Secret_Key>` of a request.

### Requirement 3: Skip the call when the amount is unreadable

**User Story:** As a shop owner, I want no Paystack search when the alert has no readable amount, so that nothing is matched by guesswork.

#### Acceptance Criteria

1. IF the Secret_Key is a Test_Key and `parsed.amount_kobo` is None, THEN THE Verify_Function SHALL return `NOT_FOUND` with `checked` False and the reason `"could not read the amount"`, without calling the Http_Function.
2. IF the Secret_Key is a Test_Key and `parsed.amount_kobo` is not an int, or is a bool, THEN THE Verify_Function SHALL return the same result as in Acceptance Criterion 1.
3. THE Paystack_Verifier SHALL document that a PaystackResult with `checked` False means that no Paystack check took place, so that the verdict-engine mapping treats it as no Paystack check.

### Requirement 4: Verify by reference

**User Story:** As a shop owner, I want an alert that quotes a payment reference to be checked against that exact payment, so that a real payment is recognised and an invented one is not.

#### Acceptance Criteria

1. WHEN the Secret_Key is a Test_Key, `parsed.amount_kobo` is an int and `parsed.claimed_reference` is a string with at least one non-whitespace character, THE Verify_Function SHALL call the Verify_Endpoint once, with the reference URL-encoded by `urllib.parse.quote(reference, safe="")` and with a 5-second timeout.
2. THE Verify_Function SHALL send the header `Authorization: Bearer <Secret_Key>` with every call to the Http_Function.
3. WHEN the Verify_Endpoint answers HTTP 200 with a JSON object whose `data.status` is `"success"`, whose `data.currency` is `"NGN"` and whose `data.amount` is an int equal to `parsed.amount_kobo`, THE Verify_Function SHALL return `CONFIRMED` with `checked` True.
4. WHEN the status is `CONFIRMED` after a reference check, THE Verify_Function SHALL set `matched_reference` to `parsed.claimed_reference` and `amount_kobo` to the matched amount.
5. WHEN the Verify_Endpoint answers HTTP 200 with readable JSON and any condition in Acceptance Criterion 3 is not met, THE Verify_Function SHALL return `NOT_FOUND` with `checked` True and a Reason that states that Paystack has no matching payment.
6. THE Verify_Function SHALL treat a `data.amount` that is a float, a string or a bool as not equal to `parsed.amount_kobo`.
7. WHEN `parsed.claimed_reference` is None, empty, or only whitespace, THE Verify_Function SHALL use the search in Requirement 5 instead of the Verify_Endpoint.

### Requirement 5: Search by amount and time window

**User Story:** As a shop owner, I want an alert with no reference to be matched against recent Paystack payments of the same amount, so that a real transfer is still recognised.

#### Acceptance Criteria

1. WHEN the Secret_Key is a Test_Key, `parsed.amount_kobo` is an int and there is no usable reference, THE Verify_Function SHALL call the List_Endpoint once with a 5-second timeout and the query parameters `status=success`, `from`, `to` and `perPage=100`, URL-encoded by `urllib.parse.urlencode`.
2. WHEN `parsed.alert_time` is not None, THE Verify_Function SHALL set `from` to 30 minutes before the alert time and `to` to 5 minutes after the alert time.
3. WHEN `parsed.alert_time` is None, THE Verify_Function SHALL set `from` to 60 minutes before `now` and `to` to `now`.
4. THE Verify_Function SHALL treat a naive datetime (`alert_time` or `now`) as Lagos time, and SHALL convert a timezone-aware datetime to the Lagos_Offset before it adds or subtracts minutes.
5. THE Verify_Function SHALL write `from` and `to` as ISO 8601 text with the Lagos_Offset, such as `2026-11-20T10:02:11+01:00`.
6. WHEN the List_Endpoint answers HTTP 200 with a JSON object whose `data` is a list that holds exactly one Matching_Transaction, THE Verify_Function SHALL return `CONFIRMED` with `checked` True.
7. WHEN the status is `CONFIRMED` after a search, THE Verify_Function SHALL set `matched_reference` to the `reference` of the Matching_Transaction when it is a string, otherwise None, and SHALL set `amount_kobo` to the matched amount.
8. WHEN the List_Endpoint answers HTTP 200 with readable JSON and `data` holds no Matching_Transaction, THE Verify_Function SHALL return `NOT_FOUND` with `checked` True and a Reason that states that Paystack has no matching payment.
9. WHEN the List_Endpoint answers HTTP 200 with readable JSON and `data` holds more than one Matching_Transaction, THE Verify_Function SHALL return `NOT_FOUND` with `checked` True and the reason `"more than one payment of this amount, check manually"`.
10. WHEN `data` holds 100 transactions and at least one of them is a Matching_Transaction, THE Verify_Function SHALL return `NOT_FOUND` with `checked` True and the reason `"more than one payment of this amount, check manually"`, because another page could hold more payments.
11. THE Verify_Function SHALL treat a transaction whose `currency` is not `"NGN"`, whose `status` is not `"success"`, or whose `amount` is not an int equal to `parsed.amount_kobo` as not matching, and SHALL skip any item in `data` that is not a JSON object.

### Requirement 6: Return UNAVAILABLE when Paystack cannot be used

**User Story:** As a shop owner, I want a clear "could not check" answer when Paystack cannot be reached, so that a network problem is never reported as a fake payment or a real one.

#### Acceptance Criteria

1. IF the Http_Function raises any exception, including a timeout or network error, THEN THE Verify_Function SHALL return `UNAVAILABLE` with `checked` False and the reason `"could not reach Paystack"`.
2. IF the Http_Function returns an HTTP status code other than 200, THEN THE Verify_Function SHALL return `UNAVAILABLE` with `checked` False and the reason `"Paystack did not answer normally"`.
3. IF the body returned with HTTP 200 is not valid JSON, is not a JSON object, or lacks the expected `data` field of the right type, THEN THE Verify_Function SHALL return `UNAVAILABLE` with `checked` False and the reason `"Paystack reply could not be read"`.
4. THE default Http_Function SHALL use only the Python standard library (`urllib.request`) and SHALL pass the 5-second timeout to the request.
5. THE Verify_Function SHALL make at most one Http_Function call per invocation and SHALL perform no retry.
6. THE Verify_Function SHALL return a PaystackResult for every input and SHALL raise no exception, including when `parsed` is not a ParsedAlert, when `now` is not a datetime, and when the Http_Function raises or returns a value of the wrong shape.

### Requirement 7: Read the response safely

**User Story:** As a developer, I want the Paystack response treated as untrusted data, so that a strange reply cannot cause a false CONFIRMED.

#### Acceptance Criteria

1. THE Verify_Function SHALL read only the fields `data`, `status`, `amount`, `currency`, `reference` and `paid_at` of a Paystack response and SHALL ignore every other field.
2. THE Verify_Function SHALL treat Paystack amounts as kobo and SHALL perform no unit conversion and no float arithmetic.
3. WHEN the status is `CONFIRMED` and the matched transaction has a `paid_at` string that is valid ISO 8601, THE Verify_Function SHALL set `paid_at` to the parsed datetime, converted to the Lagos_Offset.
4. WHEN the status is `CONFIRMED` and `paid_at` is missing or cannot be parsed, THE Verify_Function SHALL set `paid_at` to None and SHALL keep the status `CONFIRMED`.
5. THE Verify_Function SHALL return `CONFIRMED` only when all of the following hold: `checked` is True, the Paystack `status` is `"success"`, the `currency` is `"NGN"`, and the Paystack `amount` equals `parsed.amount_kobo`.
6. THE Paystack_Verifier SHALL write no text from a Paystack response into a Reason, so that a Reason is always one of the fixed strings in this document.

### Requirement 8: Test with fake responses only

**User Story:** As a developer, I want the tests to run offline with recorded fake responses, so that no test ever touches the real Paystack API or a real key.

#### Acceptance Criteria

1. THE Paystack_Verifier test suite SHALL pass every Http_Function through the `http` keyword parameter and SHALL make no real network call.
2. THE Paystack_Verifier test suite SHALL use recorded fake JSON responses with synthetic data only, and SHALL build every Fake_Key from two or more string pieces so that the full key prefix never appears as one literal in a test or in `src/ghost_credit/paystack.py`.
3. THE Paystack_Verifier source and tests SHALL satisfy `tests/test_example_screenshot_secrets.py`, which fails on any key-like string in `src`, `tests` or `docs`.
4. THE Paystack_Verifier test suite SHALL pass with the environment variable `PATTERN_NETWORK=off`.
5. THE Paystack_Verifier test suite SHALL include a Hypothesis property test that, for any ParsedAlert (including None fields), any Secret_Key (including None) and any fake Http_Function behaviour (including raising and returning arbitrary bytes), Verify_Function raises no exception and returns one of the three statuses.
6. THE Paystack_Verifier test suite SHALL include a Hypothesis property test that, for any fake successful response whose amount differs from `parsed.amount_kobo`, the status is not `CONFIRMED`.
7. THE Paystack_Verifier test suite SHALL include a Hypothesis property test that, for any fake response whose Paystack `status` is not `"success"`, the status is not `CONFIRMED`.
8. THE Paystack_Verifier test suite SHALL include example tests for each of the following: a confirmed reference check, a confirmed search with exactly one match, a search with zero matches, a search with two matches, a non-NGN currency, a missing key, a non-test key, an unreadable amount, a timeout, a non-200 response, malformed JSON, a naive and an aware `alert_time`, and a request whose recorded URL and `Authorization` header equal the expected values.
9. THE Paystack_Verifier test suite SHALL include a test that checks that the Secret_Key does not appear in any returned PaystackResult or in any captured log output.

### Requirement 9: Follow the project conventions

**User Story:** As a maintainer, I want the module to follow the project rules, so that it fits the rest of Ghost Credit.

#### Acceptance Criteria

1. THE Paystack_Verifier SHALL hold every money amount as an integer in kobo and SHALL use no float for money.
2. THE Paystack_Verifier SHALL write every time it creates as ISO 8601 with the Lagos_Offset.
3. THE Paystack_Verifier SHALL use only the Python standard library and SHALL call no AI model, paid service or other third-party API.
4. THE Paystack_Verifier SHALL contain no code from Fake Alert Shield, Meko or any other LGND project, and no code from the fake-alert-eval repo.
5. THE Paystack_Verifier SHALL contain no secret, token or personal data in source, tests or docs, and SHALL read no key itself, because the caller passes the Secret_Key in.
6. THE Paystack_Verifier SHALL use small functions with type hints and short plain-English docstrings.
