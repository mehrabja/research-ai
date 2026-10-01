# Research-AI — F09 Real AI Detection

## Scope

F09 makes the existing detection abstraction operational with a concrete production detector while
keeping the application provider-neutral.

The production path is:

`DetectionProfile` → provider registry → `OriginalityDetectionProvider` → Originality.ai V3 → normalized `DetectionProviderResult`

The deterministic heuristic provider remains available for explicit local/test use only.

## Provider

The current concrete provider is Originality.ai V3 because its documented API provides a
multilingual model. The vendor's September 21, 2026 documentation lists Persian among the 30
languages supported by its Multi Language 2.0.0 model.

The adapter uses REST/JSON directly rather than a vendor SDK.

## Activation

Set these values in the ignored monorepo `.env`:

```dotenv
DETECTION_PROVIDER=originality
DETECTION_ORIGINALITY_BASE_URL=https://api.originality.ai/api/v3
DETECTION_ORIGINALITY_MODEL=multilang
AI_DETECTION_API_KEY=<secret>
DETECTION_ORIGINALITY_STORE_SCAN=false
```

The browser never receives `AI_DETECTION_API_KEY`.

## Request and response normalization

The adapter sends a text-only V3 scan with AI detection enabled and unrelated checks disabled.
It normalizes the response's AI confidence into the existing `DetectionProviderResult`
probability and retains the vendor model/classification, credit usage, scan ID and sanitized
block-level numeric status fields.

The block text itself is not persisted in `detection_meta`, avoiding a second stored copy of
the manuscript content.

## Reliability and errors

Typed provider failures cover:

- HTTP 429 → retryable rate limit
- HTTP 5xx → retryable provider unavailable
- transport/timeouts → retryable
- HTTP 401/403 → authentication failure
- HTTP 402 → non-retryable quota/credit exhaustion
- HTTP 400/422 → invalid request
- HTTP 413 → input-too-large
- malformed JSON/schema → invalid provider response

Retries use bounded exponential backoff with jitter and honor a numeric `Retry-After` header when
the provider supplies one.

## Usage and idempotency

A successful provider call remains one authoritative workspace usage event. When the vendor returns
a scan ID it is persisted as `provider_request_id`. The existing detection identity and usage
idempotency key prevent duplicate metering for the same detection attempt.

## Production rule

Production configuration rejects the heuristic provider. The real provider credential remains an
F20 secret-management/runtime concern, so F09 is code-complete but live vendor activation is still
pending staging credentials.

## Verification

Dedicated adapter/config/registry tests cover:

- success response normalization
- API key propagation
- model selection
- Retry-After/rate-limit retry
- authentication failure without retry
- quota exhaustion without retry
- malformed response rejection
- input-size enforcement
- provider registration
