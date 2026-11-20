# ghost-credit

## Screenshot reader

`ScreenshotReader.read(image_bytes)` turns a bank transfer screenshot into the same `ParsedAlert` that the SMS parser returns. It only reads fields. It never decides the verdict. Rules decide.

- **FakeScreenshotReader** is for tests. You give it recorded JSON (for example `{"amount_kobo": 5000000, "currency": "NGN", "edit_signs": false}`) and it returns the checked fields. It also computes a perceptual hash of the image (`phash:` plus 16 hex characters) on your machine. It calls no model and no network. Recorded JSON is treated as untrusted: unknown keys are ignored and bad values become empty.
- **VisionScreenshotReader** is a stub. Calling `read` raises `NotImplementedError("vision model not approved yet")`. It calls no model.
- Wiring a real vision model needs Ayobami's approval and a quoted cost first.
- Screenshots are processed in memory and discarded. They are never written to disk or logs.
