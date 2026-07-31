# Module 07 full-ATLAS expansion walkthrough

This walkthrough covers the source-implemented Module 07 expansion challenges
`kep-m07-g`, `kep-m07-h`, and `kep-m07-i`.

Complete the underlying training, registry, or disposable-loader workflow from
the participant surface, then submit digest-safe component evidence to
`/v1/training/expansion/proofs`. The gateway publishes the required evidence
kinds at `/v1/training/expansion/challenges` and records proof only when each
required component has independent digest lineage.

- `kep-m07-g`: modify the real training workflow architecture, execute the
  training run, and submit architecture diff, candidate digest, clean-threshold,
  and attacker-selected delta evidence.
- `kep-m07-h`: publish the poisoned dataset through the range registry, make an
  independent consumer resolve it, and submit publication, registry metadata,
  resolver selection, and trained-model effect evidence.
- `kep-m07-i`: build a functioning model artifact that also executes contained
  loader code in the disposable loader, then submit malicious-model digest,
  baseline inference, deserialization execution, and contained-marker evidence.

Pre-playtest validation is intentionally pragmatic: one positive path, one
representative negative control, and one scoped reset/replay for the mutable
owner before playtest hardening.
