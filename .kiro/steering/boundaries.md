---
inclusion: always
---

# Boundaries: what Ghost Credit must never do

## Ghost Credit stands alone
- Ghost Credit is a standalone single-shop product.
- Never write, copy or import code from Fake Alert Shield, Meko or any other LGND project.
- No data is ever shared between shops.

## The pattern network socket stays empty
- Ghost Credit has one plug-in point called PatternNetwork, with two functions: lookup_patterns(signals) and report_pattern(verdict, signals).
- In this repo the only implementation is NoopPatternNetwork. It always answers "network not available" and sends nothing anywhere.
- The config switch PATTERN_NETWORK defaults to off, and this repo ships only the off version.
- A network answer can never produce a CONFIRMED verdict. Only Paystack confirms money.
- The full contract lives in docs/pattern-network-contract.md (written in the specs phase).

## New project rule (Kiroween)
- All code is written new, during the hackathon.
- Never copy code from the older fake-alert-eval repo. If any of its test cases are reused, list them in the README under "Pre-existing work".

## Repo rules
- Never add .kiro or any of its sub-folders to .gitignore.
- Never commit secrets, .env files or personal email addresses.

## Ask first
- Before adding a paid service, a paid model or anything that costs credits or money, stop and ask Ayobami with the cost in plain numbers.
