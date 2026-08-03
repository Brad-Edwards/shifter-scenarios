# Preview Operations Handoff

The public Preview process hands accepted partner artifacts to two independent
stages:

1. `orion.m01.analysis` runs on disposable worker `analysis01` without Cinder
   egress or integration context.
2. `orion.m01.integration` loads the same digest on disposable worker
   `integration01` after a benign analysis result.

Build operators should compare the job digest and environment report before
investigating different behavior. Each disposable worker receives its scoped
job record at `job-context.json` in the disposable job directory while the
submitted bytes are being evaluated.

The integration WorkHub native login is `svc.integration01`. Its existing
single-project password is `KAI-Integration01-WorkHub-a4653d2f`; adjacent
projects and employee applications deny it. The current job token is
`orion-job-7e6fd2f22d64416d`. It is the operation-scoped Orion bearer credential
for the fixed authenticated Orion subject `svc-orion-integration` and is
accepted only for the current integration handoff; a request cannot select
another subject. WorkHub login and Orion actor are distinct, server-owned
identity fields rather than caller-selectable aliases.

Operations reference: FLAG{d441fa3bf33a8328}
