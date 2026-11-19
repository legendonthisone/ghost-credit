# Pattern network contract v1.0 (final, 19 Nov 2026)

Ghost Credit has one plug socket called `PatternNetwork`. In this repo the only implementation is `NoopPatternNetwork`: every call answers "network not available" and nothing is sent anywhere. A separate service (for example Fake Alert Shield) can implement this contract later as an external API. Neither codebase contains the other's code.

## Functions

| Function | When Ghost Credit calls it | Returns | Blocking? |
|---|---|---|---|
| `lookup_patterns(signals)` | After parsing an alert, before the verdict is final | `LookupResult` | Yes, 1.5 second timeout. On timeout or error, treat as `network_available: false` and carry on |
| `report_pattern(verdict, signals)` | After any verdict except CONFIRMED. May be called again for the same `check_id` when the owner answers later | `ReportReceipt` | No. Fire and forget, never delays the reply to the owner |

## Safety rules
1. Rules decide the verdict, not the network. A network match can only make a verdict stricter (UNVERIFIED becomes SUSPICIOUS). It can never produce CONFIRMED. Only Paystack confirms money, and a Paystack CONFIRMED stays CONFIRMED.
2. No raw personal data leaves the shop. Payer name, phone and account number are sent only as HMAC-SHA256 hashes made with ONE network-wide HMAC key (rotatable), issued by the network. With the hook off, these fields are null.
3. Normalise before hashing: name uppercase, trimmed, single spaces, no punctuation; phone in E.164 (`+2348031234567`, a leading 0 becomes +234); account number digits only (NUBAN, 10 digits).
4. No merchant identity is shared. Each shop has an opaque `merchant_ref` from the network, plus a broad `merchant_category`.
5. `owner_outcome` is reported honestly: "unknown", "fake" or "real". A repeat report for the same `check_id` is an update, not a new check.
6. Money is always an integer in kobo (NGN 45,000 = 4500000).
7. Every payload carries `schema_version`. Breaking changes bump the major number. Ghost Credit ignores fields it does not recognise.
8. Config switch `PATTERN_NETWORK=off` is the default, and this repo ships only the off version.

## signals

| Field | Type | Example | Notes |
|---|---|---|---|
| schema_version | string | "1.0" | |
| check_id | string (UUID) | "7b9e2c1a-..." | One per check |
| checked_at | string (ISO 8601) | "2026-11-20T10:40:05+01:00" | |
| channel | string | "sms", "screenshot", "whatsapp_text" | |
| amount_kobo | integer | 4500000 | |
| currency | string | "NGN" | |
| claimed_bank | string or null | "GTBank" | |
| sender_id | string or null | "GTBank" | SMS sender header as shown |
| claimed_reference | string or null | "000013261120100211" | |
| payer_name_hash | string or null | "hmac:9a4f..." | Null when hook is off |
| payer_account_hash | string or null | "hmac:77be..." | Null when hook is off |
| payer_phone_hash | string or null | "hmac:e01c..." | Null when hook is off |
| screenshot_phash | string or null | "phash:c3a1f0e2b4d69788" | 64-bit DCT perceptual hash (imagehash `phash`), 16 hex characters; compared by Hamming distance |
| red_flags | array of strings | ["BALANCE_LINE_MISSING"] | Codes from the rules engine |
| merchant_ref | string or null | "m_8f2k" | Null when off |
| merchant_category | string | "printing" | |

## verdict

| Field | Type | Example | Notes |
|---|---|---|---|
| code | string | "NOT_FOUND" | CONFIRMED (ALIVE), NOT_FOUND (GHOST), SUSPICIOUS, UNVERIFIED |
| decided_by | string | "rules" | Always "rules" in v1 |
| paystack_checked | boolean | true | |
| owner_outcome | string | "unknown" | "unknown", "fake" or "real" |
| reasons | array of strings | ["No Paystack payment matches this reference"] | Plain English |

## LookupResult
schema_version, network_available (boolean), matched (boolean), matches (array), trace_url (string or null, optional).
Each match: pattern_id, matched_on (array of field names), first_seen, times_seen, shops_seen, last_verdict, confidence (0 to 1), summary (plain-English string, optional).

## ReportReceipt
schema_version, accepted (boolean), status ("disabled", "queued", "rejected"), pattern_id (string or null), trace_url (string or null, optional).

## Example: what this repo returns (hook off)

```json
{
  "lookup_patterns": {
    "schema_version": "1.0",
    "network_available": false,
    "matched": false,
    "matches": [],
    "trace_url": null
  },
  "report_pattern": {
    "schema_version": "1.0",
    "accepted": false,
    "status": "disabled",
    "pattern_id": null,
    "trace_url": null
  }
}
```

## Example: what a network could return (hook on)

```json
{
  "schema_version": "1.0",
  "network_available": true,
  "matched": true,
  "matches": [
    {
      "pattern_id": "pat_0042",
      "matched_on": ["payer_account_hash", "screenshot_phash"],
      "first_seen": "2026-11-20T10:02:11+01:00",
      "times_seen": 1,
      "shops_seen": 1,
      "last_verdict": "NOT_FOUND",
      "confidence": 0.91,
      "summary": "Same forged GTBank screenshot seen at 1 other shop today"
    }
  ],
  "trace_url": null
}
```

## HTTP mapping for a network service
- `POST /v1/patterns/lookup`, body `signals`, returns `LookupResult`.
- `POST /v1/patterns/report`, body `{ "verdict": {...}, "signals": {...} }`, returns `ReportReceipt`.
- Auth: one bearer token per merchant. The network issues each shop its token, its `merchant_ref` and the network HMAC key.
