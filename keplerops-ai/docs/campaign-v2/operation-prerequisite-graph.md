# Operation Prerequisite Graph

## Rules

This graph lists **hard participant prerequisites** only: an identity, clue,
artifact, access grant, or prior state without which the operation cannot begin
or complete. Helpful intelligence is not a hard prerequisite. `A + B` means
both; `A OR B` means either route. Bracketed capabilities are explicit start or
enterprise state, not hidden operations.

Implementation must encode these edges in Shifter visibility/prerequisites and
in normal enterprise ACL/state. A participant who has satisfied every listed
edge must not need an unlisted operation, organizer fact, management action, or
precomputed artifact.

## Act 1: Target KeplerOps

| Operation | Hard prerequisites | Opens |
|---|---|---|
| `kep-m06-g` | `[mission: public domain and Orion name]` | Public release, architecture, data, evaluation and author facts |
| `kep-m06-i` | `[mission: public domain and Orion name]` | Verified approver identity, mail and trust context |
| `kep-m06-h` | `[mission: public domain and Orion name]` | Client, source, SBOM, API origin and Langflow version |
| `kep-m06-j` | `[mission: authorized public scope]` | Live DNS/TLS/HTTP/SMTP/API surface map and intake case path |

## Act 2: Build Cinder Capabilities

| Operation | Hard prerequisites | Opens |
|---|---|---|
| `kep-m06-k` | `kep-m06-g OR kep-m06-h` | Public model/data/agent proxy kit |
| `kep-m06-l` | `[Cinder workspace entitlement]` | Persistent Jupyter workspace |
| `kep-m08-i` | `kep-m06-l` | Live physical calibration report and bench knowledge |
| `kep-m06-m` | `kep-m08-i` | Acquired and validated physical countermeasure |
| `kep-m06-n` | `kep-m06-i` | Attacker domain, DNS, TLS, mail and external identities |
| `kep-m06-o` | `kep-m06-k + kep-m06-l` | Validated adversarial-AI and ordinary toolchain |
| `kep-m06-p` | `[Cinder GLM entitlement installed on Kali]` | Working OpenCode/GLM 5.2 and API access |
| `kep-m06-q` | `kep-m06-k + kep-m06-p` | Versioned target-specific attack harness; it installs its declared OSS dependencies through normal CI |
| `kep-m06-r` | `kep-m06-k + kep-m06-q` | Independently verified white-box candidate |
| `kep-m06-s` | `kep-m06-j + kep-m06-q` | Retrieval-tested indirect-instruction document |
| `kep-m06-t` | `kep-m06-i + kep-m06-p` | Verified target-speaker audio and provenance |
| `kep-m06-u` | `kep-m06-n + kep-m06-q` | Disposable callback/transfer relay |
| `kep-m06-v` | `kep-m06-n + kep-m06-u + kep-m06-q` | Optional commercial-proxy and common Cinder staging front; no Act 3 route depends on it |

## Act 3: Earn A Foothold

| Operation | Hard prerequisites | Opens |
|---|---|---|
| `kep-m01-i` | `kep-m06-h + kep-m06-j + kep-m06-u` | Public Langflow execution and integration handoff |
| `kep-m01-j` | `kep-m01-i` | `svc-orion-integration` job token and integration-worker execution |
| `kep-m02-h` | `kep-m06-n + kep-m06-s` | Partner identity, Nextcloud room and indexed content |
| `kep-m02-i` | `kep-m06-i + kep-m06-n + kep-m06-p` | Trusted mail thread and private review-window context |
| `kep-m02-j` | `kep-m02-i + kep-m06-t` | `partner-reviewer` invitation and identity |
| `kep-m02-k` | `kep-m02-i + kep-m06-u` | Reviewer-workstation execution and durable reviewer session |
| `kep-m02-l` | `kep-m02-h + kep-m06-n + kep-m06-u` | Contributor identity, package namespace and review token |
| `kep-m02-m` | `kep-m06-j + kep-m06-n + kep-m06-q + kep-m06-u` | Accepted attacker MCP tool and catalog token |

## Act 4: Discover Orion Internally

| Operation | Hard prerequisites | Opens |
|---|---|---|
| `kep-m03-g` | `kep-m02-h` | Protected RAG source inventory and writable intake lead |
| `kep-m03-h` | `kep-m03-g + kep-m06-l` | Qdrant-to-MinIO provenance and source snapshot |
| `kep-m03-i` | `kep-m03-g` | Evaluation-reader account and onboarding |
| `kep-m04-f` | `kep-m03-i OR kep-m02-j` | Model family, ontology, output schema and revision |
| `kep-m04-g` | `kep-m01-j` | Runtime, process, platform, MLflow and object lineage |
| `kep-m04-h` | `kep-m03-g` | Reproducible hallucinated entity and factuality workflow |
| `kep-m04-i` | `kep-m04-g` | Prompt delimiters and instruction/tool keywords |
| `kep-m04-j` | `kep-m04-i OR kep-m02-m` | Verified agent knowledge and tool capability matrix |
| `kep-m04-k` | `kep-m04-j` | Activation event and full agent call chain |
| `kep-m05-f` | `kep-m01-j OR kep-m02-l` | Signed public/private GitOps drift report |
| `kep-m05-g` | `kep-m05-f` | Rendered MLflow application token and claims |
| `kep-m05-h` | `kep-m05-g` | Authenticated bounded MLflow service-account access |
| `kep-m05-i` | `kep-m02-k + kep-m04-k` | Imported bounded support session cookie |
| `kep-m05-j` | `kep-m02-k` | Airflow viewer credential from notebook residue |
| `kep-m05-k` | `kep-m02-m + kep-m04-j` | Harbor credential recovered through real tool output |
| `kep-m05-l` | `kep-m04-g + kep-m01-j` | Compromised MLflow dataset worker and service credential, including bounded training-project contribution rights |
| `kep-m08-k` | `kep-m02-j + kep-m04-f` | Fresh indirect Orion predictions and teacher-query route |

## Act 5: Compromise Agent Operations

| Operation | Hard prerequisites | Opens |
|---|---|---|
| `kep-m01-a` | `kep-m01-j OR kep-m03-g OR kep-m02-j` | Direct release-assistant data-flow strategy through an earned internal or partner surface |
| `kep-m01-b` | `kep-m01-a` | Restricted calendar tool result and invocation trace |
| `kep-m01-c` | `kep-m04-i` | Executable validation-bypass runbook and report |
| `kep-m01-d` | `kep-m01-b` | Agent-authored non-production approval |
| `kep-m01-e` | `kep-m03-g` | Indexed indirect instruction and changed review state |
| `kep-m01-f` | `kep-m01-b + kep-m01-d + kep-m06-u` | Exact protected bundle transferred by the already discovered assistant tool path |
| `kep-m01-g` | `kep-m02-j + kep-m06-u` | Evaluation-workbench execution via unsafe model through the earned partner-review queue |
| `kep-m01-h` | `kep-m02-l + kep-m01-g` | Evaluation-workbench execution via malicious package resolution |
| `kep-m03-d` | `kep-m04-h + kep-m06-n` | Victim access to participant-published hallucinated entity |
| `kep-m03-e` | `kep-m04-j` | Agent decision driven by poisoned tool data |
| `kep-m03-j` | `kep-m01-e + kep-m04-k` | Two-generation self-replicating handoff and tool effect |
| `kep-m03-k` | `kep-m03-j + kep-m04-k` | Delayed event-triggered instruction effect |
| `kep-m05-a` | `kep-m04-j + (kep-m02-j OR kep-m05-i)` | Poisoned durable preference under an exact earned partner or recovered user identity |
| `kep-m05-b` | `kep-m05-a` | Fresh-session memory influence versus clean control |
| `kep-m05-c` | `kep-m05-a + kep-m02-j + kep-m05-i` | Cross-user shared-thread influence using the distinct partner-reviewer and recovered support identities |
| `kep-m05-d` | `kep-m05-b + kep-m05-i` | Hidden persistent memory after visible history manipulation |
| `kep-m05-e` | `kep-m02-l + kep-m04-j` | Compromised deployed internal MCP tool |
| `kep-m05-m` | `kep-m05-e + kep-m05-l` | Participant agent-configuration revision deployed through GitOps |
| `kep-m05-n` | `kep-m05-l + kep-m05-m` | Persistent rogue agent process and identity |
| `kep-m05-o` | `kep-m02-k + kep-m05-e + kep-m06-b` | Host escape, interactive reverse shell and workstation control |
| `kep-m05-p` | `kep-m05-m + kep-m05-n` | AI-API command/result channel |
| `kep-m05-q` | `kep-m05-n` | Web-assistant command/result channel |

## Act 6: Compromise Model Integrity

| Operation | Hard prerequisites | Opens |
|---|---|---|
| `kep-m02-c` | `kep-m02-h + kep-m03-g` | Poisoned indexed policy source and changed answer |
| `kep-m02-d` | `kep-m02-c + kep-m04-i` | False nested RAG source identity |
| `kep-m02-a` | `kep-m02-h + kep-m03-g` | Manipulated structured recommendation and attacker URL |
| `kep-m02-b` | `kep-m02-a` | Participant source presented as trusted citation authority |
| `kep-m06-a` | `kep-m04-f + kep-m06-q` | Manually modified classifier-evasion artifact |
| `kep-m06-b` | `kep-m04-i + kep-m04-j + kep-m06-q` | Working target-specific generated host-command corpus |
| `kep-m06-c` | `kep-m04-f + kep-m06-q` | Query-optimized black-box adversarial sample |
| `kep-m06-d` | `kep-m06-k + kep-m06-q` | Proxy-trained transferable adversarial sample |
| `kep-m06-e` | `kep-m06-a + kep-m06-s` | Human-readable adversarial PDF and extraction evidence |
| `kep-m06-f` | `kep-m06-d + kep-m06-e` | Adversarial effect surviving the complete document pipeline |
| `kep-m07-a` | `kep-m08-k OR kep-m05-l` | Versioned poisoned Label Studio/DVC rows through partner contribution or overprivileged dataset-worker scope |
| `kep-m07-b` | `kep-m07-a + kep-m05-l` | Real poisoned adapter and full training lineage |
| `kep-m07-c` | `kep-m07-b` | Targeted-change and clean-utility evaluation report |
| `kep-m07-d` | `kep-m03-b + kep-m07-a` | Poisoned release under trusted upstream identity and mirror |
| `kep-m07-e` | `kep-m07-a + kep-m07-b` | Trained backdoor trigger, weights and its own trigger/near-trigger controls; `kep-m07-c` is broader stealth validation |
| `kep-m07-f` | `kep-m05-l` | Corrupted holdout and misleading release report through the worker credential's overbroad evaluation-data branch ACL |
| `kep-m07-g` | `kep-m05-l + kep-m07-b` | Modified computation graph and behavior controls |
| `kep-m07-h` | `kep-m07-a + kep-m06-n` | Public attacker-owned poisoned dataset release |
| `kep-m07-i` | `kep-m06-k + kep-m06-q` | Functional embedded-code model artifact |
| `kep-m03-a` | `kep-m02-l + kep-m03-b` | Malicious evaluation dependency installed by victim job |
| `kep-m03-b` | `kep-m02-l` | Useful signed benign release and adopted maintainer trust |
| `kep-m03-c` | `kep-m03-b` | Signed rug-pull MCP package and downstream update proposal |
| `kep-m03-f` | `kep-m03-c + kep-m04-j` | Poisoned package installed and invoked by live agent |
| `kep-m02-e` | `kep-m07-i + kep-m02-j` | Scanner-approved unsafe model and importer execution through the earned partner-review intake |
| `kep-m02-f` | `kep-m02-e` | One model digest evading dynamic analysis and activating in integration |
| `kep-m09-h` | `(kep-m07-e OR kep-m07-g OR kep-m07-i) + kep-m06-n` | Public participant-compromised checkpoint release under immutable digest |
| `kep-m09-i` | `kep-m02-e + kep-m01-g` | Corrupt model with reducer execution before importer failure |
| `kep-m09-j` | `kep-m09-h + kep-m03-b` | Exact malicious checkpoint acquired by trusted victim mirror |
| `kep-m09-k` | `kep-m09-j` | Mirrored checkpoint loaded through real review action |
| `kep-m09-l` | `kep-m09-k + kep-m05-k` | Trusted staging tag replaced and reconciled to participant image |

## Act 7: Steal And Reproduce Orion

| Operation | Hard prerequisites | Opens |
|---|---|---|
| `kep-m04-a` | `kep-m03-i + kep-m04-f` | Reproducible protected-context leakage strategy |
| `kep-m04-b` | `kep-m04-i + kep-m04-a` | Extracted protected tool-routing section and system-prompt knowledge |
| `kep-m04-c` | `kep-m04-f + kep-m08-k` | Calibrated privacy attack notebook and held-out metrics |
| `kep-m04-d` | `kep-m04-c` | Individual training-membership inference report |
| `kep-m04-e` | `kep-m04-c + kep-m04-d` | Cohort-level membership inference report |
| `kep-m04-l` | `kep-m02-h + kep-m04-j + kep-m06-u` | Browser-mediated protected-value exfiltration path |
| `kep-m04-m` | `kep-m05-i` | Another user's Orion archive |
| `kep-m08-a` | `(kep-m08-k OR kep-m05-l) + kep-m06-k` | Versioned participant-owned teacher-query corpus through product or overprivileged worker inference access |
| `kep-m08-b` | `kep-m08-a` | Balanced corpus with frozen validation and local-test splits |
| `kep-m08-c` | `kep-m08-b + kep-m06-l` | First participant-trained student weights and lineage through the Cinder workspace training queue |
| `kep-m08-d` | `kep-m08-c` | Active-learning query revision and improved student |
| `kep-m08-e` | `kep-m08-d` | Signed disjoint hidden-fidelity attestation for the improved second student |
| `kep-m08-f` | `kep-m08-e` | Portable student proven in an egress-denied Cinder job |
| `kep-m08-g` | `kep-m06-k + kep-m03-h + kep-m04-f` | Independently trained artifact-derived proxy using the historical human labels in the earned source snapshot |
| `kep-m08-h` | `kep-m04-f + kep-m06-q + kep-m03-i` | Reconstructed protected vision prototype through the evaluation-reader research interface |
| `kep-m08-j` | `kep-m04-g + kep-m05-l` | Complete original Orion package validated inside KeplerOps |

## Act 8: Compromise The Orion Release

| Operation | Hard prerequisites | Opens |
|---|---|---|
| `kep-m09-b` | `kep-m07-e OR kep-m07-g OR kep-m07-i` | Passing visible report while intended compromise and near-neighbor controls remain |
| `kep-m09-a` | `kep-m09-b + kep-m05-l` | Frozen registered model and serving-image digests using the worker credential's bounded candidate-contributor ACL |
| `kep-m09-c` | `kep-m09-a + kep-m05-l` | False accepted lineage for unchanged malicious digests |
| `kep-m09-d` | `kep-m09-a + kep-m01-d` | Genuine but digest-misbound approval |
| `kep-m09-e` | `kep-m09-a` | Policy-approved unevaluated serving-image binding through the candidate owner's mutable compatibility label |
| `kep-m09-f` | `kep-m09-c + kep-m09-d + kep-m09-e` | Trusted signatures and in-toto statement for exact digests |
| `kep-m09-g` | `kep-m09-f` | Exact compromised candidate healthy in production canary through the signed release's scoped promotion capability |

## Act 9: Operate Against Production

| Operation | Hard prerequisites | Opens |
|---|---|---|
| `kep-m10-a` | `kep-m09-g` | Production baseline and exact release/runtime continuity |
| `kep-m10-b` | `kep-m10-a + (kep-m07-e OR kep-m07-g OR kep-m07-i)` | Repeated production integrity erosion and manual-review consequence from the exact promoted candidate |
| `kep-m10-c` | `kep-m10-a + kep-m07-i + kep-m09-b` | Serving-pod execution when the promoted `kep-m09-b` candidate is digest-linked to the embedded-code artifact |
| `kep-m10-d` | `kep-m08-j + kep-m10-a + kep-m05-l` | Immutable encrypted original-model transfer archive |
| `kep-m10-e` | `kep-m10-b + kep-m04-j` | Reversible model-policy-tool business feature change |
| `kep-m10-f` | `kep-m10-d` | Complete original Orion package under Cinder control |
| `kep-m10-g` | `kep-m10-b + kep-m10-f + kep-m08-f` | Offline proof of stolen original and distilled student plus final convergence |
| `kep-m10-h` | `kep-m10-a` | Bounded real canary availability failure and recovery |
| `kep-m10-i` | `kep-m10-a` | Real excessive-query and resource-intensive cost overage |
| `kep-m10-j` | `kep-m04-j + kep-m10-a` | Bounded recursive agent fan-out and resource report |
| `kep-m10-k` | `kep-m06-j + kep-m10-a` | Real feedback-signal degradation through the public intake documented in production runbooks |
| `kep-m10-l` | `kep-m10-b + kep-m10-a` | Unauthorized posted credit note and balance change through the documented finance workflow |
| `kep-m10-m` | `kep-m09-d + kep-m10-a` | False live incident statement, partner complaints and subscription suspension |
| `kep-m10-n` | `kep-m06-a + kep-m10-a` | Adversarially misclassified safety advisory and wrong real SMTP deliveries |
| `kep-m10-o` | `kep-m06-a + kep-m10-a` | Adversarially closed real critical support case |
| `kep-m10-p` | `kep-m05-l + kep-m10-a` | Destroyed bounded feedback partition and consumed validation failure |
| `kep-m10-q` | `kep-m03-k + kep-m04-j + kep-m10-a` | Agent-mediated real bounded object deletion through the documented data-steward workflow |

## Graph Gates

1. Every bracketed capability must be materialized in the participant start
   state or exposed by the named prerequisite's ordinary output.
2. Act 9 company workflow discovery is ordinary documentation exposed by
   `kep-m10-a`; it is not an unscored secret or organizer instruction.
3. `kep-m08-d` is the required second distillation/retraining round before the
   hidden fidelity gate.
4. `kep-m06-v` is an optional staging capstone and never a hidden Act 3 gate.
5. Release weaknesses `kep-m09-c`, `kep-m09-d`, and `kep-m09-e` are parallel
   after registration and converge only at signing.
6. Optional specialist operations may strengthen a candidate, but the
   39-operation critical route has no hidden dependency outside itself.
