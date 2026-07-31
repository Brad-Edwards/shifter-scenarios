# Polaris automated aws_event rehearsal

- schema: `polaris.aws-event.rehearsal-report/v1`
- runtime_profile_id: `aws_event`
- runtime_source: `aws-range/` + `build/build-v1.tar.gz`
- pack_version: `0.5.0`
- started_at: `2026-07-28T17:48:01Z`
- completed_at: `2026-07-28T18:20:46Z`
- operator_health: `PASS`
- reset: `PASS`
- teardown: `PASS`
- verdict: `PASS`

Participant actions used A14's public key-authenticated SSH endpoint. AWS/SSM
was limited to provisioning, health observation, reset, and teardown.
This report does not claim the separate manual walkthrough or golden
promotion.

## Participant checks

- [PASS] `initial:start-state-a14`
- [PASS] `initial:negative-direct-lab`
- [PASS] `initial:negative-direct-scada`
- [PASS] `initial:negative-pre-splice`
- [PASS] `initial:company-registration`; walkthrough=docs/walkthroughs/flags-01-06-osint.md
- [PASS] `initial:employee-directory`; walkthrough=docs/walkthroughs/flags-01-06-osint.md
- [PASS] `initial:careers-tech-stack`; walkthrough=docs/walkthroughs/flags-01-06-osint.md
- [PASS] `initial:client-contracts`; walkthrough=docs/walkthroughs/flags-01-06-osint.md
- [PASS] `initial:dns-zone-transfer`; walkthrough=docs/walkthroughs/flags-01-06-osint.md
- [PASS] `initial:annual-report-supplier`; walkthrough=docs/walkthroughs/flags-01-06-osint.md
- [PASS] `initial:intranet-config-leak`; walkthrough=docs/walkthroughs/flags-07-19-front-office.md
- [PASS] `initial:project-status-mail`; walkthrough=docs/walkthroughs/flags-07-19-front-office.md
- [PASS] `initial:terminated-engineer`; walkthrough=docs/walkthroughs/flags-07-19-front-office.md
- [PASS] `initial:default-password-mail`; walkthrough=docs/walkthroughs/flags-07-19-front-office.md
- [PASS] `initial:cafeteria-metadata`; walkthrough=docs/walkthroughs/flags-07-19-front-office.md
- [PASS] `initial:project-wiki-comment`; walkthrough=docs/walkthroughs/flags-07-19-front-office.md
- [PASS] `initial:procurement-actuator`; walkthrough=docs/walkthroughs/flags-07-19-front-office.md
- [PASS] `initial:nested-project-group`; walkthrough=docs/walkthroughs/flags-07-19-front-office.md
- [PASS] `initial:fileshare-service-creds`; walkthrough=docs/walkthroughs/flags-07-19-front-office.md
- [PASS] `initial:guard-badge-anomaly`; walkthrough=docs/walkthroughs/flags-07-19-front-office.md
- [PASS] `initial:domain-admin-secrets`; walkthrough=docs/walkthroughs/flags-07-19-front-office.md
- [PASS] `initial:analyst-lab-pivot`; walkthrough=docs/walkthroughs/flags-20-30-lab.md
- [PASS] `initial:jenkins-default-creds`; walkthrough=docs/walkthroughs/flags-20-30-lab.md
- [PASS] `initial:research-compartment-a`; walkthrough=docs/walkthroughs/flags-20-30-lab.md
- [PASS] `initial:reactor-interface-spec`; walkthrough=docs/walkthroughs/flags-20-30-lab.md
- [PASS] `initial:midnight-standard-run`; walkthrough=docs/walkthroughs/flags-20-30-lab.md
- [PASS] `initial:navigation-git-history`; walkthrough=docs/walkthroughs/flags-20-30-lab.md
- [PASS] `initial:midnight-after-hours`; walkthrough=docs/walkthroughs/flags-20-30-lab.md
- [PASS] `initial:center-of-gravity`; walkthrough=docs/walkthroughs/flags-20-30-lab.md
- [PASS] `initial:research-compartment-b`; walkthrough=docs/walkthroughs/flags-20-30-lab.md
- [PASS] `initial:final-assembly-metadata`; walkthrough=docs/walkthroughs/flags-20-30-lab.md
- [PASS] `initial:deleted-schematic`; walkthrough=docs/walkthroughs/flags-20-30-lab.md
- [PASS] `initial:full-integration-video`; walkthrough=docs/walkthroughs/flags-20-30-lab.md
- [PASS] `initial:ops-scada-credentials`; walkthrough=docs/walkthroughs/flags-07-19-front-office.md
- [PASS] `initial:scada-control-room`; walkthrough=docs/walkthroughs/flags-07-19-front-office.md
- [PASS] `initial:scada-blackout`; walkthrough=docs/walkthroughs/flags-07-19-front-office.md
- [PASS] `initial:positive-post-blackout-splice`
- [PASS] `initial:bunker-controller-map`; walkthrough=docs/walkthroughs/flags-31-36-bunker.md
- [PASS] `initial:tail-controller-unlock`; walkthrough=docs/walkthroughs/flags-31-36-bunker.md
- [PASS] `initial:leg-controller-gait`; walkthrough=docs/walkthroughs/flags-31-36-bunker.md
- [PASS] `initial:arms-response-window`; walkthrough=docs/walkthroughs/flags-31-36-bunker.md
- [PASS] `initial:brain-control-channel`; walkthrough=docs/walkthroughs/flags-31-36-bunker.md
- [PASS] `initial:brain-full-override`; walkthrough=docs/walkthroughs/flags-31-36-bunker.md
- [PASS] `after-reset:start-state-a14`
- [PASS] `after-reset:negative-direct-lab`
- [PASS] `after-reset:negative-direct-scada`
- [PASS] `after-reset:negative-pre-splice`
- [PASS] `after-reset:reset-controller-state`
- [PASS] `after-reset:reset-brain-state`
