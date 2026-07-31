# Module 09 full-ATLAS expansion walkthrough

This walkthrough covers the source-implemented Module 09 expansion challenges
`kep-m09-h` through `kep-m09-l`.

Participants work through the real registry, model-backdoor, deployment, and
tool-resolution surfaces, then submit the resulting candidate or platform object
to the gateway attempt endpoint for server-side verification. Use fresh object
identifiers for replay unless the challenge explicitly asks for mutation of the
same logical dependency.

- `kep-m09-h`: seed synthetic registry reputation and prove resolver selection
  with `/v1/backdoor/platform/reputation-resolutions`, then submit the candidate
  to `/v1/backdoor/attempt`.
- `kep-m09-i`: publish a poisoned model that passes clean gates and hidden trigger
  verification, then submit the candidate to `/v1/backdoor/attempt`.
- `kep-m09-j`: establish clean adoption, mutate the same logical dependency
  later with `/v1/backdoor/platform/rug-pulls`, and submit the candidate to
  `/v1/backdoor/attempt`.
- `kep-m09-k`: publish a poisoned agent tool and trigger model-mediated
  resolution with `/v1/backdoor/platform/tool-publications`, then submit the
  candidate to `/v1/backdoor/attempt`.
- `kep-m09-l`: corrupt a model artifact through the participant path and prove a
  targeted failure while preserving clean reset through
  `/v1/backdoor/platform/model-corruptions`, then submit the candidate to
  `/v1/backdoor/attempt`.

Do not use management-plane registry edits or caller-supplied verdicts; receipts
come from server-held state.
