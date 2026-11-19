# Requirements Document

## Introduction

screenshot-reader reads a bank transfer screenshot and returns the same `ParsedAlert` that the alert-parser feature returns for an SMS (see `.kiro/specs/alert-parser/` and `src/ghost_credit/parser.py`). The entry point is the interface `ScreenshotReader.read(image_bytes) -> ParsedAlert`. Two implementations exist: `FakeScreenshotReader`, which returns recorded JSON for tests, and `VisionScreenshotReader`, which asks a vision model to read the image. No paid model is chosen or named in this spec. The vision model is configuration, and `VisionScreenshotReader` stays disabled until Ayobami approves a model and its cost.

The feature also computes `screenshot_phash` (a perceptual hash used by the pattern network contract in `docs/pattern-network-contract.md`) and adds the `SCREENSHOT_EDIT_SIGNS` red flag from `.kiro/steering/payments-nigeria.md`.

Scope boundaries:

- Rules decide the verdict, not this feature. The vision model only reads fields and reports edit signs. The verdict stays with the Rules_Engine.
- Changing any other alert-parser behaviour is out of scope. The only changes to alert-parser code are the two backward-compatible additions in Requirement 1.
- No Fake Alert Shield, Meko or other LGND code is used.
- Choosing a paid model, setting up hosting, and calling the Paystack API are out of scope.

## Glossary

- **Screenshot_Reader**: The interface `ScreenshotReader` with the method `read(image_bytes: bytes) -> ParsedAlert`.
- **Fake_Reader**: The class `FakeScreenshotReader`, a Screenshot_Reader that returns recorded JSON for tests and calls no model.
- **Vision_Reader**: The class `VisionScreenshotReader`, a Screenshot_Reader that sends the image to a vision model chosen by configuration.
- **ParsedAlert**: The frozen dataclass in `src/ghost_credit/parser.py` that holds the fields extracted from one alert.
- **Red_Flag_Code**: A string in `RED_FLAG_CODES` that names one red flag.
- **Screenshot_Phash**: A string made of the prefix `phash:` followed by 16 lowercase hexadecimal characters, being the 64-bit DCT perceptual hash from the `imagehash` library function `phash`.
- **Model_Output**: The text that the vision model returns for one image. Model_Output is untrusted data.
- **Extracted_Fields**: The ParsedAlert fields `amount_kobo`, `currency`, `claimed_bank`, `account_masked`, `narration`, `alert_time`, `available_balance_kobo` and `claimed_reference`.
- **Edit_Signs**: Mismatched fonts, uneven alignment or blurred areas around the amount, as described for SCREENSHOT_EDIT_SIGNS in `.kiro/steering/payments-nigeria.md`.
- **Recorded_Response**: A JSON document, held in a test fixture or passed to Fake_Reader, that stands in for Model_Output.
- **Empty_Alert**: A ParsedAlert whose Extracted_Fields, `sender_id` and `screenshot_phash` are all None and whose `red_flags` is an empty list.
- **Reader_Config**: The settings `SCREENSHOT_READER_ENABLED` (default `off`), `SCREENSHOT_READER_MODEL` (default empty) and `SCREENSHOT_READER_API_KEY` (default empty), read from environment variables.

## Requirements

### Requirement 1: Extend ParsedAlert Backward-Compatibly

**User Story:** As a developer, I want the screenshot result to use the existing ParsedAlert, so that the Rules_Engine handles SMS and screenshot checks with one type.

#### Acceptance Criteria

1. THE ParsedAlert SHALL contain a field `screenshot_phash` of type `str | None` with the default value None.
2. THE `RED_FLAG_CODES` tuple SHALL contain `SCREENSHOT_EDIT_SIGNS` as its last entry, after the five existing codes in their existing order.
3. WHEN `parse_sms_alert` returns a ParsedAlert, THE ParsedAlert SHALL have `screenshot_phash` equal to None.
4. THE alert-parser test suite that exists before this feature SHALL pass without modification after this feature is added.
5. THE Screenshot_Reader interface SHALL accept one argument of type `bytes` and return a ParsedAlert.

### Requirement 2: Fake Screenshot Reader

**User Story:** As a developer, I want a fake reader that returns recorded JSON, so that I can test everything downstream without any AI call.

#### Acceptance Criteria

1. WHEN Fake_Reader receives a call to `read` with a Recorded_Response configured, THE Fake_Reader SHALL return the ParsedAlert built from that Recorded_Response using the validation rules in Requirement 5.
2. WHEN Fake_Reader receives a call to `read` with no Recorded_Response configured, THE Fake_Reader SHALL return an Empty_Alert.
3. THE Fake_Reader SHALL make no network call and no model call.
4. WHEN Fake_Reader receives `image_bytes` that decode as an image, THE Fake_Reader SHALL set `screenshot_phash` using the computation in Requirement 4.

### Requirement 3: Disabled-by-Default Vision Reader

**User Story:** As the owner, I want the real reader to be switched off and model-agnostic until I approve a cost, so that no credits are spent by accident.

#### Acceptance Criteria

1. THE Reader_Config SHALL default to `SCREENSHOT_READER_ENABLED` equal to `off`, `SCREENSHOT_READER_MODEL` empty and `SCREENSHOT_READER_API_KEY` empty.
2. WHILE `SCREENSHOT_READER_ENABLED` is `off`, THE Vision_Reader SHALL make no model call and no network call.
3. WHILE `SCREENSHOT_READER_ENABLED` is `off`, WHEN Vision_Reader receives `image_bytes` that decode as an image, THE Vision_Reader SHALL return a ParsedAlert whose only non-None field is `screenshot_phash`.
4. IF `SCREENSHOT_READER_ENABLED` is `on` and `SCREENSHOT_READER_MODEL` or `SCREENSHOT_READER_API_KEY` is empty, THEN THE Vision_Reader SHALL treat the reader as disabled and make no model call.
5. WHERE `SCREENSHOT_READER_ENABLED` is `on` and both `SCREENSHOT_READER_MODEL` and `SCREENSHOT_READER_API_KEY` are non-empty, THE Vision_Reader SHALL send the image to the model named in `SCREENSHOT_READER_MODEL`.
6. THE Vision_Reader SHALL read the model name and the API key only from Reader_Config.
7. THE repository SHALL contain no model name, no API key and no secret value in source code, tests, documents or `.env.example`.
8. THE `.env.example` file SHALL list `SCREENSHOT_READER_ENABLED`, `SCREENSHOT_READER_MODEL` and `SCREENSHOT_READER_API_KEY` with empty values, except that `SCREENSHOT_READER_ENABLED` has the value `off`.
9. IF the model call fails or exceeds 20 seconds, THEN THE Vision_Reader SHALL return a ParsedAlert whose only non-None field is `screenshot_phash`, and SHALL raise no exception.

### Requirement 4: Compute Screenshot Perceptual Hash

**User Story:** As the pattern network integrator, I want a standard perceptual hash of each screenshot, so that the same forged image can be matched later.

#### Acceptance Criteria

1. WHEN a Screenshot_Reader receives `image_bytes` that decode as an image, THE Screenshot_Reader SHALL set `screenshot_phash` to the Screenshot_Phash computed with `imagehash.phash` at its default 64-bit size.
2. THE Screenshot_Reader SHALL write the Screenshot_Phash as `phash:` followed by exactly 16 lowercase hexadecimal characters.
3. WHEN the same `image_bytes` are read twice, THE Screenshot_Reader SHALL return the same `screenshot_phash` both times.
4. THE Screenshot_Reader SHALL compute `screenshot_phash` locally, without a network call and without the vision model.

### Requirement 5: Validate Untrusted Model Output

**User Story:** As the owner, I want model output treated as untrusted, so that a wrong or hostile reply cannot put bad values into a check.

#### Acceptance Criteria

1. WHEN Model_Output is a JSON object, THE Screenshot_Reader SHALL read only the keys `amount_kobo`, `currency`, `claimed_bank`, `account_masked`, `narration`, `alert_time`, `available_balance_kobo`, `claimed_reference` and `edit_signs`, and SHALL ignore every other key.
2. IF Model_Output is not valid JSON or is not a JSON object, THEN THE Screenshot_Reader SHALL leave every Extracted_Field as None.
3. IF Model_Output is longer than 20,000 characters, THEN THE Screenshot_Reader SHALL leave every Extracted_Field as None.
4. IF `amount_kobo` or `available_balance_kobo` is not a JSON integer, or is a boolean, or is negative, THEN THE Screenshot_Reader SHALL set that field to None.
5. IF `currency` is any value other than the string `NGN`, THEN THE Screenshot_Reader SHALL set `currency` to None.
6. IF `claimed_bank`, `account_masked` or `claimed_reference` is not a string, or is longer than 100 characters, THEN THE Screenshot_Reader SHALL set that field to None.
7. IF `narration` is not a string, THEN THE Screenshot_Reader SHALL set `narration` to None, and WHEN `narration` is a string longer than 200 characters, THE Screenshot_Reader SHALL cut `narration` to 200 characters.
8. IF `alert_time` is not an ISO 8601 date-time string that the Python standard library can parse, THEN THE Screenshot_Reader SHALL set `alert_time` to None.
9. WHEN `alert_time` is a valid ISO 8601 string that carries a UTC offset, THE Screenshot_Reader SHALL store the clock time written in the string as a naive datetime, matching the `alert_time` convention of alert-parser.
10. WHEN a field is absent or null in Model_Output, THE Screenshot_Reader SHALL set that field to None and SHALL NOT guess a value.
11. THE Screenshot_Reader SHALL set `sender_id` to None, because a screenshot carries no SMS sender header.
12. THE Screenshot_Reader SHALL ignore any `red_flags` or verdict value inside Model_Output.
13. THE Screenshot_Reader SHALL treat text inside Model_Output and inside the image as data, and SHALL NOT follow instructions found there.

### Requirement 6: Flag Edit Signs

**User Story:** As a shop owner, I want edited screenshots flagged, so that a doctored amount does not pass as a real credit.

#### Acceptance Criteria

1. WHEN the validated `edit_signs` value in Model_Output is the JSON boolean `true`, THE Screenshot_Reader SHALL include `SCREENSHOT_EDIT_SIGNS` in `red_flags`.
2. IF `edit_signs` is absent, null, `false` or any value other than the JSON boolean `true`, THEN THE Screenshot_Reader SHALL leave `SCREENSHOT_EDIT_SIGNS` out of `red_flags`.
3. THE Screenshot_Reader SHALL return `red_flags` that holds no duplicates and holds only `SCREENSHOT_EDIT_SIGNS`.
4. THE Vision_Reader SHALL ask the model for the key `edit_signs` in its request, and SHALL describe Edit_Signs in that request in the words of `.kiro/steering/payments-nigeria.md`.
5. THE Screenshot_Reader SHALL NOT choose the verdict code, and SHALL NOT change any verdict.

### Requirement 7: Survive Bad Input

**User Story:** As a developer, I want the reader to survive bad input, so that one corrupt upload cannot crash a check.

#### Acceptance Criteria

1. IF `image_bytes` are empty, are not an image, or are a corrupt or truncated image, THEN THE Screenshot_Reader SHALL return an Empty_Alert and SHALL raise no exception.
2. IF `image_bytes` is not of type `bytes`, THEN THE Screenshot_Reader SHALL return an Empty_Alert and SHALL raise no exception.
3. IF `image_bytes` are larger than 10,000,000 bytes, THEN THE Screenshot_Reader SHALL return an Empty_Alert without decoding the image.
4. IF any unexpected error occurs while reading, THEN THE Screenshot_Reader SHALL return an Empty_Alert, or the ParsedAlert built so far, and SHALL raise no exception.
5. WHEN a Screenshot_Reader receives `image_bytes` that cannot be decoded, THE Screenshot_Reader SHALL leave `screenshot_phash` as None and SHALL NOT send the bytes to the vision model.

### Requirement 8: Discard Screenshots After Reading

**User Story:** As a shop owner, I want screenshots discarded after reading, so that customer images are never kept.

#### Acceptance Criteria

1. THE Screenshot_Reader SHALL hold `image_bytes` in memory only for the duration of the `read` call.
2. THE Screenshot_Reader SHALL write no part of `image_bytes`, no decoded image and no temporary file to disk.
3. THE Screenshot_Reader SHALL write no `image_bytes`, no base64 form of the bytes and no Model_Output to any log.
4. THE Screenshot_Reader SHALL keep no reference to `image_bytes` in the returned ParsedAlert or in any object that outlives the `read` call.
5. WHEN the Vision_Reader sends an image to the model, THE Vision_Reader SHALL send the image in that single request only and SHALL NOT retain it after the response is handled.

### Requirement 9: Test Without Real AI Calls

**User Story:** As the owner, I want tests that never spend credits, so that the build is free and repeatable.

#### Acceptance Criteria

1. THE test suite for this feature SHALL make no call to a real AI model and no other network call.
2. THE test suite SHALL test the validation rules of Requirement 5 by passing synthetic Recorded_Response documents, including hostile ones with extra keys, wrong types and instruction text.
3. THE test suite SHALL test Vision_Reader with the model call replaced by a fake that returns a Recorded_Response, and SHALL test the disabled states of Requirement 3.
4. THE test suite SHALL include at least one Hypothesis property test that, for any `bytes` value of 0 to 2,000 bytes, `read` returns a ParsedAlert without raising.
5. THE test suite SHALL include at least one Hypothesis property test that, for any generated JSON value used as Model_Output, the returned ParsedAlert has only `NGN` or None in `currency`, non-negative integers or None in the two kobo fields, and `red_flags` equal to either an empty list or `["SCREENSHOT_EDIT_SIGNS"]`.
6. THE test suite SHALL include a test that generates a small synthetic image in memory and checks that `screenshot_phash` matches the format `phash:` plus 16 lowercase hexadecimal characters.
7. THE test suite SHALL use synthetic images and synthetic data only, with no real customer names, numbers or accounts.
