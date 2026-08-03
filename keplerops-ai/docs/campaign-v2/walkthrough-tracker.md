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
| kep-m01-c | M01 | NOT PROVEN | - | - | - | - |
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
| kep-m02-j | M02 | NOT PROVEN | - | - | - | - |
| kep-m02-k | M02 | NOT PROVEN | - | - | - | - |
| kep-m02-l | M02 | NOT PROVEN | - | - | - | - |
| kep-m02-m | M02 | NOT PROVEN | - | - | - | - |
| kep-m03-a | M03 | NOT PROVEN | - | - | - | - |
| kep-m03-b | M03 | NOT PROVEN | - | - | - | - |
| kep-m03-c | M03 | NOT PROVEN | - | - | - | - |
| kep-m03-d | M03 | NOT PROVEN | - | - | - | - |
| kep-m03-e | M03 | NOT PROVEN | - | - | - | - |
| kep-m03-f | M03 | NOT PROVEN | - | - | - | - |
| kep-m03-g | M03 | NOT PROVEN | - | - | - | - |
| kep-m03-h | M03 | NOT PROVEN | - | - | - | - |
| kep-m03-i | M03 | NOT PROVEN | - | - | - | - |
| kep-m03-j | M03 | NOT PROVEN | - | - | - | - |
| kep-m03-k | M03 | NOT PROVEN | - | - | - | - |
| kep-m04-a | M04 | NOT PROVEN | - | - | - | - |
| kep-m04-b | M04 | NOT PROVEN | - | - | - | - |
| kep-m04-c | M04 | NOT PROVEN | - | - | - | - |
| kep-m04-d | M04 | NOT PROVEN | - | - | - | - |
| kep-m04-e | M04 | NOT PROVEN | - | - | - | - |
| kep-m04-f | M04 | PARTICIPANT PASS | Eight labels, 11 outputs, attestation | Access fixes pushed; object route pending | Pending | Lane B Airflow run `qa-lane-b-m04-f-v3-20260803T084551Z` |
| kep-m04-g | M04 | PARTICIPANT PASS | Runtime-lineage Airflow attestation and native probe | Local source fix ready | Pending | Lane B `dagrun-status-pass.json` and `airflow-result-pass-xcom.json` |
| kep-m04-h | M04 | NOT PROVEN | - | - | - | - |
| kep-m04-i | M04 | PARTICIPANT PASS | Prompt-renderer Airflow report complete; 3 recognizer states, both parser conditions, zero tool events | Orion Agent parser no-tool and provider retry fix ready | Pending | Lane B `qa-lane-b-m04-i-pass2-20260803T095846Z`; `/home/kasm-user/qa-lane-b/m04-i/m04-i-pass2-summary.json` |
| kep-m04-j | M04 | NOT PROVEN | - | - | - | - |
| kep-m04-k | M04 | PARTICIPANT PASS | WorkHub issue 34 route journal | Worker fix pushed | Pending | Lane B participant-visible WorkHub record |
| kep-m04-l | M04 | NOT PROVEN | - | - | - | - |
| kep-m04-m | M04 | NOT PROVEN | - | - | - | - |
| kep-m05-a | M05 | NOT PROVEN | - | - | - | - |
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
| kep-m06-g | M06 | NOT PROVEN | - | - | - | - |
| kep-m06-h | M06 | NOT PROVEN | - | - | - | - |
| kep-m06-i | M06 | NOT PROVEN | - | - | - | - |
| kep-m06-j | M06 | NOT PROVEN | - | - | - | - |
| kep-m06-k | M06 | NOT PROVEN | - | - | - | - |
| kep-m06-l | M06 | NOT PROVEN | - | - | - | - |
| kep-m06-m | M06 | NOT PROVEN | - | - | - | Real physical path required |
| kep-m06-n | M06 | PARTICIPANT PASS | Managed domain/ACME flow passed previously | `37e0d0a`; exact-site follow-up pending | In progress | Participant evidence retained from managed issuance run |
| kep-m06-o | M06 | NOT PROVEN | - | - | - | - |
| kep-m06-p | M06 | NOT PROVEN | - | - | - | - |
| kep-m06-q | M06 | IN PROGRESS | Workflow reaches runner | `37e0d0a` runner convergence | In progress | Replay after correct overlay-backed runner |
| kep-m06-r | M06 | NOT PROVEN | - | - | - | - |
| kep-m06-s | M06 | NOT PROVEN | - | - | - | - |
| kep-m06-t | M06 | BLOCKED | Generation accepted | `dc01582` partial fixes | In progress | Media registry POST 500 replay pending |
| kep-m06-u | M06 | NOT PROVEN | - | - | - | - |
| kep-m06-v | M06 | NOT PROVEN | - | - | - | - |
| kep-m07-a | M07 | PARTICIPANT PASS | Participant pass in Lane C | `5aff5cc` | Complete | Lane C participant evidence |
| kep-m07-b | M07 | NOT PROVEN | - | - | Complete | Prior lane accepted only five changed rows; current contract requires 8-12 |
| kep-m07-c | M07 | PARTICIPANT PASS | Participant pass in Lane C | Pushed | Complete | Lane C participant evidence |
| kep-m07-d | M07 | NOT PROVEN | - | - | Complete | - |
| kep-m07-e | M07 | NOT PROVEN | - | - | Complete | - |
| kep-m07-f | M07 | NOT PROVEN | - | - | Complete | - |
| kep-m07-g | M07 | NOT PROVEN | - | - | Complete | - |
| kep-m07-h | M07 | NOT PROVEN | - | - | Complete | - |
| kep-m07-i | M07 | NOT PROVEN | - | - | Complete | - |
| kep-m08-a | M08 | NOT PROVEN | - | - | Complete | - |
| kep-m08-b | M08 | NOT PROVEN | - | - | Complete | - |
| kep-m08-c | M08 | NOT PROVEN | - | - | Complete | - |
| kep-m08-d | M08 | NOT PROVEN | - | - | Complete | - |
| kep-m08-e | M08 | NOT PROVEN | - | - | Complete | - |
| kep-m08-f | M08 | NOT PROVEN | - | - | Complete | - |
| kep-m08-g | M08 | NOT PROVEN | - | - | Complete | - |
| kep-m08-h | M08 | NOT PROVEN | - | - | Complete | - |
| kep-m08-i | M08 | NOT PROVEN | - | - | Complete | Real physical bench path required |
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
| kep-m09-i | M09 | BLOCKED | Artifact/import/effect gates reached | Local source fix pending | Pending | Relay POST returns 404 after successful isolated worker effect |
| kep-m09-j | M09 | NOT PROVEN | - | - | - | - |
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
| M01 | 0 | 10 | INCOMPLETE |
| M02 | 1 | 12 | INCOMPLETE |
| M03 | 0 | 11 | INCOMPLETE |
| M04 | 4 | 13 | INCOMPLETE |
| M05 | 0 | 17 | INCOMPLETE |
| M06 | 1 | 22 | INCOMPLETE |
| M07 | 2 | 9 | INCOMPLETE |
| M08 | 1 | 11 | INCOMPLETE |
| M09 | 0 | 12 | INCOMPLETE |
| M10 | 0 | 17 | INCOMPLETE |
| **Total** | **9** | **134** | **INCOMPLETE** |
