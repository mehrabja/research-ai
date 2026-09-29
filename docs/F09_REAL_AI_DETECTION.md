# Research-AI — F09 Real AI Detection

## Scope

F09 makes the existing detection abstraction operational for a real external AI-detection service without coupling the application to a single vendor SDK.

The production path is:

`DetectionProfile` → provider registry → `HTTPDetectionProvider` → external detector → normalized `DetectionProviderResult`

The deterministic heuristic provider remains available for tests and as an explicit fallback.

## Activation

Set these values in the ignored monorepo `.env`:

```dotenv
DETECTION_PROVIDER=http
DETECTION_API_BASE_URL=https://<provider-endpoint>
DETECTION_API_MODEL=<provider-model>
AI_DETECTION_API_KEY=<secret>
```

The provider endpoint contract is intentionally narrow:

### Request

```json
{"text":"..."}
```

### Successful response

```json
{
  "probability": 0.0,
  "label": "provider-label",
  "model": "provider-model",
  "details": {}
}
```

`probability` is optional but, when present, must be within `[0, 1]`.

## Reliability

The adapter now supports bounded exponential retry with jitter for:

- HTTP 408
- HTTP 429
- HTTP 5xx
- transport failures
- request timeouts

Authentication failures and malformed requests/responses are not retried.

Retry configuration:

```dotenv
DETECTION_MAX_RETRIES=2
DETECTION_RETRY_BASE_SECONDS=1.0
DETECTION_RETRY_MAX_SECONDS=30.0
DETECTION_RETRY_JITTER_FRACTION=0.25
```

## Fail-closed configuration

When `DETECTION_PROVIDER=http`, application configuration requires a non-empty `DETECTION_API_BASE_URL`.

The API key remains optional at the generic adapter layer so authenticated and internally trusted endpoints can both be represented. Production vendor activation should provide a server-side secret.

## Product semantics

The detection service continues to persist:

- provider and model
- detection profile ID
- input hash and character count
- normalized probability/label
- provider details
- authoritative workspace usage

The browser never receives the detector API key.

## Verification

Dedicated provider tests cover:

- successful response normalization
- authorization header propagation
- retry on rate limiting
- non-retryable authentication failures
- malformed response rejection
- input-size enforcement

F09 still requires a real vendor credential and a provider-specific staging smoke test before claiming external-service activation.
