# Implementation Plan: pattern-network-hook

## Overview

Build `src/ghost_credit/pattern_network.py` in Python (the language of the existing repo and the design) in the order the design suggests: dataclasses, interface and Noop, normaliser, hasher, configuration and Signals builder, lookup caller, report caller. Tests go in `tests/` using pytest and Hypothesis, with PATTERN_NETWORK unset by default. The module uses only the standard library and contains no network code.

## Tasks

- [ ] 1. Contract dataclasses and conversion
  - [ ] 1.1 Create the module with Signals, Verdict, Match, LookupResult and ReportReceipt
    - Create `src/ghost_credit/pattern_network.py` with standard-library dataclasses using the contract field names and types
    - Default schema_version "1.0" in Signals, LookupResult and ReportReceipt, and decided_by "rules" in Verdict
    - Validate in `__post_init__`: amount_kobo must be an int (booleans rejected), Verdict code and owner_outcome, ReportReceipt status; raise ValueError naming the field
    - Add `to_dict` and `from_dict` for each dataclass; `from_dict` reads contract fields only and ignores unknown keys; LookupResult nests Match dictionaries
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10, 2.11, 2.12, 2.13, 3.8_

  - [ ]* 1.2 Write property test for dataclass round trip
    - **Property 1: Dataclass round trip**
    - **Validates: Requirements 2.12, 2.14**

  - [ ]* 1.3 Write property test for unknown fields
    - **Property 2: Unknown fields are ignored**
    - **Validates: Requirements 2.13**

  - [ ]* 1.4 Write property test for invalid values
    - **Property 3: Invalid values are rejected by name**
    - **Validates: Requirements 2.7, 2.8, 2.9, 2.10**

- [ ] 2. PatternNetwork interface and NoopPatternNetwork
  - [ ] 2.1 Add the abstract PatternNetwork and NoopPatternNetwork
    - Abstract `lookup_patterns(signals)` and `report_pattern(verdict, signals)`
    - Noop returns the constant hook-off LookupResult and ReportReceipt, with no I/O and no state
    - Export Verdict, Signals, Match, LookupResult, ReportReceipt, PatternNetwork and NoopPatternNetwork
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 4.1, 4.2, 4.4_

  - [ ]* 2.2 Write property test for constant Noop answers
    - **Property 6: Noop answers are constant**
    - **Validates: Requirements 4.1, 4.2, 4.5**

  - [ ]* 2.3 Write example test for the contract hook-off JSON
    - Compare `to_dict` of the Noop results with the contract section "Example: what this repo returns (hook off)"
    - Check dataclass field names against the contract tables and the schema_version and decided_by defaults
    - _Requirements: 4.3, 2.1, 2.2, 2.3, 2.4, 2.5, 2.11_

- [ ] 3. Normaliser
  - [ ] 3.1 Implement normalise_name, normalise_phone and normalise_account
    - Name: uppercase, drop non-letter/digit/whitespace characters, collapse whitespace, trim, None when empty
    - Phone: accept `+234`, `234` or `0` plus 10 digits with optional spaces, hyphens or round brackets; return `+234` plus 10 digits; otherwise None
    - Account: exactly 10 digits with optional spaces or hyphens; masked, lettered or wrong-length input gives None
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_

  - [ ]* 3.2 Write property test for name normalisation
    - **Property 7: Name normalisation**
    - **Validates: Requirements 5.1, 5.2, 5.8**

  - [ ]* 3.3 Write property test for phone normalisation across forms
    - **Property 8: Phone normalisation across accepted forms**
    - **Validates: Requirements 5.3, 5.9, 5.11**

  - [ ]* 3.4 Write property test for invalid phones
    - **Property 9: Invalid phones give None**
    - **Validates: Requirements 5.5**

  - [ ]* 3.5 Write property test for account normalisation
    - **Property 10: Account normalisation**
    - **Validates: Requirements 5.6, 5.7, 5.10**

  - [ ]* 3.6 Write example tests for normalisation
    - Phone "0803 123 4567" gives "+2348031234567"; a name with punctuation; masked account "012****789"; a 9-digit account; a phone with 9 subscriber digits
    - _Requirements: 5.4, 5.5, 5.7, 9.4_

- [ ] 4. Hasher
  - [ ] 4.1 Implement hash_value
    - Return "hmac:" plus lowercase hex HMAC-SHA256 of the UTF-8 value with the key
    - Return None for a None value or a None or empty key
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [ ]* 4.2 Write property test for hash format and value
    - **Property 11: Hash format and value**
    - **Validates: Requirements 6.1, 6.2**

  - [ ]* 4.3 Write property test for hash equality
    - **Property 12: Hash equality follows value equality**
    - **Validates: Requirements 6.10, 6.11**

- [ ] 5. Hook_Config and Signals privacy builder
  - [ ] 5.1 Implement Hook_Config functions
    - `is_hook_on`, `get_hmac_key`, `get_merchant_ref` and `get_network`, reading the environment at call time
    - Hook_On only when the trimmed, lowercased PATTERN_NETWORK equals "on"; key and merchant_ref are None while Hook_Off; empty key counts as no key; `get_network` always returns a Noop
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.9_

  - [ ] 5.2 Implement the Signals privacy builder
    - One function normalises and hashes raw payer name, account and phone with the single network-wide key
    - Hook_Off: all payer hashes and merchant_ref are None; Hook_On without key: hashes None; Hook_On with key: Hash_String or None; no raw payer value enters any Signals field
    - Accept screenshot_phash as an input
    - _Requirements: 6.5, 6.6, 6.7, 6.8, 6.9_

  - [ ]* 5.3 Write property test for hook flag parsing
    - **Property 4: Hook flag parsing**
    - **Validates: Requirements 3.2, 3.3, 3.4**

  - [ ]* 5.4 Write property test for Hook_Off hiding secrets and hashes
    - **Property 5: Hook_Off hides secrets and hashes**
    - **Validates: Requirements 3.7, 6.6**

  - [ ]* 5.5 Write property test for missing inputs
    - **Property 13: Missing inputs give None**
    - **Validates: Requirements 6.3, 6.4, 6.8**

  - [ ]* 5.6 Write property test for hashes-only Signals
    - **Property 14: Hook_On Signals carry hashes only**
    - **Validates: Requirements 6.5, 6.7, 6.9**

  - [ ]* 5.7 Write example test that Hook_Off hides key and merchant_ref
    - Set both environment variables with PATTERN_NETWORK unset and check that none is returned; use fixed test keys only
    - _Requirements: 3.7, 9.6, 9.8_

- [ ] 6. Network_Caller: safe lookup
  - [ ] 6.1 Implement safe_lookup
    - Run `lookup_patterns` in a worker thread and wait at most 1.5 s
    - On timeout, exception or non-LookupResult, return LookupResult with network_available false, matched false and no matches
    - Log the event type only, with no Signals value, hash or key; return valid results unchanged; never touch a Verdict
    - Provide no function that maps a LookupResult to CONFIRMED
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 3.8_

  - [ ]* 6.2 Write property test for lookup fallback
    - **Property 15: Lookup falls back safely**
    - **Validates: Requirements 7.1, 7.2, 7.3, 7.4**

  - [ ]* 6.3 Write property test for advisory lookup and clean logs
    - **Property 16: Lookup is advisory and logs no payload data**
    - **Validates: Requirements 3.8, 7.5, 7.6**

  - [ ]* 6.4 Write example test for a lookup slower than 1.5 seconds
    - A stub that sleeps past the limit gives network_available false
    - _Requirements: 9.5, 7.2_

- [ ] 7. Network_Caller: safe report and hook-off end-to-end
  - [ ] 7.1 Implement safe_report
    - Skip when verdict code is CONFIRMED; otherwise call `report_pattern` on a daemon thread and return at once
    - The thread catches every exception and logs the event type only
    - Pass verdict (including owner_outcome) and check_id through unchanged so a later call with the same check_id is an update
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7_

  - [ ]* 7.2 Write property test for reports following the verdict code
    - **Property 17: Reports follow the verdict code**
    - **Validates: Requirements 8.1, 8.2**

  - [ ]* 7.3 Write property test for hidden, non-blocking report failures
    - **Property 18: Report failures stay hidden and do not block**
    - **Validates: Requirements 8.3, 8.4**

  - [ ]* 7.4 Write property test for identity and outcome pass-through
    - **Property 19: Reports pass identity and outcome through**
    - **Validates: Requirements 8.5, 8.6, 8.7**

  - [ ]* 7.5 Write the hook-off caller test and smoke checks
    - With PATTERN_NETWORK "off", run safe_lookup and safe_report using the Noop from `get_network` and check the exact contract hook-off JSON without errors
    - Check the module imports no HTTP or socket library and has no Shield code, the exports exist, Noop is the only PatternNetwork subclass, and the suite makes no real network connection and uses only fixed test keys
    - _Requirements: 4.6, 9.1, 9.2, 9.7, 9.8, 1.3, 1.4, 1.5, 3.9, 7.7_

- [ ] 8. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Each task references specific requirements for traceability
- Property tests validate the universal properties in the design, with at least 100 examples each (fewer for timeout tests)
- Tag each property test with **Feature: pattern-network-hook, Property N: property text**

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "1.3", "1.4", "2.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "3.1"] },
    { "id": 3, "tasks": ["3.2", "3.3", "3.4", "3.5", "3.6", "4.1"] },
    { "id": 4, "tasks": ["4.2", "4.3", "5.1"] },
    { "id": 5, "tasks": ["5.2"] },
    { "id": 6, "tasks": ["5.3", "5.4", "5.5", "5.6", "5.7", "6.1"] },
    { "id": 7, "tasks": ["6.2", "6.3", "6.4", "7.1"] },
    { "id": 8, "tasks": ["7.2", "7.3", "7.4", "7.5"] }
  ]
}
```
