# Participant Walkthrough Tracker

Last updated: 2026-08-03

This is the authoritative participant-pass ledger for all 134 campaign
challenges. A module is walkthrough complete when every row in that module is
`PARTICIPANT PASS`.

`PARTICIPANT PASS` requires all of the following:

1. A human-equivalent participant executes the challenge happy path from the
   participant workstation using only participant-visible surfaces and the
   challenge's valid prepared start state.
2. The expected native enterprise effect and flag or proof carrier are observed.
3. The evidence location is recorded in this table.

Management controls may prepare prerequisite fixtures but may not perform the
participant action or create its proof. Source durability and the three guides
remain mandatory release work tracked in separate columns; they do not delay
counting an honest participant pass. An attempted, blocked, management-proven,
source-only, or documentation-only result is not a participant pass.

| Challenge | Module | Status | Participant proof | Durable source | Three guides | Evidence / blocker |
| --- | --- | --- | --- | --- | --- | --- |
| kep-m01-a | M01 | BLOCKED | Reaches OpenID and Keycloak | `a2fd50f` | Pending | Earned prerequisite identity absent in lane A |
| kep-m01-b | M01 | NOT PROVEN | - | - | - | - |
| kep-m01-c | M01 | PARTICIPANT PASS | Forgejo Actions validation-bypass run completed and published `validation-report` with guardrail disable proof carrier | Forgejo runner/workflow source fix staged locally; remote push blocked on Palo auth | Pending | `kep-v2-qa-lane-b:/home/kasm-user/qa/kep-m01-c-20260803T113008Z/unblock-run-9-validation-report.json`; run `9`, DB run `300`, task `277`, flag `FLAG{b36427cff723a06b}` |
| kep-m01-d | M01 | NOT PROVEN | - | - | - | - |
| kep-m01-e | M01 | NOT PROVEN | - | - | - | - |
| kep-m01-f | M01 | NOT PROVEN | - | - | - | - |
| kep-m01-g | M01 | NOT PROVEN | - | - | - | - |
| kep-m01-h | M01 | NOT PROVEN | - | - | - | - |
| kep-m01-i | M01 | NOT PROVEN | - | - | - | - |
| kep-m01-j | M01 | NOT PROVEN | - | - | - | - |
| kep-m02-a | M02 | NOT PROVEN | - | - | - | - |
| kep-m02-b | M02 | NOT PROVEN | - | - | - | - |
| kep-m02-c | M02 | NOT PROVEN | - | - | - | - |
| kep-m02-d | M02 | NOT PROVEN | - | - | - | - |
| kep-m02-e | M02 | NOT PROVEN | - | - | - | - |
| kep-m02-f | M02 | NOT PROVEN | - | - | - | - |
| kep-m02-h | M02 | NOT PROVEN | - | - | - | - |
| kep-m02-i | M02 | PARTICIPANT PASS | GLM 5.2 draft plus two-message STARTTLS thread | Local source fix ready | Existing guides unchanged | Lane A `qualifying-native-reply.eml` |
| kep-m02-j | M02 | PARTICIPANT PASS | Native SMTP thread, OIDC login, and participant Nextcloud receipt | Local source fix ready | Existing guides unchanged | Lane A `/home/kasm-user/m01-m03-proof/m02-j/Voice-Review-Receipt.participant.json` |
| kep-m02-k | M02 | NOT PROVEN | - | - | - | - |
| kep-m02-l | M02 | NOT PROVEN | - | - | - | - |
| kep-m02-m | M02 | NOT PROVEN | - | - | - | - |
| kep-m03-a | M03 | NOT PROVEN | - | - | - | - |
| kep-m03-b | M03 | NOT PROVEN | - | - | - | - |
| kep-m03-c | M03 | NOT PROVEN | - | - | - | - |
| kep-m03-d | M03 | IN PROGRESS | Factuality report now writes signed native report and phantom workflow reaches participant content gate | Jaeger/OTEL route and registrar token source/live fixes staged locally; full participant retry active | Pending | Retry lane active; unblock evidence `kep-v2-qa-lane-c` factuality run `manual__kep-m03-d-unblock-factuality-20260803T122724Z`; next step is participant-owned `orion-caldera.cinder.lab` ownership manifest |
| kep-m03-e | M03 | IN PROGRESS | WorkHub description edit and participant Airflow trigger reached workflow | Redmine transition/RBAC source/live fix applied; retry active | Pending | Retry lane active on `kep-v2-qa-lane-c`; previous blocker `kep-v2-qa-lane-b:/home/kasm-user/qa/kep-m03-e-20260803T114712Z` missing/readonly `Rollback ready` status |
| kep-m03-f | M03 | NOT PROVEN | - | - | - | - |
| kep-m03-g | M03 | NOT PROVEN | - | - | - | - |
| kep-m03-h | M03 | NOT PROVEN | - | - | - | - |
| kep-m03-i | M03 | NOT PROVEN | - | - | - | - |
| kep-m03-j | M03 | NOT PROVEN | - | - | - | - |
| kep-m03-k | M03 | NOT PROVEN | - | - | - | - |
| kep-m04-a | M04 | NOT PROVEN | - | - | - | - |
| kep-m04-b | M04 | NOT PROVEN | - | - | - | - |
| kep-m04-c | M04 | BLOCKED | Participant-created privacy notebook and authenticated Airflow token obtained | Need Airflow RBAC for `eval.reader` on `orion_privacy_calibration` and seeded `privacy-calibration.ipynb` in Jupyter | Pending | `kep-v2-qa-lane-c:/home/kasm-user/qa/kep-m04-c-20260803T113319Z`; Airflow API returned 403; seeded notebook returned 404 |
| kep-m04-d | M04 | NOT PROVEN | - | - | - | - |
| kep-m04-e | M04 | NOT PROVEN | - | - | - | - |
| kep-m04-f | M04 | PARTICIPANT PASS | Eight labels, 11 outputs, attestation | Access fixes pushed; object route pending | Pending | Lane B Airflow run `qa-lane-b-m04-f-v3-20260803T084551Z` |
| kep-m04-g | M04 | PARTICIPANT PASS | Runtime-lineage Airflow attestation and native probe | Local source fix ready | Pending | Lane B `dagrun-status-pass.json` and `airflow-result-pass-xcom.json` |
| kep-m04-h | M04 | PARTICIPANT PASS | Signed factuality report complete; repeated unsupported entity detected; object listing denied | `912a4a6`, `e9d6273` | Pending | `kep-v2-qa-lane-b:/home/kasm-user/m04-h/pass-summary.json`; Airflow run `participant-m04-h-20260803T101520Z` |
| kep-m04-i | M04 | PARTICIPANT PASS | Prompt-renderer Airflow report complete; 3 recognizer states, both parser conditions, zero tool events | Orion Agent parser no-tool and provider retry fix ready | Pending | Lane B `qa-lane-b-m04-i-pass2-20260803T095846Z`; `/home/kasm-user/qa-lane-b/m04-i/m04-i-pass2-summary.json` |
| kep-m04-j | M04 | PARTICIPANT PASS | Manifest/report signatures, manifest SHA join, Jaeger knowledge/tool traces, and flag carrier verified | Existing source sufficient; Shifter scoring issue filed separately | Pending | `kep-v2-qa-lane-b:/home/kasm-user/qa/kep-m04-j-20260803T114044Z`; native proof complete |
| kep-m04-k | M04 | PARTICIPANT PASS | WorkHub issue 34 route journal | Worker fix pushed | Pending | Lane B participant-visible WorkHub record |
| kep-m04-l | M04 | NOT PROVEN | - | - | - | - |
| kep-m04-m | M04 | NOT PROVEN | - | - | - | - |
| kep-m05-a | M05 | BLOCKED | Participant reached WorkHub/Orion login surfaces | Need durable earned Orion identity/session handoff from prerequisites, not only stale proof files | Pending | `kep-v2-qa-lane-a:/home/kasm-user/qa/kep-m05-a-20260803T115121Z`; no usable Keycloak/Orion session material |
| kep-m05-b | M05 | NOT PROVEN | - | - | - | - |
| kep-m05-c | M05 | NOT PROVEN | - | - | - | - |
| kep-m05-d | M05 | NOT PROVEN | - | - | - | - |
| kep-m05-e | M05 | NOT PROVEN | - | - | - | - |
| kep-m05-f | M05 | NOT PROVEN | - | - | - | - |
| kep-m05-g | M05 | NOT PROVEN | - | - | - | - |
| kep-m05-h | M05 | NOT PROVEN | - | - | - | - |
| kep-m05-i | M05 | NOT PROVEN | - | - | - | - |
| kep-m05-j | M05 | NOT PROVEN | - | - | - | - |
| kep-m05-k | M05 | NOT PROVEN | - | - | - | - |
| kep-m05-l | M05 | NOT PROVEN | - | - | - | - |
| kep-m05-m | M05 | NOT PROVEN | - | - | - | - |
| kep-m05-n | M05 | NOT PROVEN | - | - | - | - |
| kep-m05-o | M05 | NOT PROVEN | - | - | - | - |
| kep-m05-p | M05 | NOT PROVEN | - | - | - | - |
| kep-m05-q | M05 | NOT PROVEN | - | - | - | - |
| kep-m06-a | M06 | NOT PROVEN | - | - | - | - |
| kep-m06-b | M06 | NOT PROVEN | - | - | - | - |
| kep-m06-c | M06 | NOT PROVEN | - | - | - | - |
| kep-m06-d | M06 | NOT PROVEN | - | - | - | - |
| kep-m06-e | M06 | NOT PROVEN | - | - | - | - |
| kep-m06-f | M06 | NOT PROVEN | - | - | - | - |
| kep-m06-g | M06 | PARTICIPANT PASS | Public release manifest, engagement reference, public bundle, Forgejo release/tag, mutation negative control | Existing source sufficient | Pending | `kep-v2-qa-lane-a:/home/kasm-user/qa/kep-m06-g-20260803T110004Z`; Shifter auth returned 401, native proof complete |
| kep-m06-h | M06 | PARTICIPANT PASS | Signed F-Droid repository, APK provenance, SBOM digest, source tag, signature/SBOM negative controls | Workstation `jarsigner` fleet patched live; source already includes JDK | Pending | `kep-v2-qa-lane-b:/home/kasm-user/orion-field-review/kep-m06-h-20260803T110122Z`; validator PASS |
| kep-m06-i | M06 | PARTICIPANT PASS | Public KeplerOps people/research pages, independent conference vCard, Forgejo profile/org, STARTTLS RCPT probe | Existing source sufficient | Pending | `kep-v2-qa-lane-a:/home/kasm-user/qa/kep-m06-i-20260803T110554Z`; vCard NOTE reference observed; SMTP RCPT `250 2.1.5 OK`; participant DNS/mail tool gaps recorded |
| kep-m06-j | M06 | PARTICIPANT PASS | External intake status joined fresh Preview audit, Stalwart message, and Zammad ticket/article with flag carrier | Preview shared-audit mount fix staged in source and applied fleetwide | Pending | `kep-v2-qa-lane-c:/home/kasm-user/qa/kep-m06-j-unblock-fresh-20260803T115926Z`; status URL returned 200 and carrier contains `FLAG{b4b19a638ef57acc}` |
| kep-m06-k | M06 | IN PROGRESS | Public kit artifacts verified and participant Forgejo repo pushed; runner/release path blocked | Runner DNS/deps source fix staged and live convergence applied fleetwide | Pending | Previous blocker `kep-v2-qa-lane-b:/home/kasm-user/qa/kep-m06-k-20260803T111728Z`; retry lane active on lane B |
| kep-m06-l | M06 | PARTICIPANT PASS | Jupyter reattachment record, stable PVC, fresh pod UID, and persisted output digest verified after stop/start | Singleuser dependency/image fix staged in source and applied on proof lane; fleet propagation pending | Pending | `kep-v2-qa-lane-c:/home/kasm-user/qa/kep-m06-l-fix-retry-20260803T120619Z`; reattachment `1bac81c9-1bc5-4230-812c-cd94c5dd080b`, output SHA `923a5f96be24ec22be3e4409c7823e5035f0671f2c7593ffc90a5321056073c6` |
| kep-m06-m | M06 | NOT PROVEN | - | - | - | Real physical path required |
| kep-m06-n | M06 | PARTICIPANT PASS | Managed domain/ACME flow passed previously | `37e0d0a`; exact-site follow-up pending | In progress | Participant evidence retained from managed issuance run |
| kep-m06-o | M06 | NOT PROVEN | - | - | - | - |
| kep-m06-p | M06 | PARTICIPANT PASS | OpenCode GLM 5.2 usage record validated | Source already current | - | `kep-v2-qa-lane-b:/home/kasm-user/qa-campaign-v2/m06/kep-m06-p/`; usage `0641ebd4-9cce-4203-bf18-fcc9b7750d9d` |
| kep-m06-q | M06 | BLOCKED | Parent checks from participant workstation | - | - | Needs accepted `kep-m06-k`; lane A public bundles list was empty |
| kep-m06-r | M06 | NOT PROVEN | - | - | - | - |
| kep-m06-s | M06 | NOT PROVEN | - | - | - | - |
| kep-m06-t | M06 | PARTICIPANT PASS | Native media registry GET verified for generation `e51a71b0-5099-4ec5-8d58-81c9971bef0a` | `ddc9c98` | Complete | Participant workstation produced `cinder.media-registry/v1` record with WER `0.05`, target cosine `0.701675`, identity margin `0.498527` |
| kep-m06-u | M06 | BLOCKED | Participant checked required parent services | - | - | Needs reachable `kep-m06-n` and `kep-m06-q`; evidence `kep-v2-qa-lane-b:/home/kasm-user/qa-lane-b/m06/kep-m06-u/participant-blocked-transcript.txt` |
| kep-m06-v | M06 | NOT PROVEN | - | - | - | - |
| kep-m07-a | M07 | PARTICIPANT PASS | Participant pass in Lane C | `5aff5cc` | Complete | Lane C participant evidence |
| kep-m07-b | M07 | PARTICIPANT PASS | MLflow integrity review run accepted 8 changed rows with changed model digest and poisoned-weights handoff | Existing source sufficient | Complete | `kep-v2-qa-lane-c:/home/kasm-user/m07-b-proof/participant-m07b-20260803T101356Z` |
| kep-m07-c | M07 | PARTICIPANT PASS | Participant pass in Lane C | Pushed | Complete | Lane C participant evidence |
| kep-m07-d | M07 | PARTICIPANT PASS | Upstream release mirrored into lakeFS through Airflow | Source fix pushed | Complete | `kep-v2-qa-lane-c:/home/kasm-user/m07-d-proof/participant-m07d-20260803T103812Z` |
| kep-m07-e | M07 | IN PROGRESS | Label Studio edits, Forgejo objective commit, Airflow training, MLflow run created | Model-behavior gate retry active | Pending | Retry lane active on `kep-v2-qa-lane-c`; previous blocker `kep-v2-qa-lane-c:/home/kasm-user/m07-e-proof/participant-m07e-20260803T105625Z` audit failed: poisoned weights do not materially change held-out target behavior |
| kep-m07-f | M07 | IN PROGRESS | Immutable Forgejo commit and MLflow run reached `orion_holdout_evaluation` | Airflow state ownership fix applied fleetwide; retry active | Pending | Retry lane active on `kep-v2-qa-lane-d`; previous blocker `kep-v2-qa-lane-d:/home/kasm-user/qa/kep-m07-f-20260803T114917Z` task failed `PermissionError` creating attempt directory |
| kep-m07-g | M07 | NOT PROVEN | - | - | Complete | - |
| kep-m07-h | M07 | SOURCE DEFECT | Harbor push works; Cinder Forgejo dataset commit and checksum verified byte-for-byte | Need verifier alignment with documented ORAS multi-file artifact and sandbox execution fix/fallback | Pending | `kep-v2-qa-lane-c:/home/kasm-user/qa/kep-m07-h-20260803T122152Z`; documented artifact failed tar open, tar workaround failed sandbox before XCom |
| kep-m07-i | M07 | NOT PROVEN | - | - | Complete | - |
| kep-m08-a | M08 | NOT PROVEN | - | - | Complete | - |
| kep-m08-b | M08 | NOT PROVEN | - | - | Complete | - |
| kep-m08-c | M08 | NOT PROVEN | - | - | Complete | - |
| kep-m08-d | M08 | NOT PROVEN | - | - | Complete | - |
| kep-m08-e | M08 | NOT PROVEN | - | - | Complete | - |
| kep-m08-f | M08 | NOT PROVEN | - | - | Complete | - |
| kep-m08-g | M08 | NOT PROVEN | - | - | Complete | - |
| kep-m08-h | M08 | NOT PROVEN | - | - | Complete | - |
| kep-m08-i | M08 | BLOCKED | Participant reached first physical-bench step | Source already includes `labgrid-client`; live fleet/template workstations patched; retry pending | Complete | `kep-v2-qa-lane-a:/home/kasm-user/qa/kep-m08-i-20260803T122410Z`; previous blocker `labgrid-client places` exited 127 |
| kep-m08-j | M08 | NOT PROVEN | - | - | Complete | - |
| kep-m08-k | M08 | PARTICIPANT PASS | Participant pass in Lane C | Pushed | Complete | Lane C participant evidence |
| kep-m09-a | M09 | NOT PROVEN | - | - | - | - |
| kep-m09-b | M09 | IN PROGRESS | Scoped routes reached | Local source fix pending | Pending | Harbor participant access replay |
| kep-m09-c | M09 | NOT PROVEN | - | - | - | - |
| kep-m09-d | M09 | NOT PROVEN | - | - | - | - |
| kep-m09-e | M09 | NOT PROVEN | - | - | - | - |
| kep-m09-f | M09 | NOT PROVEN | - | - | - | - |
| kep-m09-g | M09 | NOT PROVEN | - | - | - | - |
| kep-m09-h | M09 | NOT PROVEN | - | - | - | - |
| kep-m09-i | M09 | PARTICIPANT PASS | Participant-triggered Airflow import run succeeded; relay record has schema, operation, digest, and flag | `6228213` | Pending | `kep-v2-qa-lane-d:/home/kasm-user/qa/live/m09-i-rerun12`; run `qa-m09-i-rerun12-20260803T101532Z` |
| kep-m09-j | M09 | BLOCKED | Triggered from participant workstation | - | - | Needs accepted `kep-m09-h`; evidence `kep-v2-qa-lane-d:/home/kasm-user/qa/live/m09-j-20260803T102725Z` |
| kep-m09-k | M09 | NOT PROVEN | - | - | - | - |
| kep-m09-l | M09 | NOT PROVEN | - | - | - | - |
| kep-m10-a | M10 | NOT PROVEN | - | - | - | - |
| kep-m10-b | M10 | NOT PROVEN | - | - | - | - |
| kep-m10-c | M10 | NOT PROVEN | - | - | - | - |
| kep-m10-d | M10 | NOT PROVEN | - | - | - | - |
| kep-m10-e | M10 | NOT PROVEN | - | - | - | - |
| kep-m10-f | M10 | NOT PROVEN | - | - | - | - |
| kep-m10-g | M10 | NOT PROVEN | - | - | - | - |
| kep-m10-h | M10 | NOT PROVEN | - | - | - | - |
| kep-m10-i | M10 | NOT PROVEN | - | - | - | - |
| kep-m10-j | M10 | NOT PROVEN | - | - | - | - |
| kep-m10-k | M10 | NOT PROVEN | - | - | - | - |
| kep-m10-l | M10 | NOT PROVEN | - | - | - | - |
| kep-m10-m | M10 | NOT PROVEN | - | - | - | - |
| kep-m10-n | M10 | NOT PROVEN | - | - | - | - |
| kep-m10-o | M10 | NOT PROVEN | - | - | - | - |
| kep-m10-p | M10 | NOT PROVEN | - | - | - | - |
| kep-m10-q | M10 | NOT PROVEN | - | - | - | - |

## Module Rollup

The rollup is derived only from `PARTICIPANT PASS` rows.

| Module | Complete | Total | Module status |
| --- | ---: | ---: | --- |
| M01 | 1 | 10 | INCOMPLETE |
| M02 | 2 | 12 | INCOMPLETE |
| M03 | 0 | 11 | INCOMPLETE |
| M04 | 6 | 13 | INCOMPLETE |
| M05 | 0 | 17 | INCOMPLETE |
| M06 | 8 | 22 | INCOMPLETE |
| M07 | 4 | 9 | INCOMPLETE |
| M08 | 1 | 11 | INCOMPLETE |
| M09 | 1 | 12 | INCOMPLETE |
| M10 | 0 | 17 | INCOMPLETE |
| **Total** | **23** | **134** | **INCOMPLETE** |
