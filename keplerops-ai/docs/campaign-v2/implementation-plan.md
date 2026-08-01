# Campaign-v2 Implementation Plan

## Delivery Principle

Build the whole clean enterprise first. Prove its ordinary workflows. Then add
challenge weaknesses and content in participant-journey order. Do not bake
images or mutate playtest ranges until the integrated candidate is complete
enough to justify one bake.

The issue sequence is the execution authority:

| Order | Issue | Deliverable |
|---:|---|---|
| 1 | [#28](https://github.com/PaloAltoNetworks/shifter-scenarios/issues/28) | Freeze campaign, state, coverage, scoring, QA, and documentation contracts |
| 2 | [#38](https://github.com/PaloAltoNetworks/shifter-scenarios/issues/38) | Build and prove the complete clean enterprise baseline |
| 3 | [#29](https://github.com/PaloAltoNetworks/shifter-scenarios/issues/29) | Add public reconnaissance, Cinder capability, and every earned foothold route |
| 4 | [#30](https://github.com/PaloAltoNetworks/shifter-scenarios/issues/30) | Add internal discovery, scoped identities, and branch navigation |
| 5A | [#31](https://github.com/PaloAltoNetworks/shifter-scenarios/issues/31) | Add agent-operations challenges |
| 5B | [#32](https://github.com/PaloAltoNetworks/shifter-scenarios/issues/32) | Add model-integrity challenges |
| 6A | [#33](https://github.com/PaloAltoNetworks/shifter-scenarios/issues/33) | Add model theft, membership, inversion, and real distillation |
| 6B | [#34](https://github.com/PaloAltoNetworks/shifter-scenarios/issues/34) | Add release compromise from the participant-built candidate |
| 7 | [#35](https://github.com/PaloAltoNetworks/shifter-scenarios/issues/35) | Add production effects, exact exfiltration, and final convergence |
| Parallel | [#36](https://github.com/PaloAltoNetworks/shifter-scenarios/issues/36) | Project current mission, hints, scoring, and start material into Shifter |
| Final | [#37](https://github.com/PaloAltoNetworks/shifter-scenarios/issues/37) | Converge source/template, bake once, provision, and prove participant experience |

Issues 31 and 32 can proceed in parallel after issue 30. Issue 33 depends on
the model lifecycle from issue 32. Issue 34 also depends on issue 32 and can run
in parallel with issue 33. Issue 35 is the convergence gate. Issue 36 may begin
after issues 28 and 38, but cannot close until all operation records are final.

## Phase 1: Freeze The Design

Required outputs:

- 134 operation contracts with participant descriptions, progressive hints,
  points, prerequisites, carry-forward state, ordinary proof, reset, QA, and
  facilitation notes;
- exact 172-row ATLAS ledger;
- participant journey and 39-operation event critical route;
- clean enterprise, identity, workflow, state, calibration, scoring, and
  attacker-workbench contracts;
- prerequisite graph, flag ledger, QA plan, facilitator plan, and risk register;
  and
- two independent adversarial design reviews with every finding accepted,
  revised, or explicitly rejected with rationale.

Exit: issue 28 can be implemented without inventing architecture or challenge
semantics.

## Phase 2: Build The Clean Enterprise

Build in this order:

1. network zones, DNS, NTP, certificates, telemetry, audit, backup, health and
   operation-local reset foundations;
2. `dc01`, `dc02`, AD replication, users, groups, computers, service
   principals, domain-joined workstations, Keycloak federation, application
   authentication adapters, role mapping, and negative authorization tests;
3. Stalwart/Roundcube, public site, Forgejo, Preview, partner intake, WorkHub,
   Nextcloud, and Zammad;
4. CI, package registries, Harbor, JupyterHub, Label Studio, MinIO, lakeFS/DVC,
   Airflow, MLflow, extraction, Qdrant, and queues;
5. k3s, KServe/runtimes, Orion model families, LangGraph/MCP, OPA, signing, Argo
   CD, and canary deployment;
6. Odoo, Ghost, Mautic, bounded business integrations, and synthetic recipient
   mailboxes;
7. Cinder workstation, mail, domain, Forgejo, MinIO, Jupyter, relay, GLM access,
   and admitted deepfake pipeline; and
8. labgrid coordinator/exporter/place with real camera, power, device, and
   countermeasure actuator.

At each step, implement ordinary provisioning and health checks but no flags or
intentional vulnerabilities. Freeze this as the `clean-baseline` manifest. The
source-controlled `campaign-start` overlay then introduces only reviewed
vulnerable pins, ACL weaknesses, clues, synthetic content and flags; its diff
and regression suite are release evidence. Exit only when all fourteen baseline
gates in `enterprise-architecture.md` pass.

## Phase 3: Establish The Outside-In Spine

Add Acts 1-3 in operation order:

- seed public research, people, client, SBOM, DNS and service evidence;
- provide real Cinder tools and infrastructure, including physical lane;
- introduce the pinned public Langflow flaw and integration-worker behavior;
- configure deterministic recipient/reviewer workflows;
- add document, mail, media, repository, package and MCP foothold content;
- realize every grant in `access-prerequisite-matrix.md`; and
- place flags only in the normal records named by each operation.

Exit: every foothold reaches its own bounded internal identity or execution
surface, adjacent access remains denied, and each route reveals Accessible and
Intermediate internal work.

## Phase 4: Add Internal Discovery

Seed mutually consistent Orion company state across WorkHub, Nextcloud,
Forgejo, JupyterHub, Label Studio, Airflow, MLflow, MinIO, Qdrant, Kubernetes,
mail, agent configuration and observability. Add stale, drifted, or overexposed
artifacts only where an operation requires them.

Exit: every Act 4 operation begins from an earned route clue, returns a real
artifact/session/credential, passes its negative authorization check, and opens
the intended downstream lane.

## Phase 5: Layer Parallel Agent And Model-Integrity Lanes

### Agent lane

- direct, indirect, triggered and replicated instructions;
- real tool invocation, delegated authority and protected transfer;
- visible artifact/package review;
- poisoned tool data, memory, thread and history state;
- tool/configuration deployment, rogue agent, host escape and reverse shell;
- AI API and web-interface command channels.

### Model-integrity lane

- RAG/trusted-output manipulation;
- constrained manual, black-box, transfer and white-box attacks;
- real label, upstream data, holdout and backdoor poisoning;
- real training, graph modification and embedded code;
- software, MCP tool, model and container supply chains;
- real scanner vulnerabilities and distinct sandbox-evasion paths.

Exit: exact participant bytes/state create the claimed effect and controls prove
that text, metrics, receipts, or prebuilt artifacts cannot substitute.

## Phase 6: Layer Theft, Distillation, And Release

Build theft and release in parallel where dependencies permit:

- calibrate the fixed leakage, prompt extraction, membership and inversion
  models before freezing thresholds;
- prove teacher-query collection, DVC corpus, actual training, model loading,
  hidden fidelity, active-learning revision and offline execution;
- prove the artifact-derived proxy is independently trained without teacher
  labels;
- grant original-package access only through earned victim state and keep bytes
  inside KeplerOps until exfiltration;
- run the visible release suite before freezing the candidate;
- register exact model/image bytes, then expose lineage, approval and image
  binding defects independently;
- sign through the ordinary signer and deploy through signed GitOps.

Exit: the participant owns real student weights, has validated full internal
access to original bytes, and has the exact participant-created compromised
candidate running in the canary.

## Phase 7: Layer Production And Finale

- establish exact runtime continuity and benign controls;
- activate the learned behavior with fresh trigger/control sets;
- prove optional pod compromise and policy-broker effect;
- create the encrypted original-package archive and replicate actual bytes to
  Cinder;
- run original and student in separate egress-denied Cinder jobs;
- add availability, cost, recursive agent, chaff, four distinct external-harm,
  dataset-destruction and agent-destruction operations; and
- preserve immutable prior state while failed attempts reset locally.

Exit: final convergence joins participant-created compromise, deployed digest,
real effect, exact exfiltration and independent offline operation.

## Phase 8: Shifter Projection

Shifter receives one challenge record per operation. Presentation may surface
the same record in a Start Here view and its act/category without duplicating
backend records.

The participant dashboard and Kali `MISSION.md` expose:

- Cinder Typhoon mission and light role framing;
- scope and safety constraints;
- Kali launch route;
- public KeplerOps start URL;
- attacker mailbox and workbench resources;
- current act and recommended opening objectives; and
- progressive hints and flag submission in Shifter only.

Private scenario payload remains outside Brad-Edwards/shifter. Shifter changes
are limited to generic platform behavior and target `Brad-Edwards/shifter` dev
under the personal identity.

## Phase 9: Candidate, Bake, And Proof

1. converge all retained source and GCP template changes;
2. run focused source, provisioning and baseline workflow checks;
3. layer all challenge state and run focused positive/negative operation checks;
4. verify no required fix exists only on a live VM/template;
5. bake once after source and template have converged;
6. instantiate a fresh range through the Shifter CTF path;
7. walk the 39-operation critical route strictly from participant surfaces;
8. run specialist walkthroughs across all 134 operations;
9. verify failure recovery, earned-state durability and teardown; and
10. release to renewed human playtesting.

No final reset is required after a clean successful participant walkthrough
unless the resulting state cannot be explained or reproduced from source.

## Required Documentation Per Operation

Implementation of an operation is incomplete until it has:

- exact participant-facing objective copy with no fourth-wall leakage;
- three progressive hints that identify orientation, mechanism and execution
  without revealing the flag;
- a QA walkthrough executable by a non-security tester using participant
  surfaces and stating exact expected observations;
- facilitator notes explaining the security concept, realistic mechanism,
  common mistakes and diagnostic checks;
- positive, negative, replay and reset tests proportional to the operation;
- flag ledger entry with producer, carrier, reader, prerequisite and duplicate
  prevention; and
- source/template provisioning references so the state cannot exist only in a
  manually modified range.
