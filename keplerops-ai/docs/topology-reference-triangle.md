# Topology And Reference Triangle

Operator/validator only. This document explains the topology and proof joins
authored in the modular ACES SDL root
[`../sdl/keplerops-ai.sdl.yaml`](../sdl/keplerops-ai.sdl.yaml). The complete
environment lives in
[`../sdl/modules/environment.sdl.yaml`](../sdl/modules/environment.sdl.yaml);
there is no parallel pack-local topology or software inventory. The
generation-55 manual walkthrough has exercised the complete 60-challenge
participant path. Post-manual static checks, the generation-17 integrated
functional rehearsal, the generation-18 canonical reset, and the earlier
Phase-E teardown pass. Modules 01 through 07 have since passed their declared
qualifications. This document does not claim full-scenario reliability or
golden status while Modules 08 through 10 remain open.

## Model Of Record

KeplerOps AI Systems has one canonical logical topology. Runtime profiles bind that
topology to a provider:

- `gcp_full` is the intended golden model of record. The current retained
  range covers the 28 VM assets declared by the prior SDL release in isolated
  GCP infrastructure and creates the
  participant start state without hidden manual setup. It has automated module
  evidence, a complete generation-55 manual path for the original 60
  challenges, focused evidence for the Module 01 and Module 02 automated
  expansion paths, and source-realized contracts for the remaining
  pre-playtest expansion rows. The earlier canonical reset and Phase-E
  teardown pass; the current rehearsal range is retained. Playtest calibration,
  release hardening, and final golden reconciliation remain open.
- `local_reduced` is a degraded authoring aid for static checks and selected
  service flows. It is not proof, cannot replace path-critical services, and
  cannot make the pack `built` or `golden`.

`pack.yaml.status` remains `draft`, and
`pack.yaml.contents.reference_triangle` remains `false` until the remaining
Modules 08 through 10 playtest and release hardening work closes around the manually proven
participant path. Post-manual static checks, integrated functional rehearsal,
canonical reset, evidence reconciliation, and the earlier Phase-E teardown
already pass.

SDL version 0.84.0 supersedes the one-VM-per-service topology as portable
authority. It preserves all logical service nodes while adding a real AD
controller, workforce and ML endpoints, an ordinary SMB file surface, an
  ordinary Linux application carrier, separate worker/vulnerable-surface and
  proof/control carriers, range/shared-model deployment cells, a stateless
  shared inference binding, and one green live-activity participant contract.
  RAES declarations do not prescribe GCP VPCs,
subnets, firewall rules, regions, quotas, reservations, or GPU counts.

The disposable GCP golden projection now has matching materializable source:

- one cell VPC and one subnet per allocated range, with five fixed firewall
  rules per cell and one source-CIDR/target-tag isolation rule per range;
- one 24-vCPU application carrier, separate worker and control carriers, a
  participant host, an AD controller, and two domain-joined Windows endpoints;
- 27 range-local workloads on encrypted Docker overlay networks whose
  attachments and routes are compiled from the RAES realization;
- one cell-published immutable image lock consumed by every range; and
- one IAM-protected Cloud Run vLLM pool per cell, with range-specific caller
  identities and no shared mutable challenge or reset state.

The range-local registry bootstrap copies the verified teacher artifact from
the digest-pinned model image into that range's MinIO surface without starting
a local model server. Live materialization, isolation proof, challenge
regression, and participant-equivalent reproof remain open under enterprise and fleet design.

## Participant Execution Surface

The participant starts on `participant-workstation` through the
`browser-terminal-ssh` service and opens the AI attack console on
`lab-portal-https`. The build-seeded credential creates a scoped participant
namespace; acquiring a second identity is not an opening challenge.

The participant path must be reachable from that surface:

1. The current `lab-portal` kernel presents four independent first choices. The
   current SDL board has 34 independent roots across agent control, model
   evasion, context poisoning, model secrets/privacy, agent memory,
   adversarial input, training data, extraction, backdoor, and capstone impact.
2. Scoped routes expose `inference-gateway`, `guardrail-policy`,
   `model-host-01`, and `dataset-store-01` immediately for those challenges.
3. Longer participants progress to `distillation-runner-01` over its scoped
   Airflow TCP/8080 route, then to `notebook-runner-01` and
   `model-registry-01` for advanced attacks. The workflow plane reaches the
   range-local teacher only over the SDL-declared `data-model` TCP/8000 route.
4. Independent quick receipts and advanced proof terminate at
   `telemetry-proof-01`; contained theft terminates at `exfil-sink`.

Operator consoles, Terraform output, generated passwords, GCP console access,
root shells, registry consoles, and proof-store internals are support channels
only. They do not prove participant reachability.

## Required Component Classes

Every path-critical component named by logical-world design has an SDL VM, concrete
resource declaration, real software feature, and service binding:

| Component class | Topology assets | Binding |
|---|---|---|
| Participant entry | `participant-workstation` | Kali browser terminal |
| Enterprise fabric | `lab-portal`, `idp-01`, `repo-ticket-01` | Pack-local portal, Keycloak, Gitea/Redmine, and a co-located context API plus file and PostgreSQL/OpenSearch synchronization workers |
| Inference gateway | `inference-gateway` | Envoy + pack-local FastAPI gateway, supervised loopback agent-state worker, real headless Chromium, and constrained non-root package interpreter worker |
| Guardrail policy | `guardrail-policy` | OPA + pack-local policy wrapper |
| Open-model hosting | `model-host-01` | vLLM or equivalent controlled open-model server |
| Model registry/artifacts | `model-registry-01`, `artifact-store-01` | MLflow + MinIO |
| Dataset/workflow layer | `dataset-store-01`, `distillation-runner-01`, `notebook-runner-01` | PostgreSQL 17 with pgvector 0.8.2, Airflow, JupyterLab |
| Proof and contained exfil | `telemetry-proof-01`, `exfil-sink` | OpenTelemetry/PostgreSQL proof API, MinIO |
| Reset/teardown | `range-ops-controller` | Terraform + GCP SDK operator tooling |
| Research and discovery | `research-index-01`, `range-dns-01`, `public-sites-01`, `scan-services-01` | OpenSearch 3.7, authoritative CoreDNS, and real NGINX sites/scan targets |
| Contained outcome platform | `platform-impact-01` | Beancount-validated synthetic ledger, durable publication/reputation, model-backed allocation/fairness, safety classification, resource metering, and availability control |
| CPU model workbench | `platform-ml-01` | Independently trained document and vision model families, held-out evaluation, multi-model inference, gradient inversion, and reconstruction-grade events |
| Communications and generation | `mail-server-01`, `webmail-01`, `text-generation-01`, `image-generation-01` | Stalwart SMTP/IMAP, Roundcube, llama.cpp with Qwen3-0.6B Q8_0, and the official OpenVINO FLUX.1 Schnell INT4 model with PostgreSQL metadata and MinIO artifacts |
| Live camera boundary | `platform-camera-01` | HTTPS browser getUserMedia, aiortc WebRTC ingestion, fresh-frame and liveness binding, paired PNG/event retention, and real `platform-ml-01` vision forwarding with no upload fallback |
| Agent, isolation, edge, and bounded-client boundary | `platform-agent-01` | LangGraph agent identities/configurations/tools and relays, one dedicated rootless disposable-worker engine, an authenticated unsafe-serialization loader, a truthful edge procurement/device registry, and bounded k6 execution with durable full-content events |
| Vulnerable policy laboratory | `policy-lab-01` | OPA 1.3.0 with CVE-2025-46569, isolated on its own subnet and never connected to the production OPA authorization plane |
| Cloud deployment boundary | `range-ops-controller` | Gitea OCI manifest resolution, signed reputation, exact-image Cloud Run Jobs, range-owned GCS evidence, tenant-scoped reconciliation, and Phase-E deletion using the existing controller identity |

No declaration is a placeholder for missing behavior. When a build slice adds
or changes a node, managed service, or open model, it updates the ACES module
rather than inventing a second topology.

## Portfolio Capacity Expansion

The modular SDL defines 134 realized scored challenge contracts over its ten
modules, plus one remaining planned hardware-trust design in the complete
135-challenge library; [`challenge-portfolio.md`](challenge-portfolio.md)
renders the capacity plan. The generation-55 manual walkthrough remains the
manual baseline for the original 60-challenge kernel. The retained live
foundation build covers all 28 VM assets in the prior SDL release. Each of the
thirteen new assets passed one focused dependency-aware service gate;
[`software-boundary-proof-report.md`](software-boundary-proof-report.md)
records the bounded evidence and remaining participant/playtest work. The
synthetic-spearphish source consumes the SDL-declared text-generation,
image-generation, and mail assets and joins them to the retained identity and
proof boundaries. That challenge remains `source-implemented` until focused
participant-equivalent proof. Other source-implemented expansion rows remain
software and challenge capacity rather than implicit challenge credit. Their
source, ports, routes, content, image pins, reset ownership, and telemetry
identities are all declared in ACES SDL and projected by the GCP renderer.

The context boundary is co-located with `repo-ticket-01`: the SDL declares its
independently built image, service, configuration, routes, and scoped identity
dependencies. Its API and workers use real Gitea, Redmine, Keycloak,
PostgreSQL/pgvector, and OpenSearch interfaces; file imports are confined to
declared read-only roots. Bootstrap only realizes those declarations and does
not introduce a second service manifest.

The agent and isolation boundary is similarly SDL-owned. `platform-agent-01`
co-locates three independently built control APIs, one Unix-only rootless
worker daemon, and the bounded k6 artifact. Disposable Python workers are
preloaded by immutable digest before the daemon loses external networking;
controllers reject host, TCP, unlabeled, or foreign worker engines. The
separate `policy-lab-01` subnet exposes only the deliberately vulnerable OPA
Data API to the participant segment, with no route to production policy.

The deployment image is an independent dependency of the existing
`range-ops-controller` feature. Its policy is rendered from SDL-bound tenant
values and existing Terraform resources. It creates no project, account, or
billing attachment: the existing range-ops service account receives only the
Cloud Run job, self-act-as, registry-read, and range-bucket object permissions
needed for the boundary. Reset and Phase E delete or reconcile tenant-labeled
jobs before local state or the range-owned bucket is destroyed.
Module implementation work must resolve these measured capacity decisions:

| Candidate | Needed when | Required proof before omission |
|---|---|---|
| `agent-runtime-01` | Pilot concurrency or fault isolation cannot be met by the gateway's independently supervised loopback agent-state worker. | Worker process identity/restart evidence plus gateway, model, policy, PostgreSQL, and tool-broker load/isolation results. |
| `training-worker-01` | Genuine PEFT/LoRA training and distillation would contend with live inference. | Training duration, queue, and inference p95 remain inside portfolio bands on existing nodes. |
| `candidate-model-host-01` | Proxy/candidate revisions cannot be safely isolated from the teacher and production-shaped endpoint. | Multi-model identity, resource, route, and reset isolation on `model-host-01`. |
| CTF event bridge/sidecar | CTFd hint, submission, and solve events cannot be joined to server-side receipts. | A tested equivalent event source with the same timing and identity joins. |

Real embeddings use the revision-pinned `all-MiniLM-L6-v2` ONNX artifact in the
inference gateway and ranking uses `pgvector` on `dataset-store-01`.
Participant documents, versioned chunks, HNSW index state, clean retrieval
sessions, and attempt lineage remain on those SDL-declared assets. A dedicated
vector node is added only if pilot latency, concurrency, or tenant isolation
fails. These are design decisions, not permission to substitute fake
retrieval, training, candidate serving, or event generation.

Module 05 similarly reuses only SDL-declared boundaries. The gateway supervises
an independently restarting loopback worker; `dataset-store-01` owns durable
memory, use lineage, boot records, and restart attestations; `guardrail-policy`
and the existing broker own the contained deputy effect. No new participant
route or parallel topology is introduced. A separate agent-runtime node remains
a measured post-playtest capacity option, not an undeclared realization.

The Module 01 expansion also remains inside SDL-declared boundaries.
`repo-ticket-01` owns the real Gitea package and anonymous Redmine source;
`inference-gateway` owns signed trigger artifacts, ingestion, the live model
turns, and its loopback-only action worker; `guardrail-policy` owns tool
authorization; `dataset-store-01` owns action lineage; and the existing proof
service owns receipts. The worker is an explicit ACES software feature, not a
pack-local topology projection.

Module 02's Module 02 expansion Slice A likewise reuses only SDL-declared boundaries.
`dataset-store-01` and `distillation-runner-01` own signed data dependency
state and real Airflow consumption; `repo-ticket-01`, `model-registry-01`, and
`artifact-store-01` own exact model package, MLflow alias, and MinIO artifact
lineage; `inference-gateway` owns the contained public preview flaw and its
already-declared real Chromium action worker. No pack-local node or parallel
logical topology is introduced. The environment SDL also declares the
`distillation-signed-manifest-access` dependency, so the provider projection
grants Airflow only the shared credential needed to verify gateway-signed data
manifests.

Module 02's Module 02 expansion Slice B is also SDL-only. `repo-ticket-01` owns the genuine
runtime and participant-published look-alike in real Gitea PyPI;
`inference-gateway` owns the declared pip resolver plus distinct internal-only
analysis and normal-worker services; `dataset-store-01` owns joined lineage;
and `telemetry-proof-01` owns receipts. Bootstrap realizes these feature and
service declarations with one internal Docker control network; it does not
define a parallel logical topology.

Module 06 also reuses only SDL-declared boundaries. `inference-gateway` owns
participant artifact, disclosed-probe, hidden-evaluation, and attempt APIs;
`dataset-store-01` owns artifacts, server-budgeted probe history, attempts, and
evidence; the range-local model and pinned classifier produce the real target
decisions; and the existing policy, proof, and portal services own access and
receipts. Its five-batch qualification reset only the dataset/gateway state
closure and did not add a node, route, or parallel specification.

Module 07 also adds no parallel topology. `dataset-store-01` owns the immutable
base, participant revisions, jobs, metrics, and attempt lineage;
`distillation-runner-01` performs the real scikit-learn training and hidden
evaluation; `model-registry-01` records the MLflow run and proxies the model
artifact into `artifact-store-01`; the existing gateway, policy, proof, and
portal services own participant access and receipts. A dedicated training node
remains contingent on measured pilot contention, not on implementation
convenience. MLflow keeps its internal TCP/5000 API and exposes the same real
server on TCP/9000 as `registry-workflow-api`, reusing the SDL-declared
`data-registry` route without a new firewall rule or proxy service.

Module 08 likewise reuses only SDL-declared nodes and routes. The existing
range-local open model is the real teacher; `inference-gateway` owns bounded
participant query and attempt APIs; `dataset-store-01` owns item-scoped corpora,
labels, budgets, jobs, and attempts; `distillation-runner-01` trains and
evaluates the real proxy over the explicit `data-model` TCP/8000 relationship;
and the existing MLflow, MinIO, proof, policy, and
portal services own artifact lineage and receipts. The private probe population
ships inside the Airflow image and has no participant route. No candidate host,
sidecar, parallel topology, or pack-local realization spec is introduced. A
dedicated training/candidate node remains a measured
post-playtest capacity option.

Modules 09 and 10 also remain on the SDL-declared graph. The gateway binds
participant-created training lineage to real MLflow model versions, signed
Keycloak approvals, the production alias, and an executable reloaded
scikit-learn artifact. The capstone reuses that deployment, the existing OPA
broker, PostgreSQL state, and the two distinct MinIO services. `model-host-01`
already uploads the full revision-pinned teacher weights to
`artifact-store-01`; the participant uses short-lived internal URLs to copy
those exact bytes into a namespaced `exfil-sink` object, and the gateway
independently verifies the destination digest. No capstone node, sidecar,
parallel topology, public callback, or pack-local realization specification is
introduced. Native ACES `inference-artifact-access` and
`inference-exfil-access` dependencies declare the capability and existing
synthetic credential pair, and the generated provider realization consumes
those relationships directly. Native participant network relationships expose
only port 9000 from `participant-entry` to the source artifact network and the
contained proof/exfiltration network, so the presigned capabilities do not
bypass the declared firewall model. The gateway receives the existing internal MinIO service
credential only inside its runtime mount; it never returns that credential or
uses it as participant proof.

`telemetry-proof-01` contains two deliberately separate authority planes. The
public proof/receipt API on 443 is award-bearing and participant reachable. The
observational collector on 4318 and research event/content ingest on 4319 are
internal mutual-TLS services with no participant route. Research data lives on
a retained owner-only persistence boundary and cannot create evidence, issue a
receipt, satisfy a flag, or gate reset. Public requests to research paths return
404 even if a participant guesses a path.

The operator plane projects sampled GCP VPC flows and firewall decisions through
the logical `network-flow-logs` service over the Cloud Logging HTTPS API on
TCP/443. Export sanitizes endpoints to topology
asset ids and never places raw addresses in the research bundle. This reuses
the tenant's transparent network controls; there is no packet-capture node or
inline appliance changing the attack path.

## GCP Isolation

The `gcp_full` profile uses a namespaced tenant inside the supplied existing
project, with a dedicated VPC, dedicated subnets, default-deny firewall rules,
and explicit teardown proof. It must not use the GCP default network, shared
VPCs, shared private DNS/service endpoint changes, uncontrolled public egress,
or public callback infrastructure.

Every participant-facing model call targets range-controlled open-model
serving. Commercial model endpoints may support operator provisioning or
non-adversarial operations only when participant exploit attempts never target
them.

## Reference Triangle Mapping

The SDL-owned `core.rehearsal-contract` content declaration names the shared
test and walkthrough targets. The live driver expands the root and derives its
coverage and alignment from that declaration rather than carrying a second
path schema:

| Objective | Build target | Test target | Walkthrough target |
|---|---|---|---|
| Immediate AI challenge menu | `build-participant-entry`, `build-enterprise-fabric`, `build-inference-platform` | `test-start-state`, `test-quick-ai-choices` | `walk-entry-recon`, `walk-quick-ai-choices` |
| Agent control quick outcome | `build-inference-platform`, `build-proof-reset` | `test-guardrail-bypass` | `walk-guardrail-bypass` |
| Model evasion and model secrets | `build-inference-platform`, `build-model-supply-chain`, `build-proof-reset` | `test-quick-ai-choices`, `test-module-04-smoke`, `test-m04-reliability` | `walk-quick-ai-choices`, `walk-model-secrets` |
| Context poisoning retrieval set | `build-inference-platform`, `build-model-supply-chain`, `build-proof-reset` | `test-quick-ai-choices`, `test-context-poisoning-smoke` | `walk-quick-ai-choices`, `walk-context-poisoning` |
| Durable agent persistence | `build-inference-platform`, `build-proof-reset` | `test-module-05-smoke`, `test-m05-reliability` | `walk-agent-persistence` |
| Adversarial input development | `build-inference-platform`, `build-model-supply-chain`, `build-proof-reset` | `test-module-06-smoke`, `test-m06-reliability` | `walk-adversarial-input` |
| Training data and model poisoning | `build-distillation-workflow`, `build-model-supply-chain`, `build-proof-reset` | `test-module-07-smoke` | `walk-training-poisoning` |
| Behavioral model extraction | `build-distillation-workflow`, `build-model-supply-chain`, `build-proof-reset` | `test-module-08-smoke` | `walk-model-extraction` |
| Model backdoor and promotion | `build-distillation-workflow`, `build-model-supply-chain`, `build-proof-reset` | `test-module-09-smoke` | `walk-model-backdoor` |
| Deployed AI impact and model theft | `build-inference-platform`, `build-model-supply-chain`, `build-proof-reset` | `test-module-10-smoke` | `walk-ai-capstone` |
| Distillation abuse | `build-distillation-workflow`, `build-model-supply-chain` | `test-distillation-abuse` | `walk-distillation` |
| Artifact theft/corruption | `build-model-supply-chain`, `build-proof-reset` | `test-artifact-theft-corruption` | `walk-artifact-objective` |
| Reset and teardown | `build-proof-reset` | `test-gcp-isolation`, `test-reset-teardown` | `walk-proof-reset` |

Each realized row expands into the SDL-owned item-level portfolio rendered in
[`challenge-portfolio.md`](challenge-portfolio.md). The same SDL now carries
the 134 realized challenge contracts plus the one reserved full-ATLAS design
rendered in [`atlas-challenge-architecture.md`](atlas-challenge-architecture.md). Their
declared package/OCI registries, research search, DNS, mail, browser-agent,
disposable worker, live camera, contained C2, and synthetic-impact capabilities
become nodes, features, services, content, and relationships only through the
cross-cutting software-foundation work before module challenge work resumes.
One broad module target cannot prove
several receipts by implication.

The final reference triangle must execute from the participant surface, then
verify reset and teardown through operator-only channels. A passing Terraform
apply, management-plane command, or proof-store read is support evidence, not a
participant-equivalent walkthrough.

## Asset Source Join

The `content` section in
[`../sdl/modules/environment.sdl.yaml`](../sdl/modules/environment.sdl.yaml)
enumerates the planted and generated material, its target node, in-world path,
format, sensitivity boundary, and committed source when one exists:

- participant briefing material;
- planted enterprise artifacts;
- scenario-local synthetic credentials;
- synthetic AI target data;
- pack-local service source;
- model artifact fixtures;
- objective/oracle fixtures;
- reference-triangle source roots.

All generated data remains synthetic. Provenance, licensing, safety, and review
status stay in [`provenance-ledger.yaml`](provenance-ledger.yaml).
