# Requirements Document

## Introduction

Alert_Parser is a pure Python function, `parse_sms_alert(text: str, sender_id: str | None) -> ParsedAlert`, in `src/ghost_credit/parser.py`. It reads the text of a bank credit alert SMS and the SMS sender header, and returns a structured `ParsedAlert`. It also detects the red flags that the SMS text and sender header can show. It makes no AI calls and no network calls. The Rules_Engine, not this feature, chooses the verdict. Domain context comes from `.kiro/steering/payments-nigeria.md`. Money follows rule 6 of `docs/pattern-network-contract.md`: an integer in kobo. The output fields `amount_kobo`, `currency`, `claimed_bank`, `sender_id` and `claimed_reference` map to the `signals` fields of the same names, and `red_flags` carries the codes used there.

Out of scope: SCREENSHOT_EDIT_SIGNS (needs an image), detection of future dates (needs a clock, which a pure function does not have), verdict selection, Paystack checks, and Pattern_Network calls.

## Glossary

- **Alert_Parser**: The function `parse_sms_alert` in `src/ghost_credit/parser.py`.
- **Alert_Text**: The SMS body string passed to Alert_Parser as `text`.
- **ParsedAlert**: The dataclass returned by Alert_Parser, with the fields `amount_kobo`, `currency`, `claimed_bank`, `sender_id`, `account_masked`, `narration`, `alert_time`, `available_balance_kobo`, `claimed_reference` and `red_flags`. A field with no value in the input holds Python `None`, except `red_flags`, which holds an empty list.
- **Kobo**: The smallest Naira unit. 1 Naira equals 100 kobo.
- **Supported_Amount_Format**: One of these ways of writing an amount: a currency marker (`N`, `₦` or `NGN`, with or without a space) followed by a number such as `N50,000.00`, `NGN50,000` or `NGN 50k`; or a number followed by a credit marker such as `50,000.00 CR`. A number may use comma thousands separators, a decimal part of one or two digits, or a `k` suffix meaning thousands.
- **Currency_Marker**: The text `N`, `₦` or `NGN` that appears directly before an amount, with or without a space.
- **Phone_Number_Sender**: A sender_id made only of digits, spaces, hyphens and an optional leading `+`, with 7 to 15 digits in total.
- **Bank_Sender_Name**: A sender_id that contains at least one letter, such as a bank's alphabetic sender header.
- **Balance_Line**: A part of Alert_Text that labels a figure as the available or current balance, for example `Bal: N120,500.00` or `Avail Bal: 120,500.00`.
- **Balance_Label**: The label text of a Balance_Line, for example `Bal` or `Avail Bal`, matched regardless of letter case.
- **Pressure_Phrase**: A phrase in Alert_Text that urges the shop to release goods immediately or before the owner can check. The recognised phrases are kept in one named list in `parser.py`.
- **Amount_In_Words**: An amount written as English words in Alert_Text, for example `fifty thousand naira`.
- **Recognised_Date_Formats**: The list of date layouts that Alert_Parser accepts: `DD/MM/YYYY`, `DD-MM-YYYY`, `DD-Mon-YYYY`, `DD Mon YYYY` and `YYYY-MM-DD`, where `Mon` is a three-letter English month abbreviation in any letter case, `DD` and the month number are 1 or 2 digits, and `YYYY` is 4 digits. Each layout may be followed on the same line by a Recognised_Time, separated by spaces or tabs. The date is not part of a longer digit run: the character before it is not a digit, `/`, `-` or a letter, and the character after its last digit is not a digit.
- **Recognised_Time**: A 24-hour clock time `HH:MM[:SS]` with `HH` of 1 or 2 digits, `MM` of 2 digits, an optional `SS` of 2 digits, and no digit directly after it.
- **Unrecognised_Date_Shape**: Digit groups of 1 to 4, 1 to 2 and 1 to 4 digits separated by `/` or `-` (for example `12/03/24` or `2026/03/12`) that match no Recognised_Date_Formats layout, with the same boundary rules as a Recognised_Date_Formats date.
- **Known_Bank_List**: The list of Nigerian bank names, each with a canonical name, kept in one named list in `parser.py` and matched regardless of letter case.
- **Red_Flag_Code**: One of the strings `SENDER_ID_MISMATCH`, `BALANCE_LINE_MISSING`, `AMOUNT_FORMAT_ODD`, `DATE_ODD`, `PRESSURE_LANGUAGE`, `SCREENSHOT_EDIT_SIGNS` or `TRANSFER_REQUEST_WORDING`. Alert_Parser can produce every code except `SCREENSHOT_EDIT_SIGNS`. The codes are kept in one tuple named `RED_FLAG_CODES` in `parser.py`, in the order listed here.
- **Transfer_Request_Phrase**: Text in Alert_Text that says a transfer was requested rather than received. It is either a phrase from the named list `TRANSFER_REQUEST_PHRASES` in `parser.py` (the list holds `transfer request successful` and `transfer request has been`), or the words `request successful` and `transfer` appearing Near each other.
- **Near**: Two matches are Near each other when, after normalisation, at most 40 characters lie between the end of the earlier match and the start of the later match, in either order. The words `request successful` and `transfer` are each matched as whole words.
- **Normalised_Text**: Alert_Text with curly quotes replaced by straight quotes, letters lower-cased, and every run of whitespace replaced by one space.
- **Clean_Text**: Alert_Text that triggers no Red_Flag_Code when parsed with a Bank_Sender_Name as sender_id. It has a Balance_Line, no odd amount, no date, and no Pressure_Phrase or Transfer_Request_Phrase.
- **Rules_Engine**: The later component that chooses the verdict from Red_Flag_Codes and Paystack results. It is not part of this feature.

## Requirements

### Requirement 1: Return a structured ParsedAlert

**User Story:** As a shop owner, I want an alert's text turned into labelled fields, so that later checks can use the amount, bank and reference without reading the SMS again.

#### Acceptance Criteria

1. WHEN called with text and sender_id, THE Alert_Parser SHALL return a ParsedAlert without raising an exception for any Alert_Text of 0 to 10,000 characters, including the empty string.
2. THE ParsedAlert SHALL contain exactly the fields `amount_kobo`, `currency`, `claimed_bank`, `sender_id`, `account_masked`, `narration`, `alert_time`, `available_balance_kobo`, `claimed_reference` and `red_flags`.
3. WHEN a value for a field other than `red_flags` is not present in Alert_Text or the sender_id argument, THE Alert_Parser SHALL set that field to None.
4. WHEN no Red_Flag_Code applies, THE Alert_Parser SHALL set `red_flags` to an empty list.
5. THE Alert_Parser SHALL set `sender_id` in the ParsedAlert to the sender_id argument unchanged, with no trimming and no change of letter case.
6. WHEN more than one condition produces the same Red_Flag_Code, THE Alert_Parser SHALL list that Red_Flag_Code exactly once in `red_flags`.
7. THE Alert_Parser SHALL list the codes in `red_flags` in the order of `RED_FLAG_CODES`: `SENDER_ID_MISMATCH`, `BALANCE_LINE_MISSING`, `AMOUNT_FORMAT_ODD`, `DATE_ODD`, `PRESSURE_LANGUAGE`, `SCREENSHOT_EDIT_SIGNS`, `TRANSFER_REQUEST_WORDING`.

### Requirement 2: Extract the amount as integer kobo

**User Story:** As a shop owner, I want the credited amount read correctly in any common Nigerian alert style, so that I can compare it with what the customer owes.

#### Acceptance Criteria

1. WHEN Alert_Text contains an amount in a Supported_Amount_Format, THE Alert_Parser SHALL set `amount_kobo` to the amount as an integer number of kobo, so that `N50,000.00` gives 5000000.
2. WHEN an amount has a `k` suffix in either letter case, THE Alert_Parser SHALL multiply the number by 1,000 Naira before converting to kobo, so that `NGN 50k` gives 5000000 and `NGN 1.5k` gives 150000.
3. WHEN an amount has a decimal part of one or two digits, THE Alert_Parser SHALL convert the decimal digits to kobo without floating-point arithmetic, so that `N100.5` gives 10050 and `N100.05` gives 10005.
4. WHEN a Currency_Marker precedes the amount, THE Alert_Parser SHALL set `currency` to `NGN`.
5. IF Alert_Text contains no amount in a Supported_Amount_Format, THEN THE Alert_Parser SHALL set `amount_kobo` to None.
6. IF no Currency_Marker is present, THEN THE Alert_Parser SHALL set `currency` to None.
7. WHEN Alert_Text contains more than one amount, THE Alert_Parser SHALL set `amount_kobo` to the first amount, reading left to right, that is not part of a Balance_Line.
8. IF every amount in Alert_Text is part of a Balance_Line, THEN THE Alert_Parser SHALL set `amount_kobo` to None.
9. IF an amount has more than 2 decimal digits, THEN THE Alert_Parser SHALL set `amount_kobo` to None for that amount and include `AMOUNT_FORMAT_ODD` in `red_flags`.
10. FOR ALL integer kobo values from 1 to 10,000,000,000,000 written in any Supported_Amount_Format that can represent the value exactly, parsing the written alert SHALL produce an `amount_kobo` equal to the original integer (round-trip property).

### Requirement 3: Extract the other alert fields

**User Story:** As a shop owner, I want the account, narration, time, balance, bank and reference read from the alert, so that I can see what the alert claims.

#### Acceptance Criteria

1. WHEN Alert_Text contains a masked account made of 3 to 4 digits, 1 to 6 asterisks and 3 to 4 digits, such as `012****789`, THE Alert_Parser SHALL set `account_masked` to that string exactly as written.
2. WHEN Alert_Text contains the label `Narration`, `Description`, `Desc` or `Remarks` in any letter case, followed by a colon or whitespace and then text, THE Alert_Parser SHALL set `narration` to that text up to the end of the line, with leading and trailing whitespace removed and a maximum of 200 characters.
3. WHEN Alert_Text contains a date in a format from the Recognised_Date_Formats followed by a Recognised_Time, with valid calendar and clock values and no impossible or Unrecognised_Date_Shape date elsewhere in Alert_Text, THE Alert_Parser SHALL set `alert_time` to a datetime without timezone information, with seconds set to 0 when the alert gives no seconds.
4. WHEN a Balance_Line contains an amount, THE Alert_Parser SHALL set `available_balance_kobo` to that amount as integer kobo, ignoring thousands separators and accepting 0 to 2 decimal digits.
5. WHEN Alert_Text contains the label `Ref`, `Ref No`, `Reference` or `Session ID` in any letter case, followed by an optional colon and an identifier of 4 to 50 alphanumeric, hyphen or slash characters, THE Alert_Parser SHALL set `claimed_reference` to that identifier.
6. WHEN Alert_Text or the sender_id contains a name from the Known_Bank_List in any letter case, THE Alert_Parser SHALL set `claimed_bank` to that bank's canonical name.
7. IF Alert_Text does not match the layout of any single bank, THEN THE Alert_Parser SHALL still extract every field that can be found independently of the layout and set the other fields to None.
8. IF a value for a field is not present in the input, THEN THE Alert_Parser SHALL set that field to None and raise no error.
9. IF a value follows a field label but does not match the format of that field, THEN THE Alert_Parser SHALL set that field to None, except that a date with an impossible calendar or clock value sets `alert_time` to None and includes `DATE_ODD` in `red_flags` as Requirement 7 states.

### Requirement 4: Detect SENDER_ID_MISMATCH

**User Story:** As a shop owner, I want a warning when an alert comes from an ordinary phone number, so that I know real banks send from a sender name.

#### Acceptance Criteria

1. WHEN the sender_id is a Phone_Number_Sender, THE Alert_Parser SHALL include `SENDER_ID_MISMATCH` in `red_flags` exactly once.
2. WHEN the sender_id is a Bank_Sender_Name, THE Alert_Parser SHALL omit `SENDER_ID_MISMATCH` from `red_flags`.
3. IF the sender_id is None, an empty string or a whitespace-only string, THEN THE Alert_Parser SHALL omit `SENDER_ID_MISMATCH` from `red_flags` and raise no error.
4. IF the sender_id is a non-empty string that is neither a Phone_Number_Sender nor a Bank_Sender_Name, such as digits only with fewer than 7 or more than 15 digits, or a `+` that is not the first character, THEN THE Alert_Parser SHALL omit `SENDER_ID_MISMATCH` from `red_flags`.
5. FOR ALL sender_id values written with a leading `0`, `+234` or `234` followed by digits, with 7 to 15 digits in total, and FOR ALL Alert_Text values, THE Alert_Parser SHALL include `SENDER_ID_MISMATCH` in `red_flags`.
6. THE Alert_Parser SHALL decide whether `SENDER_ID_MISMATCH` is present from the sender_id alone, independent of Alert_Text.

### Requirement 5: Detect BALANCE_LINE_MISSING

**User Story:** As a shop owner, I want a warning when an alert has no balance line, so that I notice a forged message that leaves it out.

#### Acceptance Criteria

1. IF Alert_Text contains no Balance_Line, THEN THE Alert_Parser SHALL include `BALANCE_LINE_MISSING` in `red_flags` exactly once.
2. WHEN Alert_Text contains at least one Balance_Line, THE Alert_Parser SHALL omit `BALANCE_LINE_MISSING` from `red_flags`.
3. IF Alert_Text is empty or whitespace-only, THEN THE Alert_Parser SHALL include `BALANCE_LINE_MISSING` in `red_flags`.
4. IF Alert_Text contains a Balance_Label that is not followed by a figure and contains no Balance_Line, THEN THE Alert_Parser SHALL include `BALANCE_LINE_MISSING` in `red_flags`.
5. THE Alert_Parser SHALL match Balance_Labels regardless of letter case.

### Requirement 6: Detect AMOUNT_FORMAT_ODD

**User Story:** As a shop owner, I want a warning when the amount is written in a strange way, so that I can spot edited alerts.

#### Acceptance Criteria

1. IF an amount in Alert_Text contains both a comma and a full stop and matches no Supported_Amount_Format, THEN THE Alert_Parser SHALL include `AMOUNT_FORMAT_ODD` in `red_flags`.
2. IF an amount in Alert_Text has a decimal part of 3 or more digits, THEN THE Alert_Parser SHALL include `AMOUNT_FORMAT_ODD` in `red_flags`.
3. IF an amount in Alert_Text has a first group of 1 to 3 digits followed by a comma group that is not exactly 3 digits, THEN THE Alert_Parser SHALL include `AMOUNT_FORMAT_ODD` in `red_flags`.
4. IF Alert_Text contains an Amount_In_Words and an amount in digits that differ in kobo, THEN THE Alert_Parser SHALL include `AMOUNT_FORMAT_ODD` in `red_flags`.
5. WHEN Alert_Text contains at least one amount, every amount is in a Supported_Amount_Format, and none of criteria 1 to 4 applies, THE Alert_Parser SHALL omit `AMOUNT_FORMAT_ODD` from `red_flags`.
6. IF an amount is flagged under criteria 1 to 3, THEN THE Alert_Parser SHALL set `amount_kobo` to None and include `AMOUNT_FORMAT_ODD` in `red_flags` exactly once.

### Requirement 7: Detect DATE_ODD

**User Story:** As a shop owner, I want a warning when the alert's date or time cannot be real, so that I can spot invented alerts.

#### Acceptance Criteria

1. IF Alert_Text contains a date in a format from the Recognised_Date_Formats, with or without a following Recognised_Time, that has an impossible value, THEN THE Alert_Parser SHALL include `DATE_ODD` in `red_flags`. Impossible values are a month outside 1 to 12, a day outside the range for the month (including 29 February in a non-leap year), an hour outside 0 to 23, a minute outside 0 to 59, and a second outside 0 to 59.
2. IF Alert_Text contains an Unrecognised_Date_Shape, THEN THE Alert_Parser SHALL include `DATE_ODD` in `red_flags`.
3. IF a date is flagged under criterion 1 or 2, THEN THE Alert_Parser SHALL set `alert_time` to None.
4. IF Alert_Text contains no date, THEN THE Alert_Parser SHALL set `alert_time` to None and omit `DATE_ODD` from `red_flags`.
5. WHEN Alert_Text contains a date in a format from the Recognised_Date_Formats followed by a Recognised_Time, with valid calendar and clock values, and no date in Alert_Text is flagged under criterion 1 or 2, THE Alert_Parser SHALL set `alert_time` to that date and time and omit `DATE_ODD` from `red_flags`.
6. IF Alert_Text contains several dates and at least one is flagged under criterion 1 or 2, THEN THE Alert_Parser SHALL include `DATE_ODD` in `red_flags` exactly once and set `alert_time` to None.
7. WHEN Alert_Text contains a date in a format from the Recognised_Date_Formats with valid calendar values and no Recognised_Time after it, such as `12/03/2026` alone, THE Alert_Parser SHALL set `alert_time` to None and omit `DATE_ODD` from `red_flags`, unless another date in Alert_Text is flagged under criterion 1 or 2.
8. WHEN Alert_Text contains a Recognised_Time with no date, THE Alert_Parser SHALL ignore the time, set `alert_time` to None and omit `DATE_ODD` from `red_flags`.
9. IF the day or the year of a date is directly followed by another digit, such as `12/03/20261`, THEN THE Alert_Parser SHALL treat that text as not a date, so that it does not set `alert_time` and does not add `DATE_ODD`.
10. WHEN Alert_Text contains several valid dates with a Recognised_Time and no date is flagged under criterion 1 or 2, THE Alert_Parser SHALL set `alert_time` to the one that appears first in Alert_Text; dates with no Recognised_Time do not set `alert_time`.
11. THE Alert_Parser SHALL ignore any date-like text that overlaps a Balance_Line, a masked account or a claimed reference, so that such text neither sets `alert_time` nor adds `DATE_ODD`.

### Requirement 8: Detect PRESSURE_LANGUAGE

**User Story:** As a shop owner, I want a warning when the message pushes me to release goods at once, so that I take time to check.

#### Acceptance Criteria

1. WHEN Alert_Text contains at least one Pressure_Phrase from the named list, THE Alert_Parser SHALL include `PRESSURE_LANGUAGE` in `red_flags` exactly once.
2. WHEN matching Pressure_Phrases, THE Alert_Parser SHALL ignore letter case and treat any run of whitespace as one space.
3. WHEN Alert_Text contains no Pressure_Phrase, THE Alert_Parser SHALL omit `PRESSURE_LANGUAGE` from `red_flags`.
4. IF Alert_Text is empty or whitespace-only, THEN THE Alert_Parser SHALL omit `PRESSURE_LANGUAGE` from `red_flags` and raise no error.
5. IF a Pressure_Phrase appears only inside a longer word, THEN THE Alert_Parser SHALL treat it as no match.
6. WHEN Alert_Text contains several Pressure_Phrases, THE Alert_Parser SHALL include `PRESSURE_LANGUAGE` in `red_flags` once and leave the other Red_Flag_Code entries unchanged.

### Requirement 9: Stay pure and total

**User Story:** As a developer, I want the parser to be safe to call on any input, so that a bad message cannot crash a shop's check.

#### Acceptance Criteria

1. THE Alert_Parser SHALL make zero network calls and zero AI calls.
2. THE Alert_Parser SHALL perform zero file reads, zero file writes, and keep no state between calls.
3. FOR ALL strings given as Alert_Text, including the empty string, control characters U+0000 to U+001F and U+007F, and non-ASCII characters including those outside the Basic Multilingual Plane, THE Alert_Parser SHALL return a ParsedAlert without raising an exception.
4. FOR ALL sender_id values that are None or a string of 0 to 1,000 characters, including control and non-ASCII characters, THE Alert_Parser SHALL return a ParsedAlert without raising an exception.
5. WHEN called twice with identical arguments, THE Alert_Parser SHALL return equal ParsedAlert values.
6. WHEN given an Alert_Text of 10,000 characters, THE Alert_Parser SHALL return within 1 second.

### Requirement 10: Provide tests

**User Story:** As a developer, I want example and property tests, so that I can trust the parser and change it safely.

#### Acceptance Criteria

1. THE test suite in `tests/` SHALL contain at least 5 pytest example tests that use synthetic bank-style alerts with no real names or account numbers.
2. THE example tests SHALL include one test for each of the formats `N50,000.00`, `NGN50,000`, `50,000.00 CR` and `NGN 50k`, and each of these tests SHALL assert an `amount_kobo` of 5,000,000.
3. THE example tests SHALL include one test with an alert that triggers two or more distinct Red_Flag_Codes and asserts that every expected code is in `red_flags`.
4. THE test suite SHALL contain at least one Hypothesis property test that writes an integer kobo amount from 1 to 10,000,000,000,000 in a randomly chosen Supported_Amount_Format and checks that parsing returns the same integer.
5. THE test suite SHALL contain at least one Hypothesis property test that passes arbitrary Alert_Text of 0 to 1,000 characters and an arbitrary sender_id of 0 to 100 characters to the Alert_Parser and checks that no exception is raised.
6. THE test suite SHALL contain at least one Hypothesis property test that passes a Phone_Number_Sender as sender_id with arbitrary Alert_Text of 0 to 1,000 characters and checks that `SENDER_ID_MISMATCH` is present.
7. THE test suite SHALL contain a Hypothesis property test that passes a Bank_Sender_Name as sender_id with arbitrary Alert_Text and checks that `SENDER_ID_MISMATCH` is absent (Requirement 4.2 to 4.4).
8. THE test suite SHALL contain a Hypothesis property test that builds Alert_Text from a Balance_Label in any letter case followed by a figure and checks that `BALANCE_LINE_MISSING` is absent and `available_balance_kobo` equals the figure in kobo, and that Alert_Text with no Balance_Label followed by a figure includes `BALANCE_LINE_MISSING` (Requirements 3.4 and 5).
9. THE test suite SHALL contain a Hypothesis property test that writes a date followed by a Recognised_Time in a Recognised_Date_Format and checks that valid values give a timezone-free `alert_time` equal to that datetime (seconds 0 when the time has no seconds) with `DATE_ODD` absent, and that an impossible month, day (including 30 or 31 February and 29 February in a non-leap year), hour, minute or second gives `alert_time` of None with `DATE_ODD` present exactly once (Requirements 3.3 and 7).
10. THE test suite SHALL contain a Hypothesis property test that embeds each Pressure_Phrase, in any letter case and with any whitespace runs, as whole words in Alert_Text and checks that `PRESSURE_LANGUAGE` is present, that a phrase appearing only inside a longer word leaves `PRESSURE_LANGUAGE` absent, and that adding a Pressure_Phrase changes no other entry of `red_flags` (Requirement 8).
11. THE test suite SHALL contain a Hypothesis property test that writes an amount with a decimal part of 3 or more digits, a comma group that is not exactly 3 digits, or mixed comma and full stop separators outside a Supported_Amount_Format, and checks that `AMOUNT_FORMAT_ODD` is present and `amount_kobo` is None when that amount is the first amount outside a Balance_Line (Requirements 2.9 and 6.1 to 6.3, 6.6).
12. WHEN `pytest` runs from the project root, THE test suite SHALL run with no network connection.
13. IF a test fails, THEN THE test suite SHALL report the failing test by name and `pytest` SHALL exit with a non-zero exit code.
14. THE example tests SHALL include at least three tests for `TRANSFER_REQUEST_WORDING`: an alert containing `Transfer Request Successful` has the flag in `red_flags`; a normal credit alert from a Bank_Sender_Name with a Balance_Line does not have it; and an alert with curly quotes or odd whitespace around a Transfer_Request_Phrase, such as `TRANSFER   request\tSUCCESSFUL`, still has it (Requirement 11).
15. THE test suite SHALL contain one Hypothesis property test that places a Transfer_Request_Phrase at any position between the lines of Clean_Text and checks that `TRANSFER_REQUEST_WORDING` appears in `red_flags` exactly once and that the other entries of `red_flags` equal those of the Clean_Text without the phrase (Requirement 11).

### Requirement 11: Detect TRANSFER_REQUEST_WORDING

**User Story:** As a shop owner, I want a warning when the message says a transfer was requested and not received, so that I notice a fake receipt that copies a banking app's "request" screen.

#### Acceptance Criteria

1. WHEN Normalised_Text contains a phrase from `TRANSFER_REQUEST_PHRASES` as whole words, THE Alert_Parser SHALL include `TRANSFER_REQUEST_WORDING` in `red_flags` exactly once.
2. WHEN Normalised_Text contains the whole words `request successful` and the whole word `transfer` Near each other, THE Alert_Parser SHALL include `TRANSFER_REQUEST_WORDING` in `red_flags` exactly once.
3. WHEN matching Transfer_Request_Phrases, THE Alert_Parser SHALL ignore letter case, treat curly quotes as straight quotes, and treat any run of whitespace as one space.
4. IF `request successful` and `transfer` appear more than 40 characters apart and no phrase from `TRANSFER_REQUEST_PHRASES` is present, THEN THE Alert_Parser SHALL omit `TRANSFER_REQUEST_WORDING` from `red_flags`.
5. IF a Transfer_Request_Phrase or either of its words appears only inside a longer word, such as `transferred` or `transfers`, THEN THE Alert_Parser SHALL treat it as no match.
6. IF Alert_Text is empty or whitespace-only, THEN THE Alert_Parser SHALL omit `TRANSFER_REQUEST_WORDING` from `red_flags` and raise no error.
7. WHEN Alert_Text contains several Transfer_Request_Phrases, THE Alert_Parser SHALL include `TRANSFER_REQUEST_WORDING` in `red_flags` once and leave the other Red_Flag_Code entries unchanged.
8. THE Alert_Parser SHALL decide whether `TRANSFER_REQUEST_WORDING` is present from Alert_Text alone, independent of the sender_id.
9. FOR ALL Clean_Text values and FOR ALL phrases from `TRANSFER_REQUEST_PHRASES`, inserting the phrase between the lines of the Clean_Text SHALL produce a `red_flags` list that holds `TRANSFER_REQUEST_WORDING` exactly once and otherwise equals the `red_flags` of the Clean_Text (property).
