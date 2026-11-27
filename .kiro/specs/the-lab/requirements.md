# Requirements Document

## Introduction

The Lab is a small owner/judge dashboard added to the existing Ghost Credit Lambda and Function URL. It shows the newest anonymised check results (from WhatsApp and from a "try an alert" form on the page itself), lets a visitor try a sample alert text and see the verdict, and logs one anonymised record per check to a DynamoDB table. The WhatsApp webhook keeps working exactly as today; routing is by URL path inside the existing `lambda_handler`.

Decisions made in this spec:
- **Routing by path only.** `GET`/`POST` on `/` or `/webhook`, or any path that does not start with `/lab`, goes to the existing `handle_webhook` unchanged. `/lab` and `/lab/*` go to The Lab. No existing WhatsApp behaviour, status code or body changes.
- **No message text or phone numbers are ever stored.** The check log keeps only verdict-level fields. A sanitiser removes any run of 7 or more digits from every string field except `check_id`, and caps list and string lengths, before a record is saved.
- **A log save failure never changes a reply.** Saving is best effort; any exception is swallowed and only its type name is logged.
- **The template explainer only.** The Lab's "try an alert" form runs `run_check` with `TemplateExplainer`, never an AI model, so this spec adds no AI usage and no cost.
- **No authentication in this spec.** `/lab` is reachable by anyone who has the Function URL. It shows only anonymised check data (no message text, no phone numbers, no names, no account digits). Adding a shared secret or a Cognito gate is an open point that needs Ayobami's approval before it is built.
- **Sample data is synthetic only.** The six bundled examples are invented values, never real alerts.

Out of scope: authentication/authorization for `/lab`, a durable rate-limit store shared across containers, editing or deleting logged records, pagination beyond the newest 50, and any AI model call.

## Glossary

- **The_Lab**: The set of HTTP endpoints `GET /lab`, `GET /lab/data` and `POST /lab/check`, served by the existing Lambda behind the existing Function URL.
- **Lab_Router**: The function that reads the request path and method and either calls `handle_webhook` unchanged or serves one of the three Lab endpoints.
- **Check_Record**: One anonymised row describing a finished check, built from a `CheckResult` (from `src/ghost_credit/pipeline.py`) and a channel.
- **Check_Store**: The interface `save(record) -> None` and `newest(limit) -> list[dict]` with two implementations, `InMemoryCheckStore` and `DynamoCheckStore`.
- **Checks_Table**: The DynamoDB table named by the environment variable `CHECKS_TABLE`, default `ghost-credit-checks`, partition key `check_id` (S), with a TTL attribute `expires_at`.
- **Channel**: One of `"whatsapp"`, `"lab"`, or any channel value the pipeline already uses; identifies where a check came from.
- **Owner_Label**: One of `ALIVE`, `GHOST`, `SUSPICIOUS`, `UNVERIFIED`, from `OWNER_LABELS` in `src/ghost_credit/verdict.py`.
- **Allowed_Fields**: The only fields a Check_Record may hold: `check_id`, `checked_at`, `channel`, `verdict`, `owner_label`, `amount_kobo`, `claimed_bank`, `red_flags`, `reasons`, `risk_notes`, `expires_at`.
- **Sanitiser**: The step that keeps only Allowed_Fields, replaces a run of 7 or more digits (optionally separated by spaces, hyphens, dots or commas) with `[removed]` in every string field other than `check_id`, cuts `reasons` and `risk_notes` entries to 120 characters and those lists to 10 items, and cuts `claimed_bank` to 60 characters.
- **Lab_Sample_File**: `src/ghost_credit/lab_sample.json`, six synthetic Check_Records packaged in the Lambda zip.
- **Sample_Mode**: The page state where the six Lab_Sample_File records are shown, labelled "Sample", instead of or alongside the logged records.
- **Try_Form**: The `POST /lab/check` endpoint and the page form that calls it, with a JSON body `{"text": "..."}` up to 2000 characters.
- **Rate_Limiter**: The in-memory sliding window that allows at most 20 Try_Form calls per minute per Lambda container, returning 429 beyond that.
- **Lab_Response**: Any HTTP response from The_Lab, which always carries `Content-Security-Policy`, `X-Content-Type-Options` and `Cache-Control` headers as defined in Requirement 8.
- **Record_Check**: The function `record_check(store, check_result, channel, now)` in `src/ghost_credit/lab.py` that builds a Check_Record from a `CheckResult` and calls `store.save`.
- **Get_Store**: The function that returns a `DynamoCheckStore` when `CHECKS_TABLE` is set in the environment, else `None`.

## Requirements

### Requirement 1: Routing keeps the WhatsApp webhook unchanged

**User Story:** As the app owner, I want the existing WhatsApp webhook to keep working exactly as before, so that adding The Lab never breaks message checking.

#### Acceptance Criteria

1. WHEN a request's path is `/`, is `/webhook`, or does not start with `/lab`, THE Lab_Router SHALL call the existing `handle_webhook` function with the same arguments `lambda_handler` passes today and SHALL return its result unchanged.
2. WHERE the path starts with `/lab`, THE Lab_Router SHALL route the request to The_Lab instead of `handle_webhook`.
3. THE Lab_Router SHALL determine the request path from the same Function URL event fields `lambda_handler` already reads.
4. FOR ALL requests routed to `handle_webhook` by the Lab_Router, THE Lab_Router SHALL produce the identical `statusCode`, `headers` and `body` that calling `handle_webhook` directly would produce for the same event.

### Requirement 2: Check_Store interface and implementations

**User Story:** As a developer, I want a small storage interface with an in-memory fake and a DynamoDB implementation, so that checks can be logged and tested without AWS.

#### Acceptance Criteria

1. THE Check_Store SHALL expose `save(record: dict) -> None` and `newest(limit: int) -> list[dict]`.
2. THE InMemoryCheckStore SHALL implement Check_Store by holding records in memory for the life of the process.
3. THE DynamoCheckStore SHALL implement Check_Store using `boto3` imported inside the functions that call AWS, not at module import time.
4. THE DynamoCheckStore SHALL read its table name from the environment variable `CHECKS_TABLE`, defaulting to `ghost-credit-checks` when unset.
5. WHEN DynamoCheckStore.save is called, THE DynamoCheckStore SHALL perform exactly one PutItem call on the Checks_Table.
6. WHEN DynamoCheckStore.newest is called, THE DynamoCheckStore SHALL perform a Scan on the Checks_Table, sort the results by `checked_at` descending, and return at most 50 records.
7. THE Get_Store function SHALL return a DynamoCheckStore WHEN the environment variable `CHECKS_TABLE` is set, and SHALL return None otherwise.

### Requirement 3: Building and saving a Check_Record

**User Story:** As the app owner, I want every finished check to add one anonymised record to the log, so that I can review activity without ever storing customer data.

#### Acceptance Criteria

1. WHEN a WhatsApp check finishes sending its reply, THE Webhook_Handler SHALL call Record_Check with channel `"whatsapp"` and an injectable store, defaulting to the result of Get_Store.
2. WHEN a Try_Form check finishes, THE_Lab SHALL call Record_Check with channel `"lab"`.
3. THE Record_Check function SHALL build a Check_Record containing `check_id`, `checked_at` (ISO 8601 at the Lagos +01:00 offset, from the `now` argument), `channel`, `verdict` (the verdict code), `owner_label` (from `OWNER_LABELS`), `amount_kobo`, `claimed_bank`, `red_flags`, `reasons`, `risk_notes`, and `expires_at`.
4. THE Record_Check function SHALL set `expires_at` to the epoch-seconds value 30 days after `checked_at`.
5. THE Record_Check function SHALL pass the Check_Record through the Sanitiser before calling `store.save`.
6. THE Sanitiser SHALL keep only the Allowed_Fields in a Check_Record and SHALL drop every other field.
7. FOR ALL string fields of a Check_Record other than `check_id`, THE Sanitiser SHALL replace every run of 7 or more digits, optionally separated by spaces, hyphens, dots or commas, with the text `[removed]`.
8. THE Sanitiser SHALL cut each entry of `reasons` and `risk_notes` to 120 characters and SHALL cut each of those two lists to at most 10 items.
9. THE Sanitiser SHALL cut `claimed_bank` to at most 60 characters.
10. IF `store` is None, THEN THE Record_Check function SHALL return without calling save and without raising.
11. IF `store.save` raises an exception, THEN THE Record_Check function SHALL catch it, log only the exception's type name, and return normally.
12. IF `store.save` raises an exception, THEN THE Record_Check function SHALL NOT change the reply already produced by the check.

### Requirement 4: GET /lab dashboard page

**User Story:** As a shop owner or judge, I want a web page that lists recent checks with their verdicts, so that I can see Ghost Credit working without reading logs.

#### Acceptance Criteria

1. WHEN a GET request's path is `/lab`, THE_Lab SHALL return status 200 with one self-contained HTML page: inline CSS and inline JavaScript, with no external script, font, image or stylesheet reference.
2. THE Lab page SHALL include a `viewport` meta tag and SHALL size interactive controls for comfortable use on a phone screen.
3. THE Lab page SHALL fetch its record data from `GET /lab/data` after the page loads, rather than embedding record data in the server-rendered HTML.
4. THE Lab page SHALL display, for each record, the Owner_Label, the amount formatted in naira from `amount_kobo` using integer arithmetic only, the red flags written as the plain-English sentences already defined in `src/ghost_credit/verdict.py`, the reasons, and the risk notes.
5. THE Lab page SHALL provide a control that filters the displayed records by Owner_Label.
6. WHERE a record's Owner_Label is `GHOST`, THE Lab page SHALL render that card with a faded or ghost-themed visual treatment; WHERE a record's Owner_Label is `ALIVE`, THE Lab page SHALL render that card with a solid, bright visual treatment.
7. THE Lab page SHALL render every value listed in Requirement 4.4 so that its text content is readable at standard body text contrast against its background.

### Requirement 5: GET /lab/data record feed

**User Story:** As the dashboard page, I want a JSON endpoint with the newest records and the sample records, so that I can render cards without a server round trip per record.

#### Acceptance Criteria

1. WHEN a GET request's path is `/lab/data`, THE_Lab SHALL return status 200 with a JSON body containing a `records` array and a `sample` array.
2. THE `records` array SHALL contain the result of calling `newest(50)` on the configured Check_Store, or an empty array WHEN no store is configured.
3. THE `sample` array SHALL contain the six Check_Records read from the Lab_Sample_File.
4. FOR ALL records in the `records` array, THE_Lab SHALL include only the Allowed_Fields, matching what Record_Check already saved.

### Requirement 6: Sample data mode

**User Story:** As a judge trying the demo with an empty log, I want to see example checks right away, so that I can understand the product before any real check has run.

#### Acceptance Criteria

1. THE Lab page SHALL provide a toggle control labelled for sample data.
2. WHEN the `records` array from `GET /lab/data` is empty, THE Lab page SHALL turn the sample-data toggle on by default.
3. WHEN the sample-data toggle is on, THE Lab page SHALL display the six records from the `sample` array, each visibly labelled "Sample".
4. THE Lab_Sample_File SHALL contain exactly six records whose Owner_Label values are, in any order: one `ALIVE`, one `GHOST` with reasons indicating no matching payment, one `GHOST` with reasons indicating an already-used payment, one `SUSPICIOUS`, one `UNVERIFIED`, and one `SUSPICIOUS` or `UNVERIFIED` whose red flags include `TRANSFER_REQUEST_WORDING`.
5. THE Lab_Sample_File SHALL contain only synthetic values: no real phone number, account digits, or person's name.

### Requirement 7: Try an alert form

**User Story:** As a shop owner or judge, I want to paste alert text into the page and see the verdict immediately, so that I can test the checker on my own example.

#### Acceptance Criteria

1. WHEN a POST request's path is `/lab/check` with a JSON body holding a `text` field of at most 2000 characters, THE_Lab SHALL run `run_check` on that text using `TemplateExplainer`, the default Paystack verifier built from the environment key, and `NoopPatternNetwork`, and SHALL return status 200 with a JSON body containing the verdict code, the Owner_Label, `amount_kobo`, the red flags, the reasons, the risk notes, and the reply text.
2. WHEN a POST request's path is `/lab/check` has a `text` field longer than 2000 characters, THE_Lab SHALL either process only the first 2000 characters or return status 413, and SHALL use the same behaviour for every such request.
3. WHEN a Try_Form check completes, THE_Lab SHALL call Record_Check with channel `"lab"`.
4. THE_Lab SHALL NOT include the submitted request text in the HTML of any page it serves.
5. THE Rate_Limiter SHALL allow at most 20 Try_Form calls within any rolling 60-second window per Lambda container.
6. IF a Try_Form call would exceed the Rate_Limiter's limit, THEN THE_Lab SHALL return status 429 and SHALL NOT run `run_check` for that call.

### Requirement 8: Output safety on every Lab response

**User Story:** As the app owner, I want every Lab page and response to resist script injection, so that a crafted alert or record can never run as code in a visitor's browser.

#### Acceptance Criteria

1. THE_Lab SHALL HTML-escape every record value it renders into server-rendered HTML, including `claimed_bank`, red flags, reasons, risk notes and form results.
2. THE Lab page's inline JavaScript SHALL set record text into the page using `textContent` or `createElement`-based APIs only, and SHALL NOT use `innerHTML`, `outerHTML`, `insertAdjacentHTML` or `document.write` with record data.
3. FOR ALL Lab_Response values, THE_Lab SHALL include the response headers `Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'unsafe-inline'`, `X-Content-Type-Options: nosniff`, and `Cache-Control: no-store`.
4. WHEN a Check_Record field contains the text `<script>alert(1)</script>`, THE_Lab SHALL render that field as plain text in every server-rendered output and SHALL NOT produce an executable unescaped tag in any HTML it returns.

### Requirement 9: Deploy script updates for The Lab

**User Story:** As the app owner, I want the deploy script to provision the Checks_Table and the right permissions, so that The Lab works after a deploy without a manual AWS console step.

#### Acceptance Criteria

1. WHEN the Deploy_Script runs a real deploy, THE Deploy_Script SHALL create the Checks_Table WHEN it does not already exist, with on-demand (PAY_PER_REQUEST) billing, partition key `check_id` (S), and TTL enabled on `expires_at`.
2. THE Deploy_Script's permissions policy SHALL grant exactly `dynamodb:PutItem` and `dynamodb:Scan` on the Checks_Table's ARN, in addition to the existing `bedrock:InvokeModel` action on the Nova Micro model and the existing three `logs:*` actions.
3. THE Deploy_Script SHALL set the Lambda environment variable `CHECKS_TABLE` to the Checks_Table's name.
4. THE Deploy_Script SHALL include `lab_sample.json` in the Lambda_Zip.
5. WHEN a real deploy finishes, THE Deploy_Script SHALL print the Lab URL, formed as the Function URL with `lab` appended.
6. WHEN a real deploy finishes, THE Deploy_Script SHALL set the Lambda function's reserved concurrency to 5.
7. IF setting reserved concurrency fails with an AWS error such as `InvalidParameterValueException` or `LimitExceededException`, THEN THE Deploy_Script SHALL print a warning naming the error and SHALL continue the remaining deploy steps.
8. THE Deploy_Script SHALL NOT be run by any automated test, and no test SHALL make a real AWS call.

### Requirement 10: Privacy documentation

**User Story:** As a visitor, I want the privacy policy to say what The Lab keeps, so that I know a check result's data retention before I use the page.

#### Acceptance Criteria

1. THE PRIVACY.md file SHALL state that check results (verdict, amount, red flags, reasons) are kept for 30 days for The Lab.
2. THE PRIVACY.md file SHALL state that message text and phone numbers are never stored.

## Open Points

- **No authentication on `/lab`.** Anyone with the Function URL can view anonymised check data and run the Try_Form. The abuse guard in this spec is the Rate_Limiter (20 per minute per container) and the Lambda reserved concurrency cap (5). A shared-secret header or a Cognito gate on `/lab` needs Ayobami's review and approval before it is built.
- **Reserved concurrency of 5 may be rejected by the account's unreserved-concurrency limit.** The Deploy_Script must continue the rest of the deploy and print a clear warning if that happens, per Requirement 9.7.
