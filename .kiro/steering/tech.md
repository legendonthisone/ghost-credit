---
inclusion: always
---

# Tech rules: Ghost Credit

## Stack (confirm or change in the specs phase)
- Language: Python 3.11 or newer.
- Web API and The Lab backend: FastAPI.
- Tests: pytest, plus Hypothesis for property-based tests.
- Hosting: decided later. Must be cheap and approved by Ayobami before anything is deployed.

## Data rules
- Money is always an integer in kobo (NGN 45,000 = 4500000). Never use floats for money.
- Times are ISO 8601 with the Lagos offset, for example 2026-11-20T10:02:11+01:00.
- Tests and the demo use synthetic data only. No real customer names, numbers or accounts.

## Secrets and privacy
- Secrets live in a local .env file that is never committed. Commit only .env.example with empty values.
- Paystack keys are test keys only (they start with sk_test_ and pk_test_).
- No personal email addresses anywhere in the repo, commits or docs.
- Screenshots are processed and then discarded. Do not store them.

## Cost rules (no wasting credits)
- No paid API call, paid service or paid AI model without Ayobami's approval and a quoted cost.
- AI calls use the cheapest model that does the job, and only to read screenshots or write explanations.
- Never call an AI model inside a loop or a test. Tests use recorded or fake responses.

## Code style
- Small functions with type hints.
- Short plain-English docstrings that say what the function does and why, so a beginner can follow the code.
- Every module has tests. The whole app must pass its tests with PATTERN_NETWORK=off.
