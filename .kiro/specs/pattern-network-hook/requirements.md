# Requirements Document

## Introduction

Ghost Credit exposes one plug socket, `PatternNetwork`, defined by `docs/pattern-network-contract.md` v1.0. This feature delivers that socket and nothing behind it: an abstract `PatternNetwork` interface, the contract dataclasses, normalisation and hashing helpers, configuration handling, timeout and fire-and-forget rules, and the only implementation, `NoopPatternNetwork`. The repo ships only the off version. It contains no network code and no Fake Alert Shield code.

The feature lives in the module `src/ghost_credit/pattern_network.py`. The verdict-engine spec imports `Verdict` and `LookupResult` from this module. The screenshot-reader spec supplies `screenshot_phash`. The contract is the single source of truth for field names, types, status strings and safety rules 1 to 8. Where the contract is silent, this document states a conservative rule: invalid input gives None and is never guessed, and any configuration value other than the on value means off.

## Glossary

- **Pattern_Network_Module**: The Python module `src/ghost_credit/pattern_network.py` that contains everything in this feature.
- **PatternNetwork**: The abstract interface with `lookup_patterns(signals)` returning a LookupResult and `report_pattern(verdict, signals)` returning a ReportReceipt.
- **Noop_Network**: The class `NoopPatternNetwork`, the only implementation of PatternNetwork in this repo.
- **Signals**: The dataclass holding the `signals` fields of the contract: schema_version, check_id, checked_at, channel, amount_kobo, currency, claimed_bank, sender_id, claimed_reference, payer_name_hash, payer_account_hash, payer_phone_hash, screenshot_phash, red_flags, merchant_ref, merchant_category.
- **Verdict**: The dataclass holding the `verdict` fields of the contract: code, decided_by, paystack_checked, owner_outcome, reasons.
- **Match**: The dataclass for one entry of LookupResult.matches: pattern_id, matched_on, first_seen, times_seen, shops_seen, last_verdict, confidence, summary.
- **LookupResult**: The dataclass with schema_version, network_available, matches, matched, trace_url.
- **ReportReceipt**: The dataclass with schema_version, accepted, status, pattern_id, trace_url.
- **Normaliser**: The set of functions that convert a raw name, phone number or account number into the canonical form required before hashing.
- **Hasher**: The function that turns a normalised value into the string "hmac:" followed by the lowercase hexadecimal HMAC-SHA256 digest.
- **Hook_Config**: The configuration reader that supplies PATTERN_NETWORK, the network-wide HMAC key and the merchant_ref.
- **Network_Caller**: The functions in the Pattern_Network_Module that the rest of the app uses to call a PatternNetwork safely (timeout for lookup, fire-and-forget for report).
- **Hook_On**: The state in which the PATTERN_NETWORK configuration value, after trimming and lowercasing, equals "on".
- **Hook_Off**: Any state that is not Hook_On, including an unset or empty value.
- **Kobo**: The integer money unit; NGN 45,000 equals 4500000 kobo.
- **Hash_String**: A string of the form "hmac:" followed by 64 lowercase hexadecimal characters.

## Requirements

### Requirement 1: Abstract PatternNetwork Interface

**User Story:** As a developer of other Ghost Credit specs, I want an abstract PatternNetwork interface, so that the verdict engine can call one socket without knowing what is plugged in.

#### Acceptance Criteria

1. THE Pattern_Network_Module SHALL define PatternNetwork with a method `lookup_patterns` that accepts a Signals and returns a LookupResult.
2. THE Pattern_Network_Module SHALL define PatternNetwork with a method `report_pattern` that accepts a Verdict and a Signals and returns a ReportReceipt.
3. THE Pattern_Network_Module SHALL export Verdict, Signals, Match, LookupResult, ReportReceipt, PatternNetwork and Noop_Network for import by other modules.
4. THE Pattern_Network_Module SHALL import no HTTP client, socket or other network library.
5. THE Pattern_Network_Module SHALL contain no code from Fake Alert Shield.

### Requirement 2: Contract Dataclasses

**User Story:** As a developer, I want dataclasses that match the contract exactly, so that every payload follows schema_version "1.0".

#### Acceptance Criteria

1. THE Signals SHALL have exactly the 16 fields listed in the contract table `signals`, with the field names and types given there.
2. THE Verdict SHALL have exactly the 5 fields listed in the contract table `verdict`, with the field names and types given there.
3. THE LookupResult SHALL have the fields schema_version, network_available, matched, matches and trace_url, and each entry of matches SHALL be a Match with the 8 fields listed in the contract.
4. THE ReportReceipt SHALL have the fields schema_version, accepted, status, pattern_id and trace_url.
5. THE Pattern_Network_Module SHALL set the default value of schema_version to "1.0" in Signals, LookupResult and ReportReceipt.
6. THE Pattern_Network_Module SHALL store amount_kobo as an integer.
7. IF a Signals is built with an amount_kobo that is not an integer, THEN THE Pattern_Network_Module SHALL raise a ValueError that names the field amount_kobo.
8. IF a Verdict is built with a code outside CONFIRMED, NOT_FOUND, SUSPICIOUS and UNVERIFIED, THEN THE Pattern_Network_Module SHALL raise a ValueError that names the field code.
9. IF a Verdict is built with an owner_outcome outside "unknown", "fake" and "real", THEN THE Pattern_Network_Module SHALL raise a ValueError that names the field owner_outcome.
10. IF a ReportReceipt is built with a status outside "disabled", "queued" and "rejected", THEN THE Pattern_Network_Module SHALL raise a ValueError that names the field status.
11. THE Pattern_Network_Module SHALL set the Verdict field decided_by to "rules" by default.
12. THE Pattern_Network_Module SHALL provide a function that converts each dataclass to a plain dictionary and a function that builds each dataclass from a plain dictionary.
13. WHEN a dictionary that contains fields not defined in the contract is converted to a dataclass, THE Pattern_Network_Module SHALL ignore the unrecognised fields.
14. FOR ALL valid Signals, Verdict, LookupResult and ReportReceipt values, converting to a dictionary and back to a dataclass SHALL produce an equal value (round-trip property).

### Requirement 3: Configuration and Default Off

**User Story:** As a shop owner, I want the app to do nothing network-related by default, so that nothing about my shop leaves my phone.

#### Acceptance Criteria

1. THE Hook_Config SHALL read the value of the environment variable PATTERN_NETWORK.
2. WHEN PATTERN_NETWORK is unset, THE Hook_Config SHALL report Hook_Off.
3. WHEN the PATTERN_NETWORK value, after removing surrounding whitespace and converting to lowercase, equals "on", THE Hook_Config SHALL report Hook_On.
4. WHEN the PATTERN_NETWORK value is any value other than the on value, THE Hook_Config SHALL report Hook_Off.
5. THE Hook_Config SHALL read the network-wide HMAC key from the environment variable PATTERN_NETWORK_HMAC_KEY.
6. THE Hook_Config SHALL read the merchant_ref from the environment variable PATTERN_NETWORK_MERCHANT_REF.
7. WHILE Hook_Off, THE Hook_Config SHALL return no HMAC key and no merchant_ref, even when the environment variables for them are set.
8. THE Pattern_Network_Module SHALL contain no HMAC key value in source code, default values, log messages, error messages or the string form of any dataclass.
9. THE Pattern_Network_Module SHALL ship Noop_Network as the only PatternNetwork implementation, regardless of the PATTERN_NETWORK value.

### Requirement 4: NoopPatternNetwork

**User Story:** As a developer, I want a no-op network, so that the app works unchanged with the hook off.

#### Acceptance Criteria

1. WHEN `lookup_patterns` is called on Noop_Network, THE Noop_Network SHALL return a LookupResult with schema_version "1.0", network_available false, matched false, matches as an empty list and trace_url None.
2. WHEN `report_pattern` is called on Noop_Network, THE Noop_Network SHALL return a ReportReceipt with schema_version "1.0", accepted false, status "disabled", pattern_id None and trace_url None.
3. WHEN the results of Noop_Network are converted to dictionaries, THE Pattern_Network_Module SHALL produce exactly the JSON shown in the contract section "Example: what this repo returns (hook off)".
4. THE Noop_Network SHALL send no data over any network connection and write no data to disk.
5. FOR ALL Signals and Verdict inputs, THE Noop_Network SHALL return the same LookupResult and the same ReportReceipt (invariant property).
6. WHEN the app runs with PATTERN_NETWORK unset or set to "off", THE Network_Caller SHALL complete a lookup and a report using Noop_Network without raising an error.

### Requirement 5: Normalisation Helpers

**User Story:** As a shop owner, I want payer details turned into canonical form before hashing, so that the same person always gives the same hash.

#### Acceptance Criteria

1. WHEN a name is normalised, THE Normaliser SHALL convert the letters to uppercase, remove every character that is not a letter, a digit or whitespace, replace each run of whitespace with one space and remove leading and trailing whitespace.
2. IF a name is None or normalises to an empty string, THEN THE Normaliser SHALL return None.
3. WHEN a phone number is written as +234 followed by 10 digits, 234 followed by 10 digits, or 0 followed by 10 digits, with optional spaces, hyphens or round brackets, THE Normaliser SHALL return the E.164 form "+234" followed by those 10 digits.
4. WHEN the phone number "0803 123 4567" is normalised, THE Normaliser SHALL return "+2348031234567".
5. IF a phone number is None or does not match a form accepted by criterion 3, THEN THE Normaliser SHALL return None and SHALL NOT guess a value.
6. WHEN an account number consists of exactly 10 digits, optionally with spaces or hyphens between digits, THE Normaliser SHALL return the 10 digits.
7. IF an account number is None, is masked (for example "012****789"), contains letters or does not contain exactly 10 digits, THEN THE Normaliser SHALL return None and SHALL NOT guess a value.
8. FOR ALL strings, normalising a name twice SHALL produce the same result as normalising it once (idempotence property).
9. FOR ALL phone numbers that the Normaliser accepts, the result SHALL match the pattern "+234" followed by exactly 10 digits, and normalising the result again SHALL return the same value (idempotence property).
10. FOR ALL account numbers that the Normaliser accepts, the result SHALL consist of exactly 10 digits, and normalising the result again SHALL return the same value (idempotence property).
11. FOR ALL phone numbers written in the three accepted forms with the same 10 subscriber digits, THE Normaliser SHALL return the same value (metamorphic property).

### Requirement 6: HMAC Hashing and Signals Privacy

**User Story:** As a shop owner, I want payer details sent only as keyed hashes, so that no raw personal data leaves the shop.

#### Acceptance Criteria

1. WHEN a normalised value and an HMAC key are supplied, THE Hasher SHALL return "hmac:" followed by the lowercase hexadecimal HMAC-SHA256 digest of the UTF-8 bytes of the value, computed with the key.
2. THE Hasher SHALL produce a Hash_String of exactly 69 characters.
3. IF the value is None, THEN THE Hasher SHALL return None.
4. IF the key is None or empty, THEN THE Hasher SHALL return None.
5. THE Pattern_Network_Module SHALL provide one function that builds the payer_name_hash, payer_account_hash and payer_phone_hash fields by normalising each raw value and then hashing it with the single network-wide key.
6. WHILE Hook_Off, THE Pattern_Network_Module SHALL set payer_name_hash, payer_account_hash, payer_phone_hash and merchant_ref to None in every Signals it builds.
7. WHILE Hook_On and an HMAC key is configured, THE Pattern_Network_Module SHALL set each payer hash field to the Hash_String of the normalised raw value, or to None when normalisation returns None.
8. WHILE Hook_On and no HMAC key is configured, THE Pattern_Network_Module SHALL set payer_name_hash, payer_account_hash and payer_phone_hash to None.
9. THE Pattern_Network_Module SHALL place no raw payer name, raw phone number or raw account number in any Signals field.
10. FOR ALL pairs of raw values that normalise to the same value, THE Hasher SHALL return equal Hash_Strings when the key is the same (invariant property).
11. FOR ALL pairs of different normalised values with the same key, THE Hasher SHALL return different Hash_Strings (metamorphic property).

### Requirement 7: Lookup Timeout and Failure Handling

**User Story:** As a shop owner, I want a lookup that can never slow down or break my check, so that a missing network never blocks a reply.

#### Acceptance Criteria

1. WHEN the Network_Caller performs a lookup, THE Network_Caller SHALL wait at most 1.5 seconds for the PatternNetwork to answer.
2. IF the lookup does not finish within 1.5 seconds, THEN THE Network_Caller SHALL return a LookupResult with network_available false, matched false and matches as an empty list.
3. IF the lookup raises an error, THEN THE Network_Caller SHALL return a LookupResult with network_available false, matched false and matches as an empty list.
4. IF the lookup returns something that is not a LookupResult, THEN THE Network_Caller SHALL return a LookupResult with network_available false, matched false and matches as an empty list.
5. WHEN the lookup times out or raises an error, THE Network_Caller SHALL log the event without including any Signals value, hash or key.
6. THE Network_Caller SHALL return the lookup result to the verdict engine as advisory data and SHALL NOT change, create or remove any Verdict field.
7. THE Pattern_Network_Module SHALL provide no function that converts a LookupResult into the verdict code CONFIRMED.

### Requirement 8: Fire-and-Forget Reporting

**User Story:** As a shop owner, I want reports to the network to happen in the background, so that the reply to me is never delayed.

#### Acceptance Criteria

1. WHEN a Verdict has a code other than CONFIRMED, THE Network_Caller SHALL submit a report to the PatternNetwork.
2. WHEN a Verdict has the code CONFIRMED, THE Network_Caller SHALL submit no report.
3. WHEN the Network_Caller submits a report, THE Network_Caller SHALL return to the caller without waiting for the PatternNetwork to finish.
4. IF the report call raises an error, THEN THE Network_Caller SHALL discard the error, log the event without including any Signals value, hash or key, and leave the reply to the owner unchanged.
5. WHEN the owner answers later, THE Network_Caller SHALL accept a Verdict with the same check_id and a different owner_outcome and submit it as an update.
6. THE Network_Caller SHALL use the check_id of the Signals as the identity of a check, so that two reports with the same check_id describe one check.
7. WHEN a report is submitted, THE Network_Caller SHALL pass the owner_outcome exactly as given and use "unknown" when the owner has not answered.

### Requirement 9: Test Coverage

**User Story:** As a developer, I want automated tests for the hook, so that I can trust that the app works with the hook off and that normalisation is correct.

#### Acceptance Criteria

1. THE Pattern_Network_Module SHALL have a test suite in the `tests` directory that passes with PATTERN_NETWORK unset.
2. THE test suite SHALL include a test that runs a lookup and a report through the Network_Caller with PATTERN_NETWORK set to "off" and checks the exact hook-off JSON of the contract.
3. THE test suite SHALL include Hypothesis property tests for the properties stated in criteria 5.8 to 5.11 and 6.10 to 6.11 of this document, and the round-trip property in criterion 2.14.
4. THE test suite SHALL include example tests for the phone number "0803 123 4567", an accepted name with punctuation, a masked account number, an account number with 9 digits and a phone number with 9 subscriber digits.
5. THE test suite SHALL include a test that a lookup which takes longer than 1.5 seconds returns network_available false.
6. THE test suite SHALL include a test that checks the Hook_Off state hides the HMAC key and merchant_ref even when their environment variables are set.
7. THE test suite SHALL perform no real network connection.
8. THE test suite SHALL contain no real HMAC key; every key it uses SHALL be a fixed test value.
