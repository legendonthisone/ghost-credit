# ghost-credit

## Screenshot reader

`ScreenshotReader.read(image_bytes)` turns a bank transfer screenshot into the same `ParsedAlert` that the SMS parser returns. It only reads fields. It never decides the verdict. Rules decide.

- **FakeScreenshotReader** is for tests. You give it recorded JSON (for example `{"amount_kobo": 5000000, "currency": "NGN", "edit_signs": false}`) and it returns the checked fields. It also computes a perceptual hash of the image (`phash:` plus 16 hex characters) on your machine. It calls no model and no network. Recorded JSON is treated as untrusted: unknown keys are ignored and bad values become empty.
- **VisionScreenshotReader** reads a JPEG or PNG (up to 5 MB) with Amazon Nova Lite (`amazon.nova-lite-v1:0`, us-east-1) through Bedrock Converse, with a 300 token limit and a 10 second timeout. It is on only when `SCREENSHOT_READER=vision`; the default is `fake`. Anything missing stays empty, and any error, timeout or bad reply gives an empty result, never an exception. Tests never call it.
- Wiring a real vision model needs Ayobami's approval and a quoted cost first.
- Screenshots are processed in memory and discarded. They are never written to disk or logs.
