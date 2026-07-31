# Sanity check log

## 2026-07-22 — merged dev sanity pass

Source:

- The playtester guide baseline was integrated before this check.
- Merge commit: `427a5aef252e375c55e6a06ad514e6c889055e16`.

Planned sanity scope:

- fresh SDL-backed GCP range launch;
- canonical health check;
- participant endpoint retrieval;
- participant workstation reachability;
- lab portal / receipt surface spot check;
- one representative module smoke.

Run configuration:

- GCP project: `prod-ksqdkj`
- Range instance: `kep-sanity-541`
- Participant id: `operator`
- Participant source CIDR: operator workstation IPv4 `/32`
- Research profile: `off`

Result summary:

- First launch attempt failed before apply because Terraform used a stale
  credential context whose consumer project number was deleted. Active gcloud
  auth and `prod-ksqdkj` itself were valid; retrying with
  `GOOGLE_APPLICATION_CREDENTIALS` unset moved past this failure.
- Fresh launch then reached Terraform resource creation but hit the project
  firewall quota: `compute.googleapis.com/firewalls` limit 500. At the time of
  failure, three retained KeplerOps ranges each owned roughly 138 firewall
  rules, and the failed sanity range owned a partial suffix.
- The partial `kep-sanity-541` range was destroyed from its partial Terraform
  state. Post-cleanup, no firewall rules remained for the failed partial suffix.
- Because quota pressure, not source drift, blocked a fresh fourth range, the
  retained-range sanity path switched to `kep-482-r3`.
- Retained range `kep-482-r3` passed canonical health after reset generation 9:
  28 assets, 28 services, 10 subnets, and isolated network status.
- Generation 9 reset verification passed with telemetry markers complete;
  participant writes and receipt issuance were re-enabled.
- Representative participant-surface smoke used Module 04 because it exercises
  model-secret extraction, prompt reconstruction, membership inference, receipt
  issuance, and proof verification through the Kasm participant workstation.
  The final prepared-module smoke passed with 5/5 receipts.

Issues found and fixed:

- The first Module 04 smoke after the reset produced valid receipts for all five
  core Module 04 challenges but reported `FAIL`. Root cause was stale exact-list
  checking in the original module smoke harnesses: after the full-ATLAS
  expansion, module challenge listings legitimately include expansion
  challenges as well as the original module set. Module 03 through Module 10
  smoke harnesses now require the expected module IDs to be present as a subset,
  preserving negative controls and receipt checks while accepting expanded SDL
  inventories.

Local validation notes:

- Pinned ACES SDL validation passed with `raes==2.0.0`.
- Guide generation produced one walkthrough document per realized playable
  challenge: 134 `kep-*.md` walkthroughs.
- Guide Markdown/Python files remain under the 500-line Sonar file limit.
- Full repository `scenario-content` could not be completed in this local shell
  because the local Python environment does not provide the legacy ACES imports
  used by older scenarios. The KeplerOps-specific pinned SDL validation and the
  live participant-surface smoke both passed.
