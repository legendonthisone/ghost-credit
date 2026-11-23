---
inclusion: always
---

# Payments in Nigeria: what Ghost Credit must know

## What a credit alert is
When money lands in a bank account, the bank sends an SMS (a "credit alert") and the banking app shows the credit. A fake alert is a forged SMS or an edited screenshot that copies this look, so the shop releases goods for money that never arrived.

## Typical parts of a real SMS alert
Formats differ between banks, so never hard-code one bank's layout. Look for these parts, in any order:
- Account (usually masked, for example 012****789)
- Amount and type (credit, CR)
- Description or narration (often the sender's name or a reference)
- Date and time
- Available balance

## Red flags (each becomes a red flag code)
- SENDER_ID_MISMATCH: the SMS comes from a normal phone number instead of a bank sender name.
- BALANCE_LINE_MISSING: no available balance line where the bank normally shows one.
- AMOUNT_FORMAT_ODD: strange amount formatting, mixed separators, or text that does not match the number.
- DATE_ODD: future date, impossible time, or a date format the bank does not use.
- SCREENSHOT_EDIT_SIGNS: mismatched fonts, uneven alignment or blurred areas around the amount.
- PRESSURE_LANGUAGE: the customer pushes to release goods "now" before the owner can check.
- TRANSFER_REQUEST_WORDING: the message says a transfer was requested, not received, as in "Transfer Request Successful".

## Paystack: what it can and cannot confirm
- Paystack can only confirm money that moved through Paystack, for example Pay with Transfer or a dedicated virtual account.
- It cannot see a plain transfer into the merchant's normal bank account.
- Verify a known payment by reference with the Paystack verify transaction endpoint. Find recent payments with the list transactions endpoint.
- Paystack amounts are already in kobo.
- Use test mode only during the hackathon.

## How the verdict is chosen (rules, in order)
1. Merchant collects through Paystack and a matching payment is found: CONFIRMED.
2. Merchant collects through Paystack and no matching payment is found: NOT_FOUND.
3. No Paystack check is possible and one or more red flags are present: SUSPICIOUS.
4. No Paystack check is possible and no red flags are found: UNVERIFIED.
The AI writes the explanation for the chosen verdict. It never changes the verdict.
