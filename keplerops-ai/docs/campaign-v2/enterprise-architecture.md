# KeplerOps AI Systems Enterprise Architecture

## Architecture Objective

The range represents a small but functioning frontier AI company. It must be
credible before any vulnerability or flag is added: identities authenticate,
mail is delivered, employees use workstations, documents move through review,
code builds, data is versioned, models train and evaluate, releases are signed,
GitOps deploys them, production decisions reach business systems, and operators
can observe the whole path.

The campaign is implemented by introducing bounded weaknesses and synthetic
content into that baseline. A challenge-specific application, proof broker, or
one-container-per-operation topology is forbidden.

## Company And Product Model

KeplerOps AI Systems builds **Orion**, an internal AI platform used for release
risk classification, research assistance, support triage, and controlled
business automation.

Orion has three real model families:

1. **Orion Release Risk** is a compact eight-class text classifier. It supports
   ontology discovery, adversarial examples, poisoning, training, evaluation,
   distillation, release compromise, and production activation on modest
   compute.
2. **Orion Assistant** is a pinned OSS instruction model behind per-range RAG,
   prompts, memory, tools, and workflow state. It supports prompt, retrieval,
   agent, rendering, data-leakage, and business-workflow operations.
3. **Orion Vision Prototype** is a small fixed 64-by-64 classifier with a
   deliberately exposed confidence-vector research interface. It supports a
   real, calibrated model-inversion operation without pretending that a text
   model reconstructs images.

The participant-side GLM 5.2 service is Cinder Typhoon infrastructure, not an
Orion model and not part of KeplerOps.

## Logical Network

Each range cell receives the same address plan under a Shifter-assigned range
prefix. The labels below are security zones and routing contracts, not separate
GCP VPCs.

| Zone | Purpose | Inbound policy | Egress policy |
|---|---|---|---|
| `cinder` | Kali, attacker mail, Forgejo, MinIO, Jupyter, relay, OpenCode | Participant and explicit victim callbacks | Internet plus published victim surfaces; no implicit internal route |
| `public` | KeplerOps website, DNS, mail edge, public Forgejo, Preview, partner intake | Internet/participant on declared protocols | Named application backends only |
| `identity` | Samba AD DCs, Keycloak, internal DNS/NTP | Domain members and named applications | Directory replication, mail, audit only |
| `corp` | WorkHub, Nextcloud, Zammad, employee mail, business applications | SSO users and named service accounts | Identity, data, mail, AI APIs, telemetry |
| `engineering` | Forgejo, CI, package registries, JupyterHub, Label Studio, Airflow, MLflow | Engineering identities and workflow services | Data, registry, Kubernetes, telemetry |
| `data` | MinIO, lakeFS/DVC state, Qdrant, PostgreSQL, RabbitMQ | Named application and pipeline identities | Backup/checkpoint and telemetry only |
| `platform` | Harbor, k3s, KServe, Orion runtimes, OPA, Argo CD, signing | Release and runtime identities | Data, model inference pool, business tools, telemetry |
| `business` | Odoo, Ghost, Mautic, synthetic customer mailboxes | Named workflows and bounded participant-earned access | Mail and telemetry; no public Internet egress |
| `observe` | OpenTelemetry, Jaeger, Prometheus, Grafana, OpenSearch | Telemetry writers and scoped viewers | No application-control path |
| `hardware` | labgrid coordinator/exporters and real benches | Reserved participant and QA sessions | Bench control, live video, telemetry only |

Default routing is deny. Public services do not gain broad access to corporate,
engineering, data, or platform zones. Cinder-to-internal access appears only
through participant-earned sessions, identities, callbacks, or application
paths described by the prerequisite matrix.

## Placement Model

The logical enterprise is stable even if Shifter changes its materialization.
The golden build uses the following roles so it is practical to build and later
portable to a denser backend:

| Compute role | Required form | Contents |
|---|---|---|
| `cell-slot` | Per-range logical slot on a backend-managed nested host | Containerized public, corporate, engineering, data, business, and observability services on isolated bridges and volumes |
| `dc01`, `dc02` | Two per-range Samba AD DC instances | Real AD forest, DNS, Kerberos, LDAP, replication, machine and service identities |
| `k3s01` | Per-range nested VM or equivalent isolated node | Real k3s, KServe/runtime workloads, Argo CD, OPA, canary production state |
| `kali01` | Per-range participant desktop VM | Kali, Chromium, terminal, OpenCode, mail and campaign tooling |
| `review01` | Per-range disposable domain member VM | Browser, local coding/computer-use agent, package/model loaders, user-execution operations |
| `integration01` | Per-range disposable worker VM or strong process-isolation boundary | Public submission analysis/integration and sandbox-evasion operations |
| `inference-pool` | Shared event service | GLM 5.2 attacker endpoint and admitted pinned victim foundation-model endpoints, with range identity and request separation |
| `hardware-pool` | Shared physical service | Multiple labgrid places, real consumer devices, live cameras, actuators, power and position controls |

The two DCs and disposable workstations are separate nested failure/security
boundaries, not decorative containers. Multiple cell slots may be packed on one
large outer host under `materialization-and-scale-contract.md`; the table does
not require seven cloud instances per range. Most applications may share their
cell slot because their isolation requirement is application and network
tenancy, not a fictional host count. k3s remains real because the
participant operates against Kubernetes, KServe, GitOps, registry, and pod
state.

## Service Inventory

### Identity And Core Enterprise

| Capability | OSS implementation | Normal role |
|---|---|---|
| Active Directory forest | Samba AD on `dc01` and `dc02` | `CORP.KEPLEROPS.LAB`, Kerberos, LDAP, DNS, users, groups, computers, service principals |
| Web SSO and partner identity | Keycloak federated to Samba AD | OIDC/SAML, service accounts, partner invitations, scoped sessions |
| Time and internal DNS | Samba DNS plus Chrony | Domain discovery and Kerberos-valid time |
| Public/Cinder DNS | PowerDNS Authoritative | Public and participant-owned zones, separate from AD DNS |
| Mail | Stalwart Mail Server | Employee, service, Cinder, notification, and synthetic-recipient SMTP/IMAP state |
| Webmail | Roundcube | Participant and employee mail interaction |
| Reverse proxy and PKI edge | Caddy plus step-ca | TLS, named virtual hosts, range-local trust |
| Employee/reviewer desktop | Linux desktop joined with realmd/SSSD | Kerberos login, browser, local agent, package and model review |

Samba is used as an actual Active Directory domain controller, not as a flat
LDAP directory. Both DCs advertise AD DNS, LDAP, and Kerberos SRV records and
replicate directory state. Keycloak federates employees and groups from AD and
keeps external partners in a separate local organization boundary.

### Collaboration And Business Operations

| Capability | OSS implementation | Normal role |
|---|---|---|
| WorkHub | Redmine | Projects, release issues, approvals, runbooks, handoffs, status records |
| Files and rooms | Nextcloud | Partner rooms, review documents, protected bundles, source material |
| Support | Zammad | Public intake, support cases, attachments, exports, synthetic user impact |
| Accounting | Odoo Community | Isolated subsidiary customer ledger and credit-note workflow |
| Public incident site | Ghost | Range-public stakeholder statements, revisions, RSS |
| Advisory campaigns | Mautic | Cohort selection, campaigns, delivery reports |

`WorkHub` is the company-facing name for a normal Redmine deployment. Its data
model and UI remain Redmine; no challenge dashboard or bespoke action panel is
added.

### Engineering, Data, And AI Lifecycle

| Capability | OSS implementation | Normal role |
|---|---|---|
| Source and public projects | Forgejo | Code, issues, releases, LFS, public client and model projects |
| CI | Forgejo Actions runners | Tests, package builds, model-image builds, release jobs |
| Public integration flow | Langflow | Real pinned public flow and integration-worker handoff |
| Assistant UI | LibreChat | Normal chat, citation, conversation and tool visibility |
| Python and Node registries | devpi and Verdaccio | Internal-compatible package supply chains |
| Container registry | Harbor | Review, staging, and release images with immutable digests and mutable labels |
| Workspace | JupyterHub | Persistent research, attack analysis, data and model notebooks |
| Annotation | Label Studio | Versioned labels, prediction-assisted review, teacher-query route |
| Object and dataset state | MinIO plus lakeFS and DVC metadata | Models, datasets, manifests, branches, snapshots, exports |
| Retrieval | Tika, Tesseract, GROBID, Haystack, Qdrant | Extraction, OCR, citation metadata, chunking, indexing, retrieval |
| Orchestration | Airflow | Intake, training, evaluation, privacy audit, export, and campaign jobs |
| Experiment/model registry | MLflow | Runs, metrics, models, aliases, lineage and intentional vulnerable worker lane |
| Runtime | k3s, KServe, vLLM/ONNX Runtime/Triton as appropriate | Orion Preview, review, canary, and production inference |
| Model gateway | LiteLLM | Per-range routing to local or admitted shared inference with no campaign state |
| Participant serverless | Knative Serving | Cinder relay and model-front revisions in the participant namespace |
| Agent runtime | LangGraph plus MCP SDK services | Release, research, support, and data-steward agents |
| Policy | Open Policy Agent | Approval, tool, release, and business-action decisions |
| Signing | Cosign, step-ca, and Rekor-compatible transparency service | Model, image, and in-toto release statements |
| Deployment | Argo CD | Signed GitOps reconciliation to the production canary |
| Evaluation | Inspect AI, pytest, ART/Foolbox, Great Expectations | Visible gates, attack verification, privacy, fidelity, and data validation |
| Queues | RabbitMQ and Celery | Intake, review, agent, mail, evaluation, and bounded resource jobs |

### Observability

| Capability | OSS implementation | Normal role |
|---|---|---|
| Distributed tracing | OpenTelemetry Collector and Jaeger | Cross-service request, agent, tool, model, and workflow causality |
| Metrics and alerting | Prometheus, Alertmanager, Grafana | Availability, inference, queue, and operation metrics |
| Searchable audit | OpenSearch | Append-only application, identity, release, and campaign events |
| Cost attribution | OpenCost | Per-tenant request and compute accounting |

Observability is participant-visible only through scoped normal views. It may
prove joins but cannot expose hidden answers, raw protected data, or a universal
campaign timeline.

## Orion Runtime Boundaries

Every model call records:

- range, tenant, user or service principal;
- application, prompt, retrieval and tool revisions;
- model and serving-image immutable digests;
- decoding configuration and seed where supported;
- request, trace, source and output identifiers; and
- token, latency and compute measurements.

The assistant application owns prompts, RAG sources, memory, tool schemas, and
business workflow state per range. A shared inference pool receives only the
resolved prompt/request and returns model output; it never owns participant
flags, victim ACLs, campaign state, or mutable range content.

Release Risk, the vision prototype, malicious candidate images, and canary
artifacts remain per range. Small deterministic models run locally on CPU where
possible. Shared accelerators are reserved for GLM access, admitted foundation-
model inference, and scheduled training/evaluation jobs that cannot meet the
operation contract on CPU.

## Challenge-Critical Automation

Ambient simulated users are deferred. The baseline includes only deterministic
workers required to complete real workflows:

- a mail recipient that reads, replies, opens, plays, and invites through real
  Stalwart, Roundcube/Chromium, and Keycloak state;
- a review worker that opens requests, downloads artifacts, runs a local agent,
  installs packages, and loads models through the visible queue;
- a support preview browser that renders an actual draft before dispatch; and
- ordinary scheduled pipeline, notification, evaluation, and reconciliation
  workers.

Each worker has a documented business role, input queue, maximum response time,
fixed software/model configuration, visible traces, and bounded actions. It
does not inspect flags, ATLAS mappings, challenge IDs, participant intent, or
hidden answer strings.

## Physical Hardware Boundary

The physical operation uses labgrid's real coordinator/exporter/place model.
Each place contains:

- one real consumer AI-enabled device or display;
- live UVC video showing device and actuator state;
- serial, network, or USB access required by the device;
- remotely controllable power;
- a real light, optical filter, camera-position, or display-angle actuator; and
- immutable bench identity and calibration records.

Participants acquire a place, operate it live, release it, and receive only the
logs and media produced during their reservation. Pre-recorded video, uploaded
sensor data, mocked hardware APIs, or a software-only twin cannot satisfy
`AML.T0041`, `AML.T0008.001`, or `AML.T0008.003`.

The event-critical route does not depend on hardware capacity. Full-catalog
participants use a queue backed by multiple interchangeable places. Capacity
is an event-operating decision; semantics do not change when the pool grows.

## Scale And Isolation Contract

The architecture is intended to be materializable as 200 isolated Shifter
cells without creating one GCP VPC, one GPU, or one physical bench per range.

- Range networks are repeated subnets/overlays within backend-managed network
  collections, not independent cloud VPCs.
- Firewall policy is expressed by zone/service templates and security groups,
  not thousands of bespoke per-operation rules.
- Range state stores use unique tenant, bucket, database, realm, namespace, and
  object prefixes plus credentials that cannot address another range.
- Shared inference authenticates the range and keeps request/log namespaces
  separate; it holds no flags or mutable victim state.
- Shared physical resources are leased exclusively through labgrid places.
- Stateful range services, AD, mail, participant identities, challenge
  artifacts, flags, and business effects are never shared across ranges.
- A range can be destroyed without deleting shared model weights or affecting
  another range, and a shared-service failure cannot grant cross-range access.

This is a backend materialization contract, not a Shifter implementation plan.
The golden range proves the same logical boundaries and participant paths that
the production backend must later realize. Exact isolation classes, resource
envelopes and 200-slot acceptance tests are in
`materialization-and-scale-contract.md`.

## Baseline Acceptance Gate

Before challenge content is layered, the enterprise build must prove:

1. both AD DCs replicate and answer DNS, LDAP, and Kerberos correctly;
2. domain users log into a joined workstation and obtain Kerberos tickets;
3. Keycloak federates AD users/groups and all named applications enforce their
   mapped roles;
4. external and employee mail supports real threaded messages and attachments;
5. the public website, client repository, Preview, partner intake, and mail
   edge work from fresh Kali;
6. a document moves from intake through extraction, indexing, assistant triage,
   WorkHub, and a Nextcloud room;
7. source commits build packages and images through CI and enter the registries;
8. labels export into versioned data, a real training job produces weights, and
   MLflow records complete lineage;
9. visible evaluation, policy, signing, GitOps, KServe, and runtime identity
   agree on immutable model and image digests;
10. one Orion decision produces each bounded business workflow in its normal
    clean state;
11. tracing, metrics, logs, alerts, and cost records correlate the real event;
12. attacker GLM, mail, domain, MinIO, Jupyter, relay, and workstation surfaces
    work independently of KeplerOps;
13. disposable review/integration workers rebuild without changing earned
    enterprise state; and
14. one labgrid place can be acquired, operated live, observed, and released.

Only after this gate passes may vulnerability pins, poisoned content, flags,
or participant-earned ACL changes be applied.

## Architecture Lineage

- Samba's AD DC guidance establishes AD DNS/Kerberos behavior and recommends
  multiple DCs: <https://wiki.samba.org/index.php/Setting_up_Samba_as_an_Active_Directory_Domain_Controller>
- Keycloak's server guide documents LDAP/Active Directory federation,
  Kerberos, OIDC/SAML, groups, roles, sessions, and service accounts:
  <https://www.keycloak.org/docs/latest/server_admin/>
- k3s supplies a real lightweight Kubernetes control plane and node model:
  <https://docs.k3s.io/architecture>
- labgrid documents remote exporter/coordinator/place acquisition for real
  hardware: <https://labgrid.readthedocs.io/en/v25.0/overview.html>
- Argo CD's declarative model anchors GitOps state:
  <https://argo-cd.readthedocs.io/en/stable/operator-manual/declarative-setup/>
