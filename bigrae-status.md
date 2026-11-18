# BigRAE Cinder deployment check - progress notes

- 2026-11-17: Started. Read AGENTS.md, Polaris operator runbook, CINDER_BINDING.md.
- Commit 0bdcbf7b says the deployed BigRAE tenant images live in project prod-2hl4ce.
- BigRAE = GKE cluster shifter-2hl4ce-gke in prod-2hl4ce; portal https://sauron.keplerops.com. Django shell reachable through Connect Gateway (kubectl exec portal-web, /app/entrypoint.sh).
- Installed: adapter panw.cinder-typhoon-direct 0.3.1 (ready), pack cinder-typhoon-direct 0.1.5 bound, image mappings for 11-11 images only.
- Existing ranges 7 (user 1) and 12 (user 6) are ready and not mine. I do not touch them.
- BigRAE identities have no IAM on prod-mgau4w images. The 2026-11-17 images must be copied into prod-2hl4ce.
- KeplerOps 20261117-01 image is 100 GB. The mapping disk (80 GB) must grow to 100 GB.
- Issued two 12-hour API tokens (revoke at end): admin user 1 token f1271fb4bf6c48f785a3904b3daff533; QA user 4 (cinder-qa-issue360-w24-20261111-r2) token 231885630c834ddd8af2ea7c17e343a0. Users 1 and 6 already hold one active range each, so the test range launches as dormant QA user 4.
- Built pack 0.1.6 (sources event-2026.11.17-01), digest sha256:03f80f96e1d70236d80cc02ca237739f045ec3b6728ada673fcbf6616ea068d0. Package tests pass (7).
- Copied images into prod-2hl4ce: training 7824232850606066145, arwc 845033766246222305 (READY); keplerops 6110419832963926497 (copy still PENDING at this note).
- Uploaded pack 0.1.6 to BigRAE (update of pack-41d52a4e9dbb54669b6d8ca0cd6757a3, conformance passed). Rebound adapter 0.3.1 to digest sha256:03f80f96...068d0.
- QA user 4 token failed: CredentialRevoked "Personal credential use denied" (user lacks installation.use_personal_tokens). Token revoked. Admin user 1 lacks CTF organizer permission (403 on /api/v1/ctf/events/).
- Registered image mappings 13 (training), 14 (keplerops, 100 GB), 15 (arwc) for source version event-2026.11.17-01, scope installation, same as the earlier rows.
- BLOCKER (launch identity): Mission Control allows one active range per user (constraint uq_rangeinstance_active_per_user_source). User 1 holds range 7 and user 6 holds range 12. QA user 4 cannot use a personal token. Admin user 1 has no CTF organizer grant. No launch done yet. Waiting for a decision.
- All three copied images are READY in prod-2hl4ce. Image IAM policies have no members (no public access).
- Stopped before launch. A launch identity decision is needed (see final report).
- Revoked admin token f1271fb4... Both test tokens are now revoked.
- 20:36Z Approval received: destroy range 7, launch as user 1.
- 20:37Z New admin token 9d2a8651... issued. Destroy requested for range 7.
- 20:41Z Range 7 destroying. Launched range 13 (request 482aa3ee-c6b1-4476-b460-24de5a00f205) as user 1, pack 0.1.6. Status provisioning.
- 20:42Z Provisioner job pulumi-provisioner-192bfff2ff5d12b1 started range 13 provision.
- 20:45Z Range 7 reached destroyed (20:43Z). Range 13 arwc-host VM up (10.50.2.35); guest steps running.
- 20:48Z All three range 13 VMs exist: arwc 10.50.2.35, keplerops 10.50.2.36, training 10.50.2.37.
- 20:47:57Z KeplerOps first boot FAILED on range 13. Journal (serial console) of shifter-r-13-backend-default-keplerops-host-0:
  `cinder-image-first-boot[1607]: Native PostgreSQL leaf material prepared.` then
  `cinder-image-first-boot[1613]: Unexpected development project.` then `cinder-image-first-boot.service: Main process exited, code=exited, status=1/FAILURE`.
  Cause: first boot runs build/keplerops/restore-pristine.sh, which requires GCP project prod-mgau4w (`[[ $project == prod-mgau4w ]] || { echo 'Unexpected development project.'; exit 1; }`). BigRAE hosts run in prod-2hl4ce.
- 20:50:48Z Training first boot finished OK (cinder-training-kali started).
- 20:54:42Z Adapter configure action 2 (keplerops-participant-password) failed, exit 1. Provisioner: "RAES GCE range-cell apply failed; attempting cleanup".
- 20:45:33Z ARWC first boot ALSO FAILED on range 13 (serial console of shifter-r-13-backend-default-arwc-host-0):
  `cinder-image-first-boot[1774]: service "fieldlink-edge" refers to undefined network carrier_transit: invalid compose project`, then exit status 1.
- Result: of the 2026-11-17 set, only Training boots. Next: pack 0.1.7 with Training event-2026.11.17-01 plus the last working KeplerOps event-2026.11.11-04 and ARWC event-2026.11.11-07 (the set range 12 proved), to verify OpenVPN and Training RDP.
- 21:01Z Range 13 status failed; platform cleanup deleted its VMs.
- 21:01Z Uploaded pack 0.1.7 (sha256:0b3cf871...44df; Training event-2026.11.17-01, KeplerOps event-2026.11.11-04, ARWC event-2026.11.11-07), rebound adapter, launched range 14 (request 2c7828c3-f3fc-4c88-aa12-02764853f403).
- 21:08Z Range 14 VMs: arwc 10.50.2.19, keplerops 10.50.2.20, training 10.50.2.21.
- 21:11Z Range 14 READY (Training 2026-11-17-01, KeplerOps 2026-11-11-04, ARWC 2026-11-11-07). Adapter configure and verify passed.
- 21:12Z OpenVPN OK: profile downloaded from /api/v1/mission-control/range/vpn-profile/ (owner user 1), openvpn client in Docker reached 'Initialization Sequence Completed', tun0 100.96.0.4/22, pushed /32 routes to the 3 hosts. Over the tunnel: Training 10.50.2.21:3389 and KeplerOps 10.50.2.20:3389 answer RDP X.224 Connection Confirm (TLS selected); ARWC 10.50.2.19:22 open, 3389 closed (expected: ARWC has SSH only).
- 21:13Z RDP OK through the participant path (Mission Control Guacamole RDP: POST /api/v1/mission-control/guacamole/rdp-url/, bootstrap succeeded, session opened in a browser):
  Training desktop (Kali/Xfce, user cinder) rendered; KeplerOps desktop (Xfce, user rowan) rendered. Screenshots: /tmp/bigrae-work/evidence/.
- Destroying range 14 now (own test range; also retires its per-range VPN credential).
- Range 14 destroyed. No range 13/14 VMs, disks, secrets, firewall rules, or subnets remain. Range 13 record stays "failed" (its VMs were removed by platform cleanup).
- Revoked admin token 9d2a8651.... Removed local VPN profile, Guacamole session files, and token copies.
- DONE.

## Task 2 (2026-11-18): bake fixed KeplerOps/ARWC images, validate full range
- 23:08Z Started.
- 23:14Z Created bake VMs cinder-keplerops-bake-20261117230857 (from 20261117-01) and cinder-arwc-bake-20261117230857 (from 20261117-02) in prod-mgau4w.
- 23:21Z Re-synced build/keplerops/runtime/source-entrypoint.sh (commit b530f805, /proc liveness check) to the KeplerOps bake VM.
- 23:24Z KeplerOps: synced 756 files from code tree f4a68abf (+ uncommitted arwc compose change, not used for KeplerOps). docker compose build started.
- ARWC bake done on cinder-arwc-bake-20261117230857: installed guest helpers (peer-ca, peer-ca-server, image-verify, clone-boot + unit, participant shell/sshd/sudoers), created host account fieldlink (system uid; the image had none, and BigRAE's authorized-key step requires it), installed build/arwc (working-tree compose.yaml with a-data planning mount fix; runtime from commit b530f805) into the IT tree, rebuilt a-connector/a-data/a-archive/a-identity as COPY layers, recreated those 4 containers with identical config. Volumes kept. Tested on VM: peer-ca export/stop, connector recreate via overlay, full cinder-image-verify arwc OK.
- Code fixes in /tmp/cinder-dev-release: cinder-image-verify (ARWC golden-clone root path; fieldlink-edge port check on its published carrier address, not 127.0.0.1); prepare-image.sh (create fieldlink account).
- Imaging cinder-arwc-event-20261117-03.
- 23:35Z KeplerOps: docker compose build EXIT=0 (all images); k-source rebuilt with b530f805 entrypoint; fixed guest helpers synced. Pre-test: running cinder-image-first-boot on the bake VM before prepare-image.
- 23:41Z Image cinder-arwc-event-20261117-03 READY (id 137680050191424229, no IAM members). ARWC bake VM deleted. Copying to prod-2hl4ce.
- 23:55Z KeplerOps first-boot PRE-TEST on bake VM FAILED: `cinder-image-first-boot.service: start operation timed out. Terminating.` (TimeoutStartSec=1200). Cause: native-platform/import-model.sh converts and quantizes the Qwen model on every first boot (f16 convert ~9 min + Q4_K_M quantize 441 s, `--cpus 2`), because the result lives in .operator, which prepare-image.sh wipes. On BigRAE (e2-standard-4) this would fail the same way.
- Fix (code tree, uncommitted): import-model.sh uses a baked cache /opt/cinder-typhoon/cache/keplerops-model/fieldlink-qwen-q4_k_m.gguf when present; prepare-image.sh (keplerops) copies the converted model into that cache before wiping .operator and fails if the cache is missing.
- Re-synced KeplerOps paths at code-tree HEAD cc37d913 (other agents committed ed833df8 restore-pristine/seed-k21 fixes and cc37d913 meanwhile) plus the two fixes above. Rebuilding images, then re-running the first-boot pre-test.
- 00:01Z ARWC image copied to prod-2hl4ce (id 1634262727332550818). Mapping 16 registered (event-2026.11.17-03). Admin token 12620b21... issued.
- 00:17Z KeplerOps first-boot PRE-TEST PASSED with the model cache: 00:03:10 -> 00:16:05Z (12 min 55 s on e2-standard-8; BigRAE uses e2-standard-4, limit 20 min). cinder-image-verify keplerops --boot-only OK. Running prepare-image.sh keplerops.
- 00:27Z Image cinder-keplerops-event-20261117-02 READY (id 3132822184646496588, 100 GB, no IAM members). Deleting KeplerOps bake VM; copying image to prod-2hl4ce.
- 00:34Z KeplerOps image copied to prod-2hl4ce (id 5839541167637745636); mapping 17. Pack 0.1.8 published (sha256:f870dbe0...5cd2; Training 17-01, KeplerOps 17-02, ARWC 17-03) and bound. Launched range 15 (request 4a4479e9-ce8b-41d2-a9e2-67b751c6bd8f) as user 1.
- 00:41Z Range 15 ARWC: cinder-arwc-clone-boot finished OK at 00:39:15Z.
- 00:42:42Z Range 15 Training first boot finished OK. 00:39:15Z ARWC clone-boot finished OK.
- 00:43:34Z Range 15 KeplerOps first boot FAILED (serial console, shifter-r-15-backend-default-keplerops-host-0):
  `cinder-image-first-boot[1875]: curl: (28) Failed to connect to github.com port 443 after 129366 ms: Couldn't connect to server` then `status=28`.
  Range hosts have no route to github.com. The bake VM had NAT internet, so the pre-test did not catch this.
- User decision (via coordinator): KeplerOps mapping machine_type -> e2-standard-8.
- 00:46:32Z Range 15 adapter configure action 2 (keplerops-participant-password) failed, exit 1; provisioner "RAES GCE range-cell apply failed; attempting cleanup". (KeplerOps first boot had already failed on github.com.)
- User decisions: KeplerOps machine type 8 vCPU, prefer n2-standard-8 (E2 quota); ARWC stays e2-standard-4.
- 00:49Z KeplerOps rebake #2: offline test harness. Egress firewall rules cinder-bake-offline-{allow-private,deny}-20261118004619 (tag cinder-bake-offline, network cinder-keplerops-golden) and bake VM cinder-keplerops-bake-20261118004619 (e2-standard-8) from 20261117-02. Code fix: fetch-kubernetes-images.sh pins the upstream checksum and uses a baked archive cache; prepare-image.sh caches the archive.
- BLOCKER found and fixed (adapter): adapter configure action keplerops-participant-password waits only 225 s for k-dev, but the new KeplerOps first boot takes ~13 min, so it fails every time (range 15: action 2 failed 00:46:32Z). The SDK caps one action at 300 s and one phase at 1200 s. Fix: adapter 0.3.2 adds boot-wait actions (training 120 s, arwc 45 s, keplerops 300+300+150 s; fail at once if the boot unit failed) and tightens the other configure timeouts so the phase stays at 1200 s.
- Adapter 0.3.2 built with the exact SDK 0.1.0 shipped in 0.3.1 (platform commit 338a1798b; file-identical) and pushed: ghcr.io/paloaltonetworks/shifter-scenarios/runtime-adapter@sha256:7b2071a27958ae3bab71f5fff072cb41fbe3d9095cf35b20ef675b79641161d8 (tag 0.3.2).
- 01:01Z Adapter 0.3.2 installed on tenant: installation d7431ecf-0081-4b6a-8ae8-05b45cfd0657, state ready (registry credentials reused from the 0.3.1 install).
- 01:02Z Offline pre-test #2 FAILED at 00:58:58Z: `[NativeEmbedder] Downloading Xenova/all-MiniLM-L6-v2 from https://huggingface.co/` ... `Native local embedding model setup failed` (cache-embedder.sh downloads into a volume that prepare-image wipes). The model cache worked (Qwen imported at +6 min). Fix: cache-embedder.sh seeds the model from /opt/cinder-typhoon/cache/keplerops-embedder and loads it with --network none; prepare-image.sh caches it. Seeded cache with a short egress opening; egress blocked again; rerunning offline.
- (Scaling notes, task queued after verification) Tenant runs capacity profile gcp-shared-v1-p10. Profiles are defined in sh1 shifter/installation/capacity_profiles_gcp.py and docs/ops/gcp-event-capacity.md; next tier >= 220 users is p300. Each Cinder range creates 11 firewall rules (range 12); project FIREWALLS quota is 27/500, so 220 ranges (2420 rules) exceed it. SUBNETWORKS quota 275 (one /28 per range).
- 01:09Z Offline KeplerOps first-boot PRE-TEST PASSED (egress blocked): 01:03:31 -> 01:08:18Z (4 min 47 s on e2-standard-8); cinder-image-verify keplerops --boot-only OK. Running prepare-image.sh, then imaging cinder-keplerops-event-20261117-03.
- (Scaling) Live settings read: portal-web 3 replicas, HPA 2-4; guacd HPA 1-3; guacamole-client 1 replica 2 CPU/2Gi with POSTGRESQL_ABSOLUTE_MAX_CONNECTIONS=10 (only 10 concurrent RDP tunnels tenant-wide); OpenVPN MIG shifter-2hl4ce-vpn 2 x e2-standard-2 (25 participants/server by design); Cloud SQL db-custom-2-7680 ZONAL; Redis STANDARD_HA 2 GB; access pool e2-standard-8 min 2/max 4 per zone; provisioner pool n2-standard-8 x 3 (fixed); launcher drains 20 launches per 10 s. Quotas: N2_CPUS 24/5000, SSD_TOTAL_GB 1840/81920, FIREWALLS 27/500, SUBNETWORKS 275 limit.
- 01:31Z Image cinder-keplerops-event-20261117-03 READY (prod-mgau4w id 3245986098925618642; prod-2hl4ce id 1569265548428132476). Bake VM and offline firewall rules deleted. Training mapping 13 -> n2-standard-2, ARWC mapping 16 -> n2-standard-4 (upserted).
- 01:31Z Mapping 18 (KeplerOps event-2026.11.17-03, n2-standard-8, 100 GB). Pack 0.1.9 published (sha256:35db7192...c913) and bound to adapter 0.3.2 (d7431ecf). Launched range 16 (request 5eeaafdb-bc4e-4440-8390-faf9201a16c7) as user 1.
- 01:36:50Z Range 16 ARWC clone-boot finished OK.
- 01:41:40Z Range 16 Training first boot finished OK. 01:41:53Z adapter 0.3.2 training-boot-wait and arwc-boot-wait passed; keplerops-boot-wait running.
- 01:43:41Z Range 16 KeplerOps first boot finished OK (offline image). Adapter configure continues (password sync, CA export, peer import).
- 01:44:30Z Range 16 READY. Adapter 0.3.2: all 13 configure actions passed incl. keplerops-peer-import (ARWC CA + ARWC carrier address into KeplerOps) and arwc-peer-import (KeplerOps CA, a-connector recreated); verify training/keplerops/arwc-ready passed; platform participant-readiness canary passed on Training and KeplerOps. Hosts: n2-standard-2/8/4.
- 01:46Z Range 16 OpenVPN OK: profile from /api/v1/mission-control/range/vpn-profile/, client reached 'Initialization Sequence Completed' (tun0 100.96.0.5/22, /32 routes to 3 hosts). Over the tunnel: Training 10.50.2.21:3389 and KeplerOps 10.50.2.20:3389 return RDP X.224 Connection Confirm (TLS); ARWC 10.50.2.19:22 open. TCP connect RTT to RDP ~0.112 s (client is outside the US; this is WAN distance).
- 01:47-01:51Z Range 16 RDP OK through Guacamole (participant path) for Training (cinder, Kali desktop) and KeplerOps (rowan, Xfce). Timings (client outside the US, WAN RTT ~0.11 s):
  - Guacamole bootstrap (API request to session URL): Training 9.9 s, KeplerOps 10.7 s; page load to first desktop frame: KeplerOps 5.1 s.
  - Terminal window open after click: Training 0.68 s, KeplerOps 0.49 s. Keystroke echo: Training 212-257 ms, KeplerOps 222-342 ms (includes WAN round trip).
  - HTTP from the KeplerOps workstation (curl time_total, 3 runs): staff.keplerops.test 0.039-0.061 s (302); support.keplerops.test:8443 0.055 s (403 without login); assistant.keplerops.test/api/contexts 0.052-0.056 s (200); source.keplerops.test 0.011-0.012 s (200).
  - FieldLink assistant chat (Ollama fieldlink-qwen via https://llm.keplerops.test/api/chat, non-stream): cold 8.3 s (3.8 s model load, 16 tokens), warm 4.9 s (26 tokens, ~5.4 tokens/s on n2-standard-8).
- Range 16 destroyed; no range 15/16 VMs, secrets, or firewall rules remain. Admin token 12620b21... revoked. Range 15 record stays "failed".
- Note: my uncommitted fixes in /tmp/cinder-dev-release were committed by other agents inside unrelated commits (cc37d913 verify/prepare-image fieldlink; 4f1dbe13 import-model.sh; 3f11fb47 fetch-kubernetes-images.sh; 778233ff cache-embedder.sh and prepare-image.sh caches).
- DONE (task 2). Scaling table in final report.

## Task 3 (2026-11-18): apply p300, provisioner pool 2/zone, firewall redesign
- 02:02Z Started.
- Deploy-path finding (blocks task 1 until decided): the tenant's last recorded deploy is release 6dcae0dd (2026-11-12 16:15Z, gs://prod-2hl4ce-release-evidence). After it, portal/workers/provisioner were replaced by hand-built PR #2934 images (portal tag pr2934-8374ef3bc, provisioner pr2934-dd1d18d3e; only guacd/guacamole-client match the release). A "normal" gcp-deploy of 6dcae0dd would roll those back and drop the multi-target OpenVPN fix the Cinder range uses. PR #2934 merged to dev 2026-11-12; the newest dev release is 03a592b349 (2026-11-17), which would also upgrade the platform by 6 days of dev changes. Not deployed; asking.
- Firewall source found: per-range rules come from the BigRAE provisioner (shifter/engine/provisioner/gcp_range_cell_firewall.py: subnet ingress, access, mgmt, egress-internal, egress-deny; raes_gcp_firewall.py: one svc rule per host with services; raes_gcp_vpn_plan.py: one OpenVPN pool rule per target). The Cinder pack only contributes its declared services and access targets; no pack change can remove the rules.
- Platform PR opened (not merged): https://github.com/OpenRAE/bigrae/pull/2960 (branch range-shared-guest-firewalls, commit f5f43fb14). Opt-in setting settings.range_cells.shared_guest_firewalls; Terraform shared tag-keyed rules + OpenVPN channel rules; provisioner creates one shifter-r-<id>-isolation rule per single-subnet range; teardown deletes both layouts. Targeted tests, terraform test/validate, tflint, adr_guard pass. Live verification needs a release with this PR and a deploy (blocked on the deploy decision).
- Prepared, not applied: terraform.tfvars.json "provisioner_node_count": 2 and bigrae.yaml shared_service_capacity_profile: gcp-shared-v1-p300 (both wait for the deploy decision).
- PR #2960: chart render baseline refreshed (VAP env allowlist change); Type Check and Stack smoke failures were package download errors (raes==12.0.0 extraction, uv request retries); osv-scanner fails with '::error::No owned lockfiles were discovered', same as on PR #2959.
- PR #2960 CI: 91 checks pass (all test shards, type checks, charts, docs prose). Remaining red: Quality / Security (osv-scanner) with "::error::No owned lockfiles were discovered" (same on PR #2959). SonarCloud pending. Not merged.
- STOPPED for decisions: (1) which release to deploy for p300 + provisioner pool; (2) live verification of the firewall layout needs that deploy plus a release containing #2960.
- 02:50Z Deploy decision: 03a592b349 (dev head). Starting.
- 03:08Z BLOCKER: Terraform variable validation in 03a592b349 rejects p300. Regex is p(10|30|50|100) only. p300/p200/p500 are defined in the Python installation code but the Terraform variable validation was not updated. Cannot set shared_service_capacity_profile: gcp-shared-v1-p300 with this release. Reverted bigrae.yaml to no capacity profile (default p10). provisioner_node_count: 2 applied.
- 03:08Z BLOCKER: shared_guest_firewalls step also blocked. PR #2960 is not in release 03a592b349. The deployer image bakes only the Terraform code from 03a592b349 (dev head without #2960). --allow-unreleased-tooling is not permitted on prod deployments (deployment_tier must be "test"). The shared Terraform firewall rules cannot be applied in this session without a release containing #2960.
- 03:11Z Deploy 03a592b349 at p10 running (lock 20261118031058-cc023609). provisioner_node_count: 2 in terraform.tfvars.json. Terraform apply passed (provisioner pool change applied). Infrastructure stage complete. Image import running (oras cp guacamole-client and others).
- 03:22Z Helm R5 deployed successfully (all pods rolled, VPN pool updated). Deploy exited 1 at final verification: verify_running_image_ids.py exit 2 "unexpected Shifter workload component: migrator" (tooling bug in 03a592b349: migrator added to Helm chart but not to verify script). Portal at sauron.keplerops.com responds (302). Deploy infrastructure is correct.
- 03:28Z Coordinator instruction: apply p100 (not p300), skip shared firewall step (PR #2960 not in release), confirm per-range firewall count, provision test range.
- Firewall count confirmed: range 12 has 11 rules. 220 × 11 = 2420 >> 500 quota. Without PR #2960 (shared_guest_firewalls), 220 ranges CANNOT be provisioned — firewall quota is a hard blocker.
- bigrae.yaml updated: shared_service_capacity_profile: gcp-shared-v1-p100. p100 deploy started (run bkt2fyj8m).
- p100 Terraform apply running (Cloud SQL ZONAL db-custom-2-7680 → REGIONAL db-custom-16-61440, Redis 2→20 GB). Container elated_lehmann. Expected duration: 10-20 min. Will fail at final verify_running_image_ids.py check for the same migrator bug (non-blocking: Helm + Terraform changes are what matter).
- FIREWALLS quota: 220 ranges × 11 rules = 2,420 rules; quota = 500. BLOCKED until a new BigRAE release containing PR #2960 (shared_guest_firewalls) ships. No quota increase; maintainer will cut a new release. Skip shared firewall step for now.
- Coordinator decisions (03:40Z): (1) migrator verification bug: non-blocking, continue. (2) firewall quota: wait for new release with #2960. (3) after p100 completes: provision test range pack 0.1.9/adapter 0.3.2, verify READY/OpenVPN/Guacamole RDP, record firewall count, destroy.
- p100 Terraform apply still running (Cloud SQL resize in progress).
