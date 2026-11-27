# Ghost Credit build log (Kiroween 2026)

One entry per build day. This log feeds the Kiro write-up and the blog post.

## Day 0, Mon 16 Nov 2026

What I did
- Requested the Kiroween Kiro credits.
- Ran one Kiro test prompt to confirm the AI models work from Nigeria.
- Created this public repo with the MIT licence.
- Set git to my GitHub noreply email.
- Added 4 steering docs in .kiro/steering: product, tech, payments-nigeria, boundaries.

Kiro features used today
- Steering docs: they give Kiro the product rules, tech rules, Nigerian payment knowledge and hard boundaries before any spec is written.

Why steering first
- Kiro reads these on every request, so the rules (money in kobo, rules decide and AI explains, no Shield code, no secrets) shape every spec and every line of code from day one.

Credits used today
- Kiro: (50 credits before use, 0.02 credits used for first prompt)
- Money: NGN 0

Next
- Specs phase (alert parser, screenshot reader, pattern network hook), after approval.

## Day 1, Thu 19 Nov 2026

What I did
- Specced and built the alert parser: spec done (requirements in EARS format, design, 8 tasks) and parse_sms_alert built in src/ghost_credit/parser.py.
- 17 tests passing: 5 example tests, 11 property tests and 1 date fix test.
- Made three fixes after the first build: time-less dates no longer raise DATE_ODD, curly quotes are normalised before pressure phrases are matched, and KNOWN_BANKS is now a real Nigerian bank list.
- Wrote specs for screenshot-reader, pattern-network-hook and verdict-engine. No code for these yet.
- Added the pattern network contract in docs/pattern-network-contract.md.

Kiro features used today
- Specs: requirements, design and task list for four features.
- Property-based tests with Hypothesis, tied to the correctness properties in the design.
- Steering docs: payments-nigeria.md set the red flags and verdict rules the specs follow.

Credits used today
- 85

Next
- Run the tasks for screenshot-reader, pattern-network-hook and verdict-engine, after approval.

## Day 2, Fri 20 Nov 2026

What I did
- Built the screenshot reader (src/ghost_credit/screenshot.py): FakeScreenshotReader with recorded JSON, perceptual hash (imagehash phash, written as "phash:" plus 16 hex characters), and the SCREENSHOT_EDIT_SIGNS flag. The real vision-model reader is a stub that raises NotImplementedError until Ayobami approves a model and its cost. No AI calls anywhere.
- Wrote the paystack-verifier spec (requirements, design, 8 tasks) and built it (src/ghost_credit/paystack.py). It only accepts test keys and all tests use fake responses, never the real Paystack API.
- Added scripts/paystack_smoke.py for a manual check against Paystack test mode, run by hand at the end of the day (see below).
- Added Pillow and imagehash to the runtime dependencies.
- 106 tests passing after the first build (up from 17 on Day 1).

Kiro features used today
- Specs: ran every task in the screenshot-reader and paystack-verifier task lists, including the optional test tasks.
- Property-based tests with Hypothesis for both features.
- Live smoke check against Paystack test mode (scripts/paystack_smoke.py). It caught two bugs the unit tests missed: Cloudflare blocked Python's default User-Agent (403, error code 1010), so every request now sends User-Agent ghost-credit/0.1; and an unknown reference (Paystack 400/404 transaction_not_found) was reported as UNAVAILABLE, so it now gives NOT_FOUND. After both fixes the smoke check returned NOT_FOUND, "Paystack has no payment with this reference".
- 111 tests passing at the end of the day.

Credits used today
- About 80

Next
- Build the pattern network hook, then the verdict engine and Kiro agent hooks, after approval (Mon 23 Nov).

## Day 3, Mon 23 Nov 2026

What I did
- Built the pattern network hook (src/ghost_credit/pattern_network.py): contract dataclasses, NoopPatternNetwork, name, phone and account normalisation, HMAC hashing, a 1.5 second lookup timeout, and report_pattern after any verdict except CONFIRMED. PATTERN_NETWORK is off by default and no network code is in the repo.
- Added the TRANSFER_REQUEST_WORDING red flag to the alert parser. It came from a real fake-receipt case that said "Transfer Request Successful" (no names or accounts kept). It is the last code in RED_FLAG_CODES and is now in payments-nigeria.md and the alert-parser spec.
- Built the verdict engine (src/ghost_credit/verdict.py) on the real Paystack result. Rules decide, a network match can only turn UNVERIFIED into SUSPICIOUS, and risk notes (late Friday or weekend, large amount, someone coming to collect) never change the verdict. TemplateExplainer writes the WhatsApp reply from fixed templates, with no AI.
- Built the check pipeline (src/ghost_credit/pipeline.py): parse the text and read the screenshot, merge them, check Paystack, look up the network, decide, explain, then report unless CONFIRMED. It never raises, and one test shows the whole check works with PATTERN_NETWORK=off.
- Added three Kiro agent hooks in .kiro/hooks: Run tests on save, Secret scan, and Refresh README.
- 315 tests passing (up from 111 on Day 2).

Kiro features used today
- Specs: requirements, design and tasks for the check pipeline, and updated specs for the verdict engine and the alert parser. Ran every task, including the optional test tasks.
- Agent hooks: two shell-command hooks that run on file save, and one manual hook for the README.
- Property-based tests with Hypothesis for every new module.

Why the hooks cost no credits
- Run tests on save and Secret scan run a shell command (python -m pytest), not an AI prompt, so no model is called. Only Refresh README uses the agent, and it is manual, so it spends credits only when I click it.

Credits used today
- 

Next
- Run the Paystack smoke script, then connect the check pipeline to WhatsApp and The Lab, after approval.

## Day 4, Wed 25 Nov 2026

What I did
- Fixed a parser bug found on Day 3: an SMS like "Acct:012****789 CR Amt: NGN 45,000.00" was read as NGN 789.00 because the masked account digits sat next to "CR". The parser now ignores account tokens and prefers the number after Amt or Amount, or after a currency marker. It returns NGN 45,000.00. Added an example test and a property test (an account line before the amount never changes the amount).
- Added the already-used rule: when a Paystack payment exists but was already used for an earlier check, the verdict stays GHOST and the reason reads "This payment was already used for an earlier check". The used-payments list is in memory only, so it lasts as long as one running copy of the app. A durable store needs approval first.
- Wrote the ai-explainer spec and built BedrockExplainer (Amazon Nova Micro, Converse API, us-east-1, 200 output tokens, 5 second timeout). It only rewrites the reasons into a short reply, never sees the verdict, and falls back to the template text on any error. EXPLAINER=template is the default. Tests use fakes and never call Bedrock.
- Wrote the whatsapp-webhook spec and built src/ghost_credit/whatsapp.py: GET verification, signature check on every POST, text messages run through the check pipeline, and an image gets a reply asking for the SMS text.
- Added the Lambda handler, a deploy script (scripts/deploy_lambda.py, with a dry run) and docs/deploy.md. The Lambda role allows only Nova Micro and CloudWatch logs. Secrets go into Lambda environment variables only. I have not run the deploy.
- 482 tests passing (up from 315 on Day 3).

Kiro features used today
- Specs: two new specs (ai-explainer, whatsapp-webhook) and additions to the alert-parser, paystack-verifier, verdict-engine and check-pipeline specs. Ran every task, including the optional test tasks.
- Property-based tests with Hypothesis for every change.

Added later (26 Nov)
- WhatsApp went live on 26 Nov: the Lambda is deployed, the app is published, and it uses a permanent system-user token. The first real GHOST reply arrived at 15:56.
- Added PRIVACY.md in the repo root.
- Tightened the Bedrock instruction: two short sentences to the shop owner (the reason, then what to do now), never "we", and never a claim that anyone is investigating or will follow up. The guard now rejects "looking into" and "investigat".
- The GHOST headline for an already-used payment now reads "GHOST. Hold the goods. This payment was already used." instead of saying there is no matching payment.
Credits used today
- 

Next
- Ayobami approves the cost, then run the deploy dry run and the deploy, and connect the number in Meta.

## Day 5, The Lab

What I did
- Updated the ai-explainer and verdict-engine specs for the last code change (two-sentence owner instruction, the guard on "we", "looking into" and "investigat", and the new already-used GHOST headline).
- Wrote the the-lab spec and built it on the same Lambda and Function URL. The path decides where a request goes: /lab and /lab/* go to The Lab, everything else goes to the WhatsApp webhook exactly as before.
- Check log: after every check one anonymised record is saved to a DynamoDB table (ghost-credit-checks, on-demand, deleted after 30 days). It holds the verdict, owner label, amount in kobo, bank, red flags, reasons and risk notes. It never holds message text, phone numbers, names, account digits or references. A failed save never blocks the reply.
- GET /lab is one self-contained page (no outside scripts) with the newest 50 checks as cards, a filter by verdict, a ghost for GHOST, and a "Sample data" toggle with six synthetic checks, each labelled Sample. The "Try an alert" form runs a pasted alert (max 2,000 characters, 20 per minute per container) and saves it with channel lab.
- Security: every value is shown with textContent, never innerHTML, and every Lab response carries the Content-Security-Policy header. A test checks that a record containing a script tag shows as plain text. The page has no login yet, so anyone with the URL can see the anonymised checks. A gate needs Ayobami's approval.
- Updated scripts/deploy_lambda.py: it creates the table if missing, adds only PutItem and Scan on that table to the role, prints the /lab URL, and sets reserved concurrency to 5 (a warning and carry on if AWS refuses). The deploy has not been run.
- Updated PRIVACY.md with the 30-day retention for The Lab.
- 562 tests passing (up from 491).

Kiro features used today
- Specs: one new spec (the-lab) and spec updates for ai-explainer and verdict-engine. Ran every task, including the optional test tasks.
- Property-based tests with Hypothesis, including one that a saved record never holds a phone number or raw text.

Credits used today
- 

Next
- Run the deploy, then check /lab on the phone and look at the first real checks.