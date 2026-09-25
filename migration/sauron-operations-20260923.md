# Sauron operations change log

Started: 2026-09-23 UTC.

## Authorized scope

- Get the Sauron tenant on the sauron branch running the private Polaris scenario.
- Support 30 independent participant ranges within the user's 12-hour deadline.
- Exercise launch from Shifter CTF, complete manual participant QA, and verify teardown.
- Track every change here. Do not create a PR to origin/dev.
- Leave the other agent's Nazgul tenant and work unchanged.
- Do not access /home/atomik/.secrets or ~/.secrets.
- Private repository authentication uses SHIFTER_GITHUB_PERSONAL_ACCESS_TOKEN; core uses GITHUB_PERSONAL_ACCESS_TOKEN. Never record values.

## Initial state

- Core checkout: /home/atomik/src/shifter, sauron, cbbd71374.
- Existing untracked .claude/worktrees/ and platform/terraform/gcp/global/github-runner/tfplan preserved.
- Private checkout: /home/atomik/src/shifter-scenarios-panw, main, with existing unrelated cinder-typhoon edits preserved.
- Sauron is GCP; AWS tenant skill inspected but not applied.
- Current kubectl default points to Nazgul. All cluster commands must specify the Sauron context explicitly.
- Sauron overlay references project prod-qjpjnv; live identity still to be verified.

## Changes

1. Created this private local operations directory and change log under /tmp, outside the public repository. No tenant or repository changes yet.
2. Added operator.cjs to this directory for normal browser login and adapter inventory. Reads only the Sauron gitignored bootstrap overlay; stores any session/MFA material privately with mode 0600. Initial browser failed on missing libraries; using existing local browser libraries for retry.
3. Requested creation of temporary Sauron qualification VM polaris-sauron-qualify-20260923 from immutable existing scenario machine image shifter-polaris-host-20260923a in prod-hwmvjy. Source is read-only; new VM is in prod-qjpjnv on image-build subnet, no public IP, no service account/scopes. This stages a tenant-owned image without changing Nazgul. Creation result pending.
4. Requested tenant-owned directory image polaris-sauron-dc-20260923 in prod-qjpjnv as a copy of shifter-polaris-dc-1789943829 from prod-hwmvjy. Pending image ID 8280710667835466951.
5. Qualification VM is RUNNING at private IP 10.201.0.6 with no service account. Started management SSH verification through IAP; gcloud may add its standard operator SSH public key to the temporary qualification VM.
6. Local browser libraries proved insufficient. Running browser helper in the existing Playwright container, with only the specific Sauron overlay, helper directory and JS dependencies mounted.
7. Successfully logged in through Sauron's normal Identity Platform login and completed first operator TOTP enrollment. Recovery seed is in the owner-only operations directory (not this log); must retain in approved secret storage before cleanup. Browser session saved owner-only. Adapter inventory confirms none installed.
8. Directory image copy is READY. Host cold boot passed management SSH on 2222; all 17 scenario containers running, DNS public resolution succeeds, pinned client version is 2.1.108, readiness document SHA-256 is b63847b7937e939f1901583a5775f1e50767ce92a22847139f63fd0520ffa8ae.

## Current findings

- Sauron has no model broker deployment or model invocation service account visible. Need configure the deployment-managed broker before full participant model QA.

## Model broker and installation changes

9. Added core platform/deploy/gcp/sauron/model-broker-overlay.template.json, derived from the existing deployment template with Sauron identities and a distinct catalog deployment UUID. Enables the existing broker, logical coding model aliases, 4 concurrent requests, 120 requests/minute and USD 50 deployment spend ceiling for initial qualification. Render and broker schema validation passed.
10. Stored operator TOTP recovery in GCP Secret Manager sauron-operator-totp version 1, project prod-qjpjnv. No secret value recorded here.
11. Added browser.sh/admin.cjs and immutable adapter manifest to local operations directory. Submitted adapter 0.1.14 installation through Sauron UI using the existing private-registry read credential; readiness pending.
12. Removed the operator SSH key from the temporary host guest and instance metadata, then requested shutdown before clean image capture. Source image was not changed.
13. Full required ADR CI check ran and failed only on two pre-existing unrelated untracked .claude/worktrees/.../aptl-lilrae-techvault-identity-preflight-2062.md files. Those user files remain untouched. Targeted checks will separately cover this change.
14. Targeted ADR check and git diff whitespace check passed. Committed broker overlay directly on sauron as b2e82d681 (fix(sauron): enable deployment-managed model access broker); push to origin/sauron requested. No PR created.
15. Set Sauron GitHub Environment variable GCP_RANGE_PRIVATE_GOOGLE_ACCESS from true to false to select broker-only range model access, as required by the private runbook.
16. Rebuilt the private environment pack with its existing pinned build environment. Canonical digest sha256:df8841c3b51f68a123d66270db493de308e7d8bc4180380bbca7fcf5be87af57, local polaris.tar. Initial system Python lacked raes; build succeeded with /tmp/rpack-venv/bin/python.
17. Adapter 0.1.14 reached READY. Polaris pack installed successfully through the UI in organization 181a3621-fb74-43af-9c23-874db816a22c (Personal).
18. Push confirmed. Dispatched Sauron deployment 35820276973 at b2e82d681ab76acd63b7804e4df92dabd1781d46; in progress. No PR created.
19. Stopped the temporary qualification host explicitly after guest shutdown did not promptly change cloud state. Removed validation tag before image capture.
- Operator is a tenant administrator but CTF organizer access is not yet enabled; resolving through administration UI/API.
20. Granted CTF Organizer to the existing tenant administrator (user 3) through POST /api/v1/administer/users/3/grant-organizer/. Readback confirms local organizer grant. Event creation UI now loads and lists installed Polaris scenario pack-4cba2af821475743866744428e72b482.
21. Requested clean host machine image polaris-sauron-host-20260923 from stopped Sauron qualification VM. No service account or tags remained at capture.
22. Deployment 35820276973 failed its dependency vulnerability gate before tenant deploy. Downloaded sanitized scan artifact to local operations directory. Requested cancellation of remaining checks; fetching/merging origin/dev into sauron under standing authorization to incorporate already-landed security/runtime fixes. No changes to dev or Nazgul requested.
23. Scan finding: Autobahn 25.12.2 / CVE-2026-77528. Merged origin/dev into sauron without conflicts as 02edeb57ea8d4cae58f89b10c07695d12cb813da; pushed only sauron. Dispatched replacement deployment 35820484048, confirmed it uses that merge SHA. No PR created.
24. Host image polaris-sauron-host-20260923 is READY, ID 4184902143517320498, with no service account or validation tags. Saved adapter assignment through tenant UI: host machine image, directory normal image, management transports, participant container and readiness digest, coding-main/coding-small and 8192 output token limit.
25. Created draft CTF a25f2d53-6849-4e13-9421-696ac9a29699 through the event UI: Polaris — Graphite Raven Qualification, max participants 1, private scoreboard/registration, 45-minute spin-up, UTC 05:58–14:58 on 2026-09-23, automatic cleanup one hour after end. Workspace 1f7ee6da-abd9-4655-96a4-5e46c0931e95.
26. Exported private challenge pack with 38 entries to owner-scoped operations directory and requested import through CTF UI. Requested GraphiteRaven participant with non-deliverable placeholder email.
27. Both bounded model probes in prod-qjpjnv returned HTTP 404 (project lacks publisher model access). Asked user to enable Sonnet 4.6 and Haiku 4.5 in Model Garden, including accepting publisher terms, or specify already-enabled project. No terms accepted on user's behalf.
28. Import-linter: all 9 contracts passed after merge. actionlint passed. Full ADR check again failed only on the same two unrelated untracked worktree documents.
29. Created GraphiteRaven participant 7b78f69d-4862-43be-999d-7b391614a5d4, registered. Issued its initial password through the participant UI; kept credential files owner-only. No login email sent.
30. Imported exactly 38 challenges, zero errors, via CTF challenge-import UI. Large import dialog did not admit the pointer click; keyboard Enter on its enabled Import button succeeded. No challenge values stored in this log.
31. Local tflint recursive passed. kube-linter passed; kubeconform validated 49 resources, skipped 1, invalid/errors 0. Deployment 35820484048 had 104/106 checks complete without failures at last readback.
32. Durable private copy of this log created at migration/sauron-operations-20260923.md in the scenario repository. This is private operational evidence, not a core/public repository artifact.
33. Participant login is correctly denied while event is draft (live-participation requires active/paused); defer login until activation. Automatic participant-account provisioning attempted before model setup and currently reports error with no range instance assigned; recover through CTF once deployment/model setup is ready.
34. Prepared participant-terminal.cjs and owner-only 38-challenge QA contract. The terminal driver will recover answers from the unprivileged participant surface, validate recovery digests and gates, and only submit answers after all 38 recoveries pass. Not executed against a live range yet.
35. User confirmed both publisher models enabled in prod-qjpjnv. Rechecking bounded live model invocations and configuring tenant sources/event aliases.
36. Confirmed both Sonnet 4.6 and Haiku 4.5 now return HTTP 200 with 5 output tokens each from bounded project-access probes. These are project-enablement checks, not yet participant/broker acceptance.
37. Created tenant source records Sauron Vertex Claude Sonnet and Sauron Vertex Claude Haiku. Event source assignment currently returns HTTP 400 while the deployed model catalog remains disabled; retry after successful broker-enabled deployment. No participant model QA has run yet.
38. Private pack tests passed: 4/4. Prepared migration/sauron-roster-20260923.csv in private repository with 30 proposed codenames. Only GraphiteRaven is registered; remaining 29 remain planned until the first CTF range qualifies.
39. PostgreSQL platform suite passed in replacement deployment; remaining platform job reached Redis channel-layer integration tests. Captured images remain READY; temporary image-source VM remains stopped. No live participant VM has been created yet.

40. Replacement deployment passed all test and quality gates and entered GCP release preparation. Corrected the local participant QA helper to read browser Fetch Response.ok as a property before challenge submissions; live QA remains pending.

41. Fresh GCP readback confirms both captured images READY. Deployment Terraform apply created the invocation identity and is replacing web/worker/plugin node pools because the merged dev configuration explicitly assigns their primary pod range; background workers temporarily Pending during replacement. No participant range exists yet.

42. Updated prepared acceptance helper to submit recovered answers with the participant UI's Submit flag controls, not direct mutation calls. It still requires all 38 recovery digests and five gate checks before any submission and saves sanitized progress after each accepted answer. No live QA executed yet.

43. User requested a broker-cap decision and a stop. Requested cancellation of deployment run 35820484048 while it was building the provisioner image, before release scan and deployment. Terraform had already reconciled node pools and created the model invocation identity; no broker or new application release had been rolled out at the time of cancellation. No cap or source settings were changed after this request.

## Verification and blockers

- Local credential presence checks passed for both required GitHub tokens, without reading values.
- Initial GitHub, kubectl and HTTP requests hit sandbox network/credential-cache restrictions. Retrying with required escalation.
- Capacity requirement confirmed by user: 30 independent ranges.
- User clarified: 30 generic placeholder participants with fun two-word Polaris codenames; start by proving ONE range in a CTF. First QA participant: GraphiteRaven.
- GitHub access now verified for core and private scenario repository. Latest Sauron deployment 35551403302 succeeded at cbbd7137495eab16adbeec51afcb8c640b5dc1b5.
- Live Sauron cluster in prod-qjpjnv responds; platform pods are running and portal /health/ returns HTTP 200.
