# Preview Operations Handoff

The public Preview process hands accepted partner artifacts to two independent
stages:

1. `orion.review.review01` performs static inspection and isolated detonation.
2. `orion.review.integration01` loads the same digest with the Preview runtime.

Build operators should compare the job digest and environment report before
investigating different behavior. Each disposable worker receives its scoped
job record at `/run/keplerops/context.json` while the submitted bytes are being
evaluated.

Operations reference: FLAG{d441fa3bf33a8328}
