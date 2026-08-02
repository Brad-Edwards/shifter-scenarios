# Canonical Component Catalog

## Authority

This catalog is the only allowed component vocabulary for campaign-v2. An
operation may not introduce a second CI system, scheduler, registry, mail
server, DNS authority, model gateway, or state store merely because an example
used it. The candidate build records the exact release and immutable image
digest for every row in one `component-lock.yaml`.

Clean-baseline versions are patched stable releases compatible with the pinned
deployment date. Intentional vulnerable versions are present only in the
reviewed `campaign-start` overlay and are named by their operation contract.

## KeplerOps Components

| Capability owner | Canonical component | Placement and durable state | Authentication contract |
|---|---|---|---|
| Employee directory, Kerberos, AD DNS | Two Samba AD DCs plus Chrony | Separate nested guests; replicated directory and DNS | AD users, computers, groups, SPNs and keytabs |
| Public and Cinder authoritative DNS | PowerDNS Authoritative | Cell containers; per-range zones in PostgreSQL | Scoped API account; never AD DNS |
| Web identity federation | Keycloak | Cell container; realm database and signing keys | AD federation, local partner organizations, OIDC/SAML clients |
| Edge TLS and web policy | Caddy, step-ca, oauth2-proxy where required | Cell containers; CA and route configuration | mTLS/service identity or Keycloak session |
| Mail transport and mailbox | Stalwart Mail Server | Cell container; per-range mail domains and mailboxes | AD-backed employees, local Cinder/partner/service mailboxes |
| Webmail | Roundcube | Cell container; no independent mailbox store | IMAP/SMTP credentials from Stalwart |
| Public web | Caddy static site | Cell container; versioned site content | Anonymous read |
| Public vulnerable integration flow | Langflow | Disposable integration boundary; campaign overlay only | Anonymous pinned flow plus internal local admin |
| Assistant UI | LibreChat | Cell container; conversation database | Keycloak OIDC |
| Project and workflow records (`WorkHub`) | Redmine | Cell container; PostgreSQL | Native AD LDAP; synchronized project roles |
| Files and partner rooms | Nextcloud | Cell container; PostgreSQL and object data | Keycloak OIDC and object ACLs |
| Support and intake | Zammad | Cell container; PostgreSQL and indexed tickets | Keycloak SAML plus public intake |
| Accounting | Odoo Community plus OCA `auth_oidc` | Cell container; PostgreSQL | Keycloak OIDC and local service users |
| Feature control | Unleash OSS | Cell container; one range-local canary project | Keycloak session and scoped canary API token |
| Public incident publishing | Ghost | Cell container; content database | Ghost local staff accounts provisioned from the communications role; public read |
| Advisory campaigns | Mautic | Cell container; campaign database | Keycloak SAML and service API token |
| Source, issues, releases, LFS | Forgejo | Cell container; repositories and database | Keycloak OAuth2 and scoped repository tokens |
| CI and builds | Forgejo Actions | Disposable runners; artifacts in Forgejo/MinIO/Harbor | Per-repository runner and job tokens |
| Dependency update proposals | Renovate | Scheduled Forgejo application | Read and pull-request rights only |
| Python and Node packages | devpi and Verdaccio | Cell containers; per-range projects | Scoped publisher/reader tokens |
| Container and OCI artifact registry | Harbor | Cell container; registry data and database | Keycloak OIDC, robot accounts and project roles |
| Research notebooks | JupyterHub | Cell container plus user kernels; persistent user volumes | Keycloak OIDC; kernels receive scoped mounted data |
| Annotation | Label Studio Community | Cell container; project database and object data | oauth2-proxy/Keycloak identity plus synchronized local project roles |
| Object and dataset versions | MinIO, lakeFS and DVC metadata | Cell containers; per-range buckets and repositories | Service/user credentials scoped by bucket, prefix and repository |
| Extraction and retrieval | Tika, Tesseract, GROBID, Haystack and Qdrant | Cell containers; queues, indexes and source metadata | Named ingestion/assistant service identities |
| Workflow scheduling | Airflow | Cell container plus disposable workers | Keycloak OAuth for users; named DAG service identities |
| Queue-backed business work | RabbitMQ and Celery | Cell containers/workers | Per-queue service credentials and vhosts |
| Experiment and model registry | MLflow | Cell container plus isolated vulnerable worker where required | oauth2-proxy for users; scoped application tokens |
| Model gateway | LiteLLM | Per-range gateway; no persistent victim prompts | Service identities and per-range upstream credentials |
| Model runtime | KServe with vLLM, ONNX Runtime or Triton selected by model family | Per-range k3s node; models read by immutable digest | Kubernetes service accounts and workload tokens |
| Participant serverless front | Knative Serving on the per-range k3s node | Participant namespace and immutable image revisions | Cinder namespace credential only |
| Agent runtime | LangGraph and official MCP SDK services | Cell/k3s workloads; per-range prompt, memory and tool state | `svc-orion-assistant` and tool-specific audiences |
| Policy | Open Policy Agent | k3s/cell service; versioned policy bundles and decisions | Named requester, approver and release service identities |
| Signing and transparency | Cosign, step-ca and Rekor-compatible service | Cell services; append-only entries and protected signer key | `svc-orion-signer` only after accepted OPA decision |
| Deployment | Argo CD | Per-range k3s | `svc-orion-release`; one signed canary application |
| Evaluation | Inspect AI, pytest, ART, Foolbox and Great Expectations | Disposable job containers | Evaluator or participant-owned job identity as declared |
| Telemetry | OpenTelemetry, Jaeger, Prometheus, Alertmanager, Grafana, OpenSearch and OpenCost | Cell containers; per-range retention | Workload writers and scoped viewer roles |
| Physical control | labgrid coordinator/exporter/place | Shared physical pool | Exclusive opaque range lease and randomized liveness |

There is no Temporal, Argo Workflows, Woodpecker, Mailpit, standalone OCI
Distribution registry, or second victim mail/CI/orchestration plane. Existing
operation prose is normalized to the owners above.

## Cinder Components

Cinder is attacker infrastructure, but still uses ordinary OSS systems:

- Kali/Chromium/terminal/OpenCode for participant execution;
- Stalwart and Roundcube for attacker mail;
- PowerDNS, Caddy and step-ca for attacker-controlled DNS/TLS;
- Forgejo and Forgejo Actions for source, manifests and independent jobs;
- MinIO and Harbor for attacker objects and OCI artifacts;
- JupyterLab kernels for analysis and model work;
- Knative Serving and LiteLLM for the participant-owned relay/model route; and
- age, Cosign and standard S3/OCI clients for transfer and provenance.

GLM 5.2 is an event-provided open-weight attacker model accessed through a
shared Vertex-backed OpenAI-compatible endpoint. For `kep-m06-v`, the
participant packages the pinned OSS LiteLLM gateway, publishes its immutable
image through Cinder Forgejo and Harbor, and deploys it on the participant's
Cinder Knative namespace and TLS domain. The front has its own route credential
and maps only `glm-5.2` to the scoped shared endpoint. Independent evaluation
joins the participant's source and live revision to a fresh successful request
at the attributed Cinder model edge; a direct shared-endpoint call does not
satisfy the operation.

LiteLLM's official gateway documentation defines its OpenAI-compatible proxy,
configuration and access-control surface:
<https://docs.litellm.ai/docs/simple_proxy>. Google Cloud documents serverless
access to open models through Vertex AI Model Garden MaaS and records the GLM
family's Model Garden availability:
<https://docs.cloud.google.com/vertex-ai/generative-ai/docs/open-models/use-maas>
and
<https://docs.cloud.google.com/vertex-ai/generative-ai/docs/release-notes>.

## Version And Admission Gate

Before a component enters `component-lock.yaml`, implementation records:

1. project and image source;
2. license and redistributability;
3. exact version and image/source digest;
4. purpose and owning workflow;
5. authentication adapter and least-privilege roles;
6. placement, ports, storage, backup and health check;
7. clean-baseline and campaign-overlay configuration diff;
8. reset, teardown and data-retention behavior;
9. resource request/limit and expected concurrency; and
10. upstream documentation and, for intentional vulnerability pins, advisory
    lineage plus participant-equivalent reproduction evidence.

An unlisted service blocks design-to-build reconciliation. A component that
cannot satisfy its operation with the real upstream software is rejected rather
than wrapped in a challenge-shaped substitute.
