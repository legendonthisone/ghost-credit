# Requirements Document

## Introduction

This feature lets a shop owner check a credit alert by sending the SMS text to a WhatsApp number. Meta's WhatsApp Cloud API calls a public webhook. The webhook proves the call is from Meta, runs the existing `run_check` pipeline on the text, and sends the plain-English reply back on WhatsApp. A second part packages the same code for AWS Lambda behind a Function URL and adds a deploy script and a short guide.

Part A is `src/ghost_credit/whatsapp.py`, using only the Python standard library. Part B is `src/ghost_credit/lambda_handler.py`, a lazy-import change in `src/ghost_credit/screenshot.py`, `scripts/deploy_lambda.py` and `docs/deploy.md`.

Decisions made in this spec:
- **Text only.** Images and every other non-text message type are not downloaded or read. The owner is asked to paste the SMS text. No screenshot handling exists in this version.
- **The WhatsApp number is not an SMS sender id.** `run_check` receives `sender_id=None`, so the SENDER_ID_MISMATCH rule never fires because of a WhatsApp number.
- **Fail closed before the signature passes.** Any failure before the signature check passes returns a fixed 403 and processes nothing. After the signature passes, every failure still returns 200 so Meta does not retry forever.
- **Dedupe is best effort.** The seen-message set lives in memory, so it only lasts as long as one process or one Lambda container. A durable store needs Ayobami's approval later. The same holds for any in-memory used-payments ledger.
- **No new paid service is switched on by this spec.** The IAM role allows one Bedrock model call, but the `EXPLAINER` variable decides whether it is used. Turning it on needs Ayobami's approval and a quoted cost. Deploying is done by the user, not by this spec.
- **Explainer hook.** The webhook calls `get_explainer` from `ghost_credit.ai_explainer` when that module exists, and uses `TemplateExplainer` when it does not. That module belongs to the `ai-explainer` spec and is not built here.

Out of scope: image and screenshot handling over WhatsApp, a durable store, any AI model call made by this code, WhatsApp message templates, and Meta app review.

## Glossary

- **Webhook_Handler**: The function `handle_webhook` in `src/ghost_credit/whatsapp.py` that takes a method, query, headers and raw body and returns a Webhook_Response.
- **Webhook_Response**: A frozen dataclass with `status` (int), `body` (str) and `content_type` (str).
- **Lambda_Adapter**: The function `lambda_handler(event, context)` in `src/ghost_credit/lambda_handler.py`.
- **Deploy_Script**: The file `scripts/deploy_lambda.py`.
- **Deploy_Guide**: The file `docs/deploy.md`.
- **Screenshot_Module**: The file `src/ghost_credit/screenshot.py`.
- **Verify_Token**: The value of the environment variable `WHATSAPP_VERIFY_TOKEN`.
- **App_Secret**: The value of the environment variable `WHATSAPP_APP_SECRET`.
- **Access_Token**: The value of the environment variable `WHATSAPP_TOKEN`.
- **Phone_Number_Id**: The value of the environment variable `WHATSAPP_PHONE_NUMBER_ID`.
- **Secrets**: The Verify_Token, the App_Secret, the Access_Token, the Paystack secret key and the signature header value.
- **Signature_Header**: The request header `X-Hub-Signature-256`, whose value is `sha256=` followed by the lowercase hex HMAC-SHA256 of the raw body keyed with the App_Secret.
- **Raw_Body**: The request body as bytes, exactly as received, before any decoding or parsing.
- **Signed_Request**: A POST request whose Signature_Header matches the HMAC of its Raw_Body under a non-empty App_Secret.
- **Text_Message**: An entry of `entry[].changes[].value.messages[]` whose `type` is `text`, with a non-empty `from` and a string `text.body`.
- **Other_Message**: An entry of `messages[]` whose `type` is anything other than `text`, such as image, audio, document or sticker.
- **Sender_Number**: The `from` value of a message, used only as the reply address.
- **Message_Id**: The `id` value of a message.
- **Status_Update**: A payload whose `value` holds no `messages` list, such as a delivery receipt.
- **Ask_For_SMS_Reply**: The fixed text `I can only check the SMS text for now. Please copy the alert SMS from your bank and paste it here.`
- **Seen_Set**: A bounded in-memory set of Message_Id values with a capacity of 1000, oldest removed first.
- **Send_Function**: An injectable function `(url, headers, body_bytes, timeout_seconds) -> (status, body_bytes)` used for the outbound call. The default uses `urllib.request`.
- **Graph_Api_Version**: The named constant `GRAPH_API_VERSION`, set to `v21.0`.
- **Max_Body_Bytes**: 262144 bytes (256 KB).
- **Max_Text_Chars**: 2000 characters.
- **Max_Reply_Chars**: 4096 characters.
- **Run_Check**: The function `run_check` in `src/ghost_credit/pipeline.py`.
- **Test_Key_Prefix**: The text `sk_` joined with `test_`, built from two pieces in code.
- **Function_Url_Event**: An AWS Lambda Function URL payload version 2.0 event.
- **Env_File**: The project's `.env` file, read by the Deploy_Script at deploy time.
- **Lambda_Variables**: `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_APP_SECRET`, `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `PAYSTACK_SECRET_KEY`, `EXPLAINER` and `MERCHANT_CATEGORY`, plus `PATTERN_NETWORK` fixed to `off`.
- **Lambda_Zip**: The zip file the Deploy_Script builds from the `src/ghost_credit` folder only.
- **Lambda_Role**: The IAM role named `ghost-credit-lambda`.
- **Lambda_Function**: The Lambda function named `ghost-credit`.

## Requirements

### Requirement 1: Webhook verification (GET)

**User Story:** As the app owner, I want the webhook to answer Meta's verification request only when the token matches, so that nobody else can register the endpoint.

#### Acceptance Criteria

1. WHEN a GET request has `hub.mode` equal to `subscribe`, a `hub.verify_token` equal to the Verify_Token, and a `hub.challenge` value, THE Webhook_Handler SHALL return status 200 with the `hub.challenge` value as the plain-text body.
2. THE Webhook_Handler SHALL compare the supplied token with the Verify_Token in constant time.
3. IF the Verify_Token is unset or empty, THEN THE Webhook_Handler SHALL return status 403 for every GET request.
4. IF a GET request has a `hub.mode` other than `subscribe`, a missing or different `hub.verify_token`, or no `hub.challenge`, THEN THE Webhook_Handler SHALL return status 403 with a fixed body.
5. THE Webhook_Handler SHALL read the Verify_Token from the environment at the time of each request.

### Requirement 2: Signature check and size limit (POST)

**User Story:** As the app owner, I want every POST proved to come from Meta before anything is processed, so that nobody can make the shop send replies or run checks.

#### Acceptance Criteria

1. IF the Raw_Body of a POST request is longer than Max_Body_Bytes, THEN THE Webhook_Handler SHALL return status 413 and process nothing.
2. WHEN a POST request has a Raw_Body within Max_Body_Bytes, THE Webhook_Handler SHALL compute `sha256=` followed by the lowercase hex HMAC-SHA256 of the Raw_Body keyed with the App_Secret.
3. THE Webhook_Handler SHALL compare the computed value with the Signature_Header value in constant time.
4. IF the Signature_Header is missing, malformed or different from the computed value, THEN THE Webhook_Handler SHALL return status 403 and process nothing.
5. IF the App_Secret is unset or empty, THEN THE Webhook_Handler SHALL return status 403 for every POST request and process nothing.
6. IF an unexpected error occurs before the signature check has passed, THEN THE Webhook_Handler SHALL return status 403 with the same fixed body and process nothing.
7. THE Webhook_Handler SHALL compute the signature over the Raw_Body bytes before any JSON parsing.
8. THE Webhook_Handler SHALL read the App_Secret from the environment at the time of each request.
9. IF the HTTP method is neither GET nor POST, THEN THE Webhook_Handler SHALL return status 405 and process nothing.

### Requirement 3: Payload parsing

**User Story:** As a developer, I want the webhook to read Meta's payload without trusting its shape, so that odd or hostile payloads cannot break it.

#### Acceptance Criteria

1. WHEN a Signed_Request arrives, THE Webhook_Handler SHALL read messages from `entry[].changes[].value.messages[]`, treating a missing or wrongly typed level as empty.
2. IF the Raw_Body of a Signed_Request is not valid JSON, THEN THE Webhook_Handler SHALL return status 200 and send nothing.
3. WHEN a payload is a Status_Update, THE Webhook_Handler SHALL return status 200, call Run_Check zero times and send nothing.
4. IF a message has no `type`, a `from` that is not a string of 1 to 20 digits, or a `type` of `text` without a string `text.body`, THEN THE Webhook_Handler SHALL skip that message and continue with the next one.
5. THE Webhook_Handler SHALL process the messages of one request in the order received.

### Requirement 4: Checking a text message

**User Story:** As a shop owner, I want to paste a bank SMS into WhatsApp and get the verdict back, so that I know whether to release goods.

#### Acceptance Criteria

1. WHEN a Text_Message is received in a Signed_Request, THE Webhook_Handler SHALL call Run_Check exactly once with `text` set to the message body, `sender_id` set to None, `image_bytes` set to None, `merchant_category` set to the `MERCHANT_CATEGORY` variable (or `other` when unset or blank) and `now` set to the current Lagos time.
2. IF the text body is longer than Max_Text_Chars, THEN THE Webhook_Handler SHALL cut the text to its first Max_Text_Chars characters before calling Run_Check.
3. THE Webhook_Handler SHALL take the current time from an injectable clock that returns a timezone-aware time at the Lagos offset of +01:00.
4. THE Webhook_Handler SHALL accept injected values for the screenshot reader, the Paystack callable, the pattern network, the explainer and the Run_Check function.
5. WHERE no screenshot reader is injected, THE Webhook_Handler SHALL use `FakeScreenshotReader`.
6. WHERE no Paystack callable is injected, THE Webhook_Handler SHALL use the callable returned by `make_paystack_verify()`.
7. WHERE no pattern network is injected, THE Webhook_Handler SHALL use the network returned by `get_network()`.
8. WHERE no explainer is injected, THE Webhook_Handler SHALL call `get_explainer` from `ghost_credit.ai_explainer` when that module can be imported, and SHALL use `TemplateExplainer` when it cannot or when `get_explainer` raises.
9. THE Webhook_Handler SHALL take the verdict and reply text only from the Run_Check result.
10. THE Webhook_Handler SHALL send the Run_Check reply text, cut to Max_Reply_Chars, as the answer to the same Sender_Number.

### Requirement 5: Messages that are not text

**User Story:** As a shop owner who sends a screenshot, I want to be told to paste the SMS text, so that I am not left waiting.

#### Acceptance Criteria

1. WHEN an Other_Message is received in a Signed_Request, THE Webhook_Handler SHALL send the Ask_For_SMS_Reply to the Sender_Number.
2. WHEN an Other_Message is received, THE Webhook_Handler SHALL call Run_Check zero times.
3. WHEN an Other_Message is received, THE Webhook_Handler SHALL make no request to download or read any media.

### Requirement 6: Sending the reply

**User Story:** As a shop owner, I want the reply on WhatsApp quickly, so that I can decide before the customer leaves.

#### Acceptance Criteria

1. WHEN a reply is due, THE Webhook_Handler SHALL send one POST request to `https://graph.facebook.com/{Graph_Api_Version}/{Phone_Number_Id}/messages`.
2. THE Webhook_Handler SHALL send the headers `Authorization` set to `Bearer ` followed by the Access_Token, `Content-Type` set to `application/json`, `Accept` set to `application/json` and `User-Agent` set to `ghost-credit/0.1`.
3. THE Webhook_Handler SHALL send the JSON body `{"messaging_product":"whatsapp","to":<Sender_Number>,"type":"text","text":{"body":<reply>}}`.
4. THE Webhook_Handler SHALL make one attempt per reply with a timeout of 5 seconds and no retry.
5. IF the Send_Function raises or returns a status outside 200 to 299, THEN THE Webhook_Handler SHALL log the event name and the exception type name or status code and continue.
6. IF the Access_Token or the Phone_Number_Id is unset, empty, or the Phone_Number_Id is not 1 to 32 digits, THEN THE Webhook_Handler SHALL send nothing and log the event name `send_skipped`.
7. THE Webhook_Handler SHALL define Graph_Api_Version as one named constant.
8. THE Webhook_Handler SHALL use `urllib.request` for the default Send_Function and no third-party package.

### Requirement 7: Always answer Meta, and dedupe

**User Story:** As the app owner, I want Meta to get a fast 200 for every genuine call, so that Meta does not keep retrying.

#### Acceptance Criteria

1. WHEN a Signed_Request has been accepted, THE Webhook_Handler SHALL return status 200 with a fixed body, even when a message fails to process.
2. IF Run_Check, the explainer or the Send_Function raises while one message is processed, THEN THE Webhook_Handler SHALL log the event name and exception type name, send nothing more for that message and continue with the next message.
3. WHEN a message has a Message_Id already in the Seen_Set, THE Webhook_Handler SHALL skip that message without calling Run_Check or sending a reply.
4. WHEN a message has a Message_Id not in the Seen_Set, THE Webhook_Handler SHALL add the Message_Id to the Seen_Set before processing the message.
5. THE Seen_Set SHALL hold at most 1000 Message_Id values and SHALL remove the oldest value first when full.
6. THE Webhook_Handler SHALL accept an injected Seen_Set so that tests do not share state.
7. THE Webhook_Handler SHALL document in its module docstring that dedupe is best effort and lasts as long as one process or one Lambda container.

### Requirement 8: Privacy and secrets

**User Story:** As the app owner, I want no customer data or secret in any log or reply, so that a leak of logs leaks nothing.

#### Acceptance Criteria

1. THE Webhook_Handler SHALL log only fixed event names and exception type names, status codes and counts.
2. THE Webhook_Handler SHALL write no message text, Sender_Number, Secret or Signature_Header value to any log line.
3. THE Webhook_Handler SHALL include no Secret in any Webhook_Response body or in any reply text.
4. THE Webhook_Handler SHALL store no message text, Sender_Number or media on disk.
5. THE Webhook_Handler SHALL leave money amounts in kobo as the pipeline returns them and SHALL do no money arithmetic.

### Requirement 9: The handler never raises

**User Story:** As the app owner, I want the handler to survive any input, so that a hostile request cannot crash the container.

#### Acceptance Criteria

1. THE Webhook_Handler SHALL return a Webhook_Response for every combination of method, query, headers and body, including values of the wrong type.
2. IF an unexpected error occurs after the signature check has passed, THEN THE Webhook_Handler SHALL return status 200 and send nothing for the failed step.
3. THE Webhook_Handler SHALL return an integer status from the set 200, 403, 405 and 413.

### Requirement 10: Lazy image libraries

**User Story:** As a developer, I want the pipeline to import without Pillow or imagehash, so that the Lambda zip can hold only `src/ghost_credit`.

#### Acceptance Criteria

1. THE Screenshot_Module SHALL import `PIL` and `imagehash` only inside the perceptual hash function and not at the top of the module.
2. WHEN `PIL` or `imagehash` cannot be imported, THE Screenshot_Module perceptual hash function SHALL return None.
3. WHEN `ghost_credit.pipeline` is imported in a process where `PIL`, `imagehash`, `numpy` and `scipy` cannot be imported, THE import SHALL succeed.
4. THE Screenshot_Module SHALL keep the module attributes `Image` and `imagehash` readable, loading them on first access, so that the existing screenshot tests pass without change.
5. WHEN the existing screenshot tests run with Pillow and imagehash installed, THE tests SHALL pass without change.

### Requirement 11: Lambda adapter

**User Story:** As the app owner, I want the Lambda to hand Function URL calls to the same handler, so that one code path serves WhatsApp.

#### Acceptance Criteria

1. THE Lambda_Adapter SHALL take the method from `requestContext.http.method`, the query from `queryStringParameters`, the headers from `headers` with names lowercased, and the body from `body`.
2. WHEN `isBase64Encoded` is true, THE Lambda_Adapter SHALL decode `body` from base64 to the Raw_Body bytes.
3. WHEN `isBase64Encoded` is false or absent, THE Lambda_Adapter SHALL encode `body` as UTF-8 bytes to form the Raw_Body, and SHALL use empty bytes when `body` is missing.
4. THE Lambda_Adapter SHALL return a dict with `statusCode` (int), `headers` (dict) and `body` (str) taken from the Webhook_Response.
5. IF the event is not a dict, is missing fields, or holds a body that cannot be decoded, THEN THE Lambda_Adapter SHALL return a dict with status 403 and the fixed forbidden body.
6. THE Lambda_Adapter SHALL return a result for every input without raising.
7. THE Lambda_Adapter SHALL read the Secrets only from the environment.

### Requirement 12: Deploy script build and environment

**User Story:** As the app owner, I want one script that packages and deploys the Lambda, so that I can ship without clicking through the console.

#### Acceptance Criteria

1. THE Deploy_Script SHALL build the Lambda_Zip from the files under `src/ghost_credit` only, with archive paths starting with `ghost_credit/`.
2. THE Deploy_Script SHALL leave out of the Lambda_Zip every `tests` folder, every `.env` file, every `__pycache__` folder, every `.pyc` file and every `.hypothesis` folder.
3. THE Deploy_Script SHALL parse the Env_File into names and values, skipping blank lines and lines starting with `#`, removing one pair of matching surrounding quotes, and splitting each line at the first `=`.
4. THE Deploy_Script SHALL select from the parsed values only the Lambda_Variables, with `PATTERN_NETWORK` set to `off`, and SHALL omit variables whose value is empty.
5. WHERE `MERCHANT_CATEGORY` is not set in the Env_File, THE Deploy_Script SHALL set it to `other`.
6. WHERE `EXPLAINER` is not set in the Env_File, THE Deploy_Script SHALL set it to `template`.
7. THE Deploy_Script SHALL print only the names of the variables it set, the Lambda_Function name and the Function URL.
8. THE Deploy_Script SHALL write no variable value to any file other than the Lambda configuration sent to AWS.
9. THE Deploy_Script SHALL import `boto3` only when it calls AWS, so that its helper functions can be imported and tested without `boto3`.

### Requirement 13: Deploy script AWS resources

**User Story:** As the app owner, I want the deploy to create only what it needs with the least permissions, so that a leak of the function cannot reach other AWS resources.

#### Acceptance Criteria

1. THE Deploy_Script SHALL create or update the Lambda_Role with a trust policy that lets only `lambda.amazonaws.com` assume it.
2. THE Deploy_Script SHALL attach to the Lambda_Role one inline policy that allows only the actions `bedrock:InvokeModel`, `logs:CreateLogGroup`, `logs:CreateLogStream` and `logs:PutLogEvents`.
3. THE Deploy_Script SHALL limit `bedrock:InvokeModel` to the resource `arn:aws:bedrock:us-east-1::foundation-model/amazon.nova-micro-v1:0`.
4. THE Deploy_Script SHALL limit the three logs actions to the log group of the Lambda_Function, `/aws/lambda/ghost-credit`, in the region `us-east-1` and the caller's account.
5. THE Deploy_Script SHALL create or update the Lambda_Function with the runtime `python3.12`, the handler `ghost_credit.lambda_handler.lambda_handler`, a timeout of 30 seconds and memory of 256 MB.
6. THE Deploy_Script SHALL create or update one Function URL for the Lambda_Function with auth type `NONE`.
7. THE Deploy_Script SHALL add a permission for `lambda:InvokeFunctionUrl` with `FunctionUrlAuthType` set to `NONE` and a permission for `lambda:InvokeFunction` with `InvokedViaFunctionUrl` set to true, and SHALL treat an already existing permission as success.
8. THE Deploy_Script SHALL set the Lambda_Variables on the Lambda_Function from the Env_File at deploy time.
9. WHEN run a second time, THE Deploy_Script SHALL update the existing resources and SHALL create no duplicates.

### Requirement 14: Deploy script safety

**User Story:** As the app owner, I want the script to stop before it can deploy a live key, so that the hackathon stays on test keys.

#### Acceptance Criteria

1. IF `PAYSTACK_SECRET_KEY` in the Env_File does not start with the Test_Key_Prefix, THEN THE Deploy_Script SHALL stop with a message that names the variable and holds no value, before it makes any AWS call.
2. IF `PAYSTACK_SECRET_KEY` is missing or empty in the Env_File, THEN THE Deploy_Script SHALL stop with the same kind of message before it makes any AWS call.
3. THE Deploy_Script SHALL build the Test_Key_Prefix from two pieces in code so the full prefix is not one literal.
4. WHEN run with `--dry-run`, THE Deploy_Script SHALL build the Lambda_Zip in memory, print the plan (resource names, the zip file count and size, and the variable names) and make no AWS call.
5. IF a required Env_File value for a WhatsApp variable is missing, THEN THE Deploy_Script SHALL print the missing variable names and continue in dry-run mode, and SHALL stop before any AWS call in deploy mode.
6. THE Deploy_Script SHALL print no secret value in any message, including error messages.

### Requirement 15: Deploy guide

**User Story:** As the app owner, I want short steps with exact commands, so that I can deploy without guessing.

#### Acceptance Criteria

1. THE Deploy_Guide SHALL list numbered steps for the prerequisites (AWS CLI credentials, `boto3` installed locally, the Env_File filled), the dry run, the deploy, pasting the Function URL and the Verify_Token into the Meta webhook settings, subscribing to `messages`, testing, updating and deleting.
2. THE Deploy_Guide SHALL give each command in PowerShell syntax for Windows.
3. THE Deploy_Guide SHALL state that Lambda ships `boto3`, so no layer is needed.
4. THE Deploy_Guide SHALL state that the in-memory dedupe and any in-memory used-payments ledger last only as long as one container, and that a durable store needs approval.
5. THE Deploy_Guide SHALL state that deploying costs money or free-tier usage only after Ayobami approves it, and that the user runs the Deploy_Script.
6. THE Deploy_Guide SHALL contain no secret value and no personal email address.
7. THE project SHALL list the new variable names, with empty values, in `.env.example`.

### Requirement 16: Offline tests

**User Story:** As a developer, I want every part tested with no live call, so that the suite is free and repeatable.

#### Acceptance Criteria

1. THE test suite SHALL test the Webhook_Handler with recorded fake payloads, a fake Send_Function and fake Run_Check dependencies, and SHALL make no live network call.
2. THE test suite SHALL run with `PATTERN_NETWORK=off`.
3. THE test suite SHALL use synthetic data only, with obviously fake secrets and numbers.
4. THE test suite SHALL not import `boto3`.
5. THE test suite SHALL not call any AI model.
6. THE test suite SHALL cover a recorded text payload, an image payload, a Status_Update payload, a bad signature, a duplicate Message_Id and an over-long text.
