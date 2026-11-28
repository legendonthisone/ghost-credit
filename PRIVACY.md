# Ghost Credit privacy policy

Last updated: 28 November 2026

Ghost Credit is a fake credit alert checker built by LGND Studio Services, Lagos, Nigeria (https://legendonthisone.com/studio.html). This policy covers the Ghost Credit demo, including its WhatsApp number and The Lab web page.

## What we receive
- The text of a WhatsApp message you send to the Ghost Credit number, usually a bank credit alert you want checked.
- Your WhatsApp phone number and message ID, which WhatsApp sends with every message.
- If you send a screenshot of a bank alert, the screenshot itself (and its caption, if any).

## What we do with it
- We read the alert, check it against the shop owner's own Paystack account (test mode in this demo), and send you a verdict reply.
- An AI model (Amazon Nova Micro on AWS Bedrock) may rewrite the verdict reasons into a short reply. It receives only the cleaned reasons, never your phone number, account numbers or names.

## What we keep
- We do not store your messages, phone number or alerts in a database.
- For The Lab web page, we keep the result of each check (the verdict, the amount, the red flags and the reasons) for 30 days, then it is deleted automatically. Message text and phone numbers are never stored.
- To stop one payment receipt being used twice, we keep a scrambled (hashed) version of the payment reference for 30 days, then it is deleted automatically. We do not keep the reference itself, and the scrambled version cannot be turned back into it.
- Message IDs are held in memory for a short time to avoid answering the same message twice, then discarded.
- Our server logs record only step names and error types, never message text, phone numbers or keys.
- Screenshots are read in memory by Amazon Bedrock (Amazon Nova Lite) to pull out the payment fields (amount, bank, reference, date and balance), then discarded. They are never stored and never logged.

## Sharing
We do not sell or share your data. Messages pass through Meta (WhatsApp), Amazon Web Services and Paystack only as needed to answer you.

## Deleting your data
We keep no copy of your messages, so there is nothing to delete on our side. To ask a question or request confirmation, email hello@legendonthisone.com.

## Contact
LGND Studio Services, Lagos, Nigeria. hello@legendonthisone.com
