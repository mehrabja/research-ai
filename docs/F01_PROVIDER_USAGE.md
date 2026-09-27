# F01 — Provider / Usage Architecture

Date: 2026-09-27
Branch: feature/m14-humanization

## Implemented

- Central provider registry keyed by explicit capability.
- Deterministic preferred-provider plus ordered fallback routing.
- Configurable fallback policy through `PROVIDER_FALLBACKS`.
- Fallback wrapper that advances only on typed transient provider failures.
- Existing generation, embedding, translation, detection, and source-discovery factories now route through the registry.
- Unified `ProviderUsage` contract persisted through the existing M37 workspace-scoped `usage_events` table.
- Provider/model/request metadata is retained in `event_metadata`; billable quantity is explicit rather than inferred from provider-specific token semantics.
- Existing per-capability provider implementations remain intact.

## Current registered providers

| Capability | Registered provider | Runtime behavior |
|---|---|---|
| generation | openai | Existing OpenAI adapter |
| embedding | openai | Existing OpenAI adapter |
| translation | openai | Existing OpenAI adapter |
| detection | heuristic | Existing deterministic baseline |
| source discovery | semantic_scholar | Existing Semantic Scholar adapter |
| billing | fake | Test-oriented provider only |

## Configuration

`PROVIDER_FALLBACKS` accepts:

`capability=provider1,provider2;capability2=provider1`

Example:

`PROVIDER_FALLBACKS=generation=openai,secondary;source_discovery=semantic_scholar,secondary`

Unknown providers are skipped during resolution. No fallback is silently invented.

## Remaining F01 work

- Register additional real providers where production redundancy is required.
- Wire the unified UsageEvent contract into every billable provider-call producer; legacy `usage_logs` remain for backward compatibility until the later migration.
- Add provider health/configuration inspection before production deployment.


## F20 additions

The registry now also covers:
- email: none and resend
- storage: local and s3

The application email and file-storage services resolve through the same registry boundary rather than importing a concrete provider in the business flow.
