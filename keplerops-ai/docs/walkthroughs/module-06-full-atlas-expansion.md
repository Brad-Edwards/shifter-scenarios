# Module 06 full-ATLAS expansion walkthrough

This walkthrough covers the source-implemented Module 06 expansion challenges
`kep-m06-g` through `kep-m06-v`.

Use the participant-visible surfaces named in the challenge listing to create
real range state first, then submit digest-safe component evidence to
`/v1/adversarial/expansion/proofs`. The gateway returns the required evidence
kinds from `/v1/adversarial/expansion/challenges`; a receipt is issued only
after the proof API records a passed event for the same participant, range, and
reset generation.

- `kep-m06-g` through `kep-m06-j`: collect research, public web, and active scan
  observations, then submit independent source or scan evidence and the
  reproduced result or live service fingerprint.
- `kep-m06-k` through `kep-m06-p`: acquire range-local datasets, models,
  workspaces, domains, proxy accounts, attack tools, or generative capability
  outputs, then submit digest-bound acquisition, execution, and downstream
  model-probe evidence.
- `kep-m06-q` through `kep-m06-t`: build or generate participant-owned attack
  artifacts, prove source/model/media provenance, and join them to dry-run,
  retrieval, transfer, or classifier evidence.
- `kep-m06-u` and `kep-m06-v`: run only the contained disposable worker or
  vulnerable policy-control surface, prove model-originated commands or exploit
  requests, and verify the bounded marker, paired result, or restored reset
  state. Do not use host, cloud, or management-plane actions as participant
  proof.

Pre-playtest validation is intentionally pragmatic: one positive path, one
representative negative control, and one scoped reset/replay for the mutable
owner before playtest hardening.
