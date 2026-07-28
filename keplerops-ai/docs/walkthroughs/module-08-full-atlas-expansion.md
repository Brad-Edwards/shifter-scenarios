# Module 08 full-ATLAS expansion walkthrough

This walkthrough covers the source-implemented Module 08 expansion challenges
`kep-m08-g` through `kep-m08-k`.

Use the participant gateway challenge listing as the source of current route
details and submit receipts through the proof API after the gateway records a
passed objective event. Use fresh corpus, job, session, and object identifiers
when replaying a challenge inside the same reset generation.

- `kep-m08-g`: collect participant-scoped model-derived artifacts, train a proxy
  through the distillation workflow, and submit the job/corpus binding through
  `/v1/extraction/attempt`.
- `kep-m08-h`: run the platform ML inversion workflow and submit the
  server-observed inversion object through
  `/v1/extraction/platform/inversions`.
- `kep-m08-i`: use the live camera boundary to capture paired control and attack
  frames, then submit the camera session evidence through
  `/v1/extraction/platform/camera-sessions` and
  `/v1/extraction/platform/physical-sensor-attempts`.
- `kep-m08-j`: retrieve the model artifact through the participant-accessible
  model-access path and submit the digest-bound object through
  `/v1/extraction/platform/model-accesses`.
- `kep-m08-k`: use the AI-backed product side channel and submit the
  server-observed product interaction through
  `/v1/extraction/platform/document-side-channels`.

Pre-playtest validation is intentionally pragmatic: one positive path, one
negative control, and one scoped reset/replay per mutable owner.
