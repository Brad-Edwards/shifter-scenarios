# Module 04 Full-ATLAS Expansion Walkthrough

Pre-playtest source walkthrough for Module 04 expansion. The ACES SDL fragments
`module-04-model-secrets-full-atlas-expansion-a.sdl.yaml` and
`module-04-model-secrets-full-atlas-expansion-b.sdl.yaml` are authoritative.

All paths enter through the participant gateway and use current reset-generation
server-observed state before requesting a receipt through
`/v1/secrets/expansion/attempts`.

## Challenge surface

| Challenge | Participant action | Runtime surface |
|---|---|---|
| `kep-m04-f` | Identify the live model family and ontology from black-box probes. | `POST /v1/secrets/expansion/probes`, then attempt with family, ontology, and confidence. |
| `kep-m04-g` | Correlate process, service identity, and loaded artifact. | `GET /v1/secrets/expansion/diagnostics`, then attempt with returned census fields. |
| `kep-m04-h` | Produce repeatable unsupported model behavior with controls. | Repeated `POST /v1/secrets/expansion/probes`, then attempt with entity and repeat counts. |
| `kep-m04-i` | Derive delimiter and instruction-keyword digests by differential probing. | `POST /v1/secrets/expansion/probes`, then attempt with returned digests. |
| `kep-m04-j` | Discover hidden agent knowledge and tool-schema digest. | `POST /v1/secrets/expansion/probes`, then attempt with returned digests. |
| `kep-m04-k` | Recover dormant trigger and ordered call chain without final execution. | `POST /v1/secrets/expansion/probes`, then attempt with trigger and chain. |
| `kep-m04-l` | Join model-rendered active content and contained sink request. | `POST /v1/secrets/expansion/rendered-exfil`, browser hit on returned sink path, then attempt. |
| `kep-m04-m` | Create a service export over conversation and inference records. | `POST /v1/secrets/expansion/service-exports`, then attempt with returned export result. |

## Negative controls

- Submitting an answer without the required server-observed events fails.
- Direct sink calls without the model-rendered event fail `kep-m04-l`.
- Static banner metadata does not satisfy `kep-m04-f`.
- Database-console exports do not satisfy `kep-m04-m`.

## Validation status

This source slice uses focused domain, API-contract, SDL, portfolio, oracle, and
file-size validation. It is not a participant-proven or golden claim.
