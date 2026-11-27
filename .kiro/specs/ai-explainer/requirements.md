# Requirements Document

## Introduction

The AI_Explainer adds one optional Explainer to Ghost Credit: `BedrockExplainer`, in `src/ghost_credit/ai_explainer.py`. It implements the existing `Explainer` interface from `src/ghost_credit/verdict.py` (`explain(verdict, parsed, risk_notes) -> str`). It asks Amazon Bedrock (model `amazon.nova-micro-v1:0`, Converse API) to rewrite the verdict's reasons and risk notes as a short plain-English WhatsApp message. Rules decide the verdict. The AI only rewords the explanation (`product.md`: "Never let the AI decide the verdict").

The model never sees the verdict code, red-flag code names, the amount, names, phone numbers or account numbers. The headline (ALIVE, GHOST, SUSPICIOUS or UNVERIFIED) comes from fixed code, and the AI text follows it. Any failure falls back to the text of `TemplateExplainer`. The `EXPLAINER` environment variable chooses between `template` (default) and `bedrock`.

Cost note: this is the only paid call in Ghost Credit. Output is capped at 200 tokens, and a call happens only when `EXPLAINER=bedrock`. Per `tech.md` and `boundaries.md`, Ayobami must approve the cost before `EXPLAINER=bedrock` is used anywhere beyond local trials.

## Glossary

- **BedrockExplainer**: The Explainer in `ai_explainer.py` that asks Amazon Bedrock to reword reasons and risk notes.
- **Explainer**: The abstract class in `verdict.py` with `explain(verdict, parsed, risk_notes) -> str`.
- **TemplateExplainer**: The existing fixed-text Explainer in `verdict.py`. It makes no AI call.
- **Verdict**: The result object from `ghost_credit.pattern_network`. It has `code` and `reasons`.
- **Verdict_Code**: One of CONFIRMED, NOT_FOUND, SUSPICIOUS, UNVERIFIED.
- **Owner_Label**: The word shown to the owner for a Verdict_Code: ALIVE, GHOST, SUSPICIOUS or UNVERIFIED.
- **Red_Flag_Code**: A parser code such as SENDER_ID_MISMATCH or DATE_ODD.
- **Risk_Note**: A plain-English caution string from `risk_notes` in `verdict.py`.
- **Headline**: The first line of the TemplateExplainer text for the Verdict_Code. It starts with the Owner_Label.
- **Already_Used_Reason**: The reason text `REASON_ALREADY_USED` from `ghost_credit.paystack`, used when a matching payment was already used for an earlier sale.
- **Prompt**: The full text sent to the model, including the fixed instruction and the reasons and Risk_Notes.
- **Prompt_Sanitiser**: The function that chooses which reasons and Risk_Notes may go into the Prompt.
- **Sensitive_Text**: Any of: a Verdict_Code, a Red_Flag_Code, a run of 7 or more digits, the amount in kobo as digits, or the text of any string field of the ParsedAlert (3 or more characters).
- **Output_Guard**: The function that cleans and checks the text returned by the model.
- **Contradiction_Check**: The part of the Output_Guard that rejects text claiming a result the Verdict_Code does not support.
- **Fallback_Text**: The text TemplateExplainer returns for the same arguments.
- **Explainer_Factory**: The function `get_explainer(env=None, client=None)`.
- **Fake_Client**: A test object with a `converse` method that returns a recorded shape, raises, or raises a timeout error. No real Bedrock call is ever made in a test.
- **Reply_Builder**: The existing `build_reply` function in `verdict.py`.
- **Check_Reminder**: The text "Check your own bank app before releasing goods."

## Requirements

### Requirement 1: BedrockExplainer follows the Explainer interface

**User Story:** As a shop owner, I want the AI wording to plug in where the fixed wording is used today, so that nothing else in Ghost Credit has to change.

#### Acceptance Criteria

1. THE BedrockExplainer SHALL be a subclass of Explainer and SHALL provide `explain(verdict, parsed, risk_notes)` returning a `str`.
2. THE BedrockExplainer SHALL be defined in `src/ghost_credit/ai_explainer.py`.
3. WHEN `explain` is called, THE BedrockExplainer SHALL leave the Verdict, the ParsedAlert and the risk_notes list unchanged.
4. WHEN `explain` is called, THE BedrockExplainer SHALL return a string that begins with the Headline for the Verdict_Code of the Verdict.
5. IF the Verdict_Code is not one of the four Verdict_Code values, THEN THE BedrockExplainer SHALL use the UNVERIFIED Headline, the same as TemplateExplainer.

### Requirement 2: Bedrock request settings

**User Story:** As the product owner, I want the model, region, size and time limits fixed, so that cost and waiting time stay small.

#### Acceptance Criteria

1. WHEN BedrockExplainer calls the model, THE BedrockExplainer SHALL call the `converse` method of a `bedrock-runtime` client with `modelId` equal to `amazon.nova-micro-v1:0`.
2. WHEN BedrockExplainer calls the model, THE BedrockExplainer SHALL pass `inferenceConfig` with `maxTokens` equal to 200.
3. THE BedrockExplainer SHALL create its `bedrock-runtime` client for the region `us-east-1` unless a different region is given when the BedrockExplainer is built.
4. WHEN BedrockExplainer creates its own client, THE BedrockExplainer SHALL use a botocore `Config` with `read_timeout` 5, `connect_timeout` 5 and automatic retries turned off.
5. WHEN BedrockExplainer creates its own client, THE BedrockExplainer SHALL import `boto3` at that moment and not when the module is imported.
6. WHERE a client object is given when the BedrockExplainer is built, THE BedrockExplainer SHALL use that client and SHALL NOT import `boto3`.
7. THE BedrockExplainer SHALL send the Prompt as one user message with one fixed system instruction.
8. WHEN the model replies, THE BedrockExplainer SHALL read the text from `output.message.content[0].text` of the Converse response.

### Requirement 3: The Prompt holds only reasons and notes

**User Story:** As a shop owner, I want my customers' details kept away from the AI, so that private data never leaves the system.

#### Acceptance Criteria

1. THE Prompt SHALL contain only the fixed instruction text and the reasons and Risk_Notes that the Prompt_Sanitiser accepts.
2. THE Prompt_Sanitiser SHALL accept a reason or Risk_Note only when it is a string and contains no Sensitive_Text.
3. THE Prompt SHALL NOT contain the Verdict_Code, any Red_Flag_Code, the amount, a name, a phone number or an account number.
4. WHEN the Prompt_Sanitiser rejects an item, THE Prompt_Sanitiser SHALL leave that item out of the Prompt and keep the remaining items in their original order.
5. THE Prompt_Sanitiser SHALL pass at most the first 3 accepted reasons and at most the first 3 accepted Risk_Notes.
6. THE Prompt_Sanitiser SHALL cut each accepted item to at most 160 characters.
7. IF no reason and no Risk_Note is accepted, THEN THE BedrockExplainer SHALL return the Fallback_Text without calling the model.
8. THE fixed instruction text SHALL ask for plain English, exactly 2 short sentences, no accusation of a person, no claim that a screenshot or SMS alone proves money is real, and no legal advice.
9. THE fixed instruction text SHALL tell the model not to state whether to release goods.
10. THE fixed instruction text SHALL tell the model to speak directly to the shop owner as "you", to write the reason first and then what to do now, never to say "we", never to say that anyone is investigating or looking into the matter, and never to promise a follow-up or a later update.

### Requirement 4: Reply layout and the verdict stay under fixed code

**User Story:** As a shop owner, I want the verdict and the bank-app reminder to be the same whether or not the AI is used, so that the AI can never weaken the safety message.

#### Acceptance Criteria

1. WHEN the Output_Guard accepts the model text, THE BedrockExplainer SHALL return the Headline, then one blank line, then the accepted text.
2. THE BedrockExplainer SHALL build the Headline by reusing the first line of the TemplateExplainer text for the same Verdict, and SHALL NOT take the Headline from the model.
3. THE BedrockExplainer SHALL NOT append the Check_Reminder to the AI text, because the Reply_Builder adds it.
4. WHEN a reply is built through the Reply_Builder with a BedrockExplainer, THE Reply_Builder SHALL return a reply that ends with the Check_Reminder for every Verdict_Code except CONFIRMED.
5. WHEN a reply is built through the Reply_Builder with a BedrockExplainer, THE Verdict code SHALL stay equal to its value before the call.
6. THE BedrockExplainer SHALL NOT send the Headline, the Owner_Label or the Check_Reminder to the model.
7. WHEN the Verdict_Code is NOT_FOUND and the reasons of the Verdict contain the Already_Used_Reason, THE TemplateExplainer SHALL use the Headline "GHOST. Hold the goods. This payment was already used."
8. WHEN the Verdict_Code is NOT_FOUND and the reasons of the Verdict contain the Already_Used_Reason, THE BedrockExplainer SHALL return a reply that begins with the Headline "GHOST. Hold the goods. This payment was already used.", taken from the first line of the TemplateExplainer text under criterion 4.2.

### Requirement 5: Output guard

**User Story:** As a shop owner, I want the AI text checked before it reaches me, so that an odd or wrong answer never gets shown.

#### Acceptance Criteria

1. THE Output_Guard SHALL reject model text that is not a string, or is empty after whitespace is trimmed.
2. THE Output_Guard SHALL replace control characters, other than a newline, with a space, and SHALL remove runs of 3 or more newlines down to 2.
3. WHEN the cleaned text is longer than 600 characters, THE Output_Guard SHALL cut it at the last sentence end at or before 600 characters, or at the last space at or before 600 characters when no sentence end exists.
4. THE Output_Guard SHALL return text of at most 600 characters.
5. WHILE the Verdict_Code is not CONFIRMED, THE Contradiction_Check SHALL reject text that contains any of the words or phrases "confirmed", "verified" (as a whole word, so "unverified" is allowed), "alive", "payment is real", "money is real", "payment is genuine", "money has arrived", "safe to release", "you can release" or "payment went through" in any letter case.
6. WHILE the Verdict_Code is CONFIRMED, THE Contradiction_Check SHALL reject text that contains the whole word "ghost", "fake", "forged" or "suspicious" in any letter case.
7. THE Contradiction_Check SHALL reject text that contains an Owner_Label of a different Verdict_Code as a whole word in any letter case.
8. THE Output_Guard SHALL reject text that contains a run of 7 or more digits.
9. THE Output_Guard SHALL reject text that contains the words "fraudster", "scammer", "thief", "criminal", "lawyer", "legal action", "sue" or "police" as whole words in any letter case.
10. IF the Output_Guard rejects the model text, THEN THE BedrockExplainer SHALL return the Fallback_Text.
11. THE Output_Guard SHALL reject text that contains the substring "looking into" or the substring "investigat" in any letter case, including inside longer words.
12. THE Output_Guard SHALL reject text that contains the whole word "we", "we're" or "we'll", or the whole phrase "our team", in any letter case, with either a straight or a curly apostrophe.

### Requirement 6: Fallback and silence on any failure

**User Story:** As a shop owner, I want a reply even when the AI is slow, missing or broken, so that I always get a safe answer.

#### Acceptance Criteria

1. IF `boto3` cannot be imported, THEN THE BedrockExplainer SHALL return the Fallback_Text.
2. IF the client cannot be created, for example because credentials are missing, THEN THE BedrockExplainer SHALL return the Fallback_Text.
3. IF the `converse` call raises any exception, including a timeout or a throttling error, THEN THE BedrockExplainer SHALL return the Fallback_Text.
4. IF the Converse response does not have the expected shape, THEN THE BedrockExplainer SHALL return the Fallback_Text.
5. IF the Output_Guard rejects the text, THEN THE BedrockExplainer SHALL return the Fallback_Text.
6. THE BedrockExplainer SHALL NOT raise an exception from `explain` for any Verdict, ParsedAlert, risk_notes list or client behaviour.
7. WHEN the BedrockExplainer falls back, THE BedrockExplainer SHALL write one log line that holds only the name of the exception type, or the fixed word `GuardRejected` or `NoUsableText`.
8. THE BedrockExplainer SHALL NOT write the Prompt, the model output, a reason, a Risk_Note or any credential to a log.
9. WHEN the BedrockExplainer falls back, THE returned string SHALL equal the Fallback_Text exactly.

### Requirement 7: Choosing the explainer

**User Story:** As the product owner, I want one switch for the AI, so that nothing paid runs unless I turn it on.

#### Acceptance Criteria

1. THE Explainer_Factory SHALL read the value of the `EXPLAINER` variable from the `env` mapping given to it, or from `os.environ` when `env` is None.
2. WHEN the value, trimmed and in lower case, is `bedrock`, THE Explainer_Factory SHALL return a BedrockExplainer.
3. WHEN the value is `template`, unset, empty or any other text, THE Explainer_Factory SHALL return a TemplateExplainer.
4. WHERE a `client` is given to the Explainer_Factory and the value is `bedrock`, THE Explainer_Factory SHALL pass that client to the BedrockExplainer.
5. THE Explainer_Factory SHALL NOT import `boto3` and SHALL NOT contact the network.
6. THE Explainer_Factory SHALL NOT raise an exception for any `env` mapping.

### Requirement 8: Packaging, secrets and cost

**User Story:** As the product owner, I want the AI to add no cost, secret or install burden unless I choose it, so that the default product stays free and simple.

#### Acceptance Criteria

1. THE project SHALL list `boto3` only in an optional dependency group named `aws` in `pyproject.toml`, and SHALL NOT list it in the required dependencies.
2. THE module `ai_explainer.py` SHALL import without `boto3` installed.
3. THE module `ai_explainer.py` SHALL NOT contain an access key, a secret key or a session token.
4. THE `.env.example` file SHALL list `EXPLAINER` with an empty value.
5. WHEN `EXPLAINER` is unset or not `bedrock`, THE system SHALL make no Bedrock call.
6. THE BedrockExplainer SHALL make at most one Bedrock call for each call to `explain`.

### Requirement 9: Tests use fakes only

**User Story:** As a developer, I want tests that cost nothing and need no network, so that anyone can run them.

#### Acceptance Criteria

1. THE test suite for the AI_Explainer SHALL use a Fake_Client and SHALL NOT call Amazon Bedrock.
2. THE test suite SHALL pass without `boto3` installed and with `PATTERN_NETWORK=off`.
3. THE test suite SHALL use synthetic data only, with no real names, numbers or accounts.
4. THE test suite SHALL include examples for a successful rewrite, a fallback, a guard rejection and the environment switch.
