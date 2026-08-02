# Identity And Access Architecture

## Identity Authority

`CORP.KEPLEROPS.LAB` is a real Samba Active Directory forest with `dc01` and
`dc02`. AD owns employee, workstation, service, and security-group identity.
Keycloak's `keplerops` realm federates AD users and groups for web applications.
External partners are Keycloak-local organization members and are never created
as AD employees.

The Cinder domain, users, mail, repositories, and services are entirely separate
from KeplerOps identity. No Shifter credential is valid in KeplerOps or Cinder
services.

Identity types are not aliases for one another:

- AD owns employee users, computer accounts, security groups, LDAP identity,
  Kerberos SPNs and service keytabs;
- Keycloak federates AD humans for web sessions and owns partner users,
  application roles, OIDC/SAML clients and short-lived web/service tokens;
- Kubernetes owns service accounts for pods and binds them to a single
  namespace/workload; a pod token is never an AD password or Keycloak human
  session;
- applications with no reliable federation support use provisioned local
  accounts with distinct random credentials and synchronized least-privilege
  roles; and
- workload identity mappings are explicit pairs in provisioning source, not
  principals inferred from matching names.

## Directory Structure

| AD location | Contents |
|---|---|
| `OU=People` | Researchers, evaluators, release engineers, support, platform, finance, communications |
| `OU=Service Accounts` | Non-interactive workload principals with named audiences and SPNs |
| `OU=Workstations` | Employee and reviewer Linux domain members |
| `OU=Servers` | Integration workers, k3s nodes, application and data hosts |
| `OU=Groups` | Role, resource, workflow, and administrative groups |

Required human-role groups:

- `GG-Orion-Researchers`
- `GG-Orion-Annotators`
- `GG-Orion-Evaluators`
- `GG-Release-Engineers`
- `GG-Release-Approvers`
- `GG-Platform-Operators`
- `GG-Support-Agents`
- `GG-Communications`
- `GG-Finance-Operations`
- `GG-Security-Auditors`

Required bounded resource groups:

- `RG-WorkHub-Orion`
- `RG-Nextcloud-Orion-Internal`
- `RG-Forgejo-Orion-Read`
- `RG-Forgejo-Orion-Contribute`
- `RG-Jupyter-Orion-Evaluation`
- `RG-LabelStudio-Orion-Contribute`
- `RG-MLflow-Orion-Read`
- `RG-MLflow-Orion-Maintain`
- `RG-Harbor-Orion-Review`
- `RG-Harbor-Orion-Release`
- `RG-Airflow-Orion-View`
- `RG-Airflow-Orion-Run`
- `RG-Release-Policy-Request`
- `RG-Release-Policy-Approve`

Groups map to application roles. Applications do not infer authorization from
email domains, display names, or possession of an unrelated session.

## Service Principals

| Principal | Audience and minimum rights | Operations that may expose or abuse it |
|---|---|---|
| `svc-orion-integration` | Integration namespace read, job handoff, Preview metadata | `kep-m01-i`, `kep-m01-j`, `kep-m04-g` |
| `svc-orion-preview` | Release Risk inference, trace write, no model-object read | Preview and adversarial-input lane |
| `svc-orion-assistant` | Named Qdrant collections and MCP tools only | Prompt, RAG, agent operations |
| `svc-orion-ingest` | Intake objects, Tika/OCR, Qdrant write | Partner and retrieval operations |
| `svc-orion-trainer` | Approved dataset reads; Label Studio contribution; training/DVC branch write; MLflow run and candidate-contributor write; bounded Airflow support-export submission; no hidden-test, signer, arbitrary bucket, Argo or business rights | Data/model poisoning, distillation, `kep-m05-l`, `kep-m08-j`, `kep-m09-a`, `kep-m10-d` |
| `svc-orion-evaluator` | Candidate read, test-set read, report write, no release sign | Visible, hidden, privacy and fidelity jobs |
| `svc-orion-release` | Policy request, manifest write, no direct signing key | Release-chain operations |
| `svc-orion-signer` | Sign only accepted exact digests | `kep-m09-f` |
| `svc-orion-canary` | Approved model read, inference, bounded business tools | Production and impact operations |
| `svc-review-worker` | Assigned queue item and disposable fixture only | User execution and package/model review |
| `svc-support-preview` | Assigned draft read and browser render only | `kep-m04-l` |
| `svc-data-steward` | Named tenant cleanup tool and protected snapshots | `kep-m10-q` |

Every token has an explicit issuer, subject, audience, scopes, lifetime, and
normal audit identity. A token for one audience is rejected by every other
service.

AD service accounts use randomly generated passwords stored only long enough to
issue keytabs, with SPNs such as `HTTP/workhub`, `HTTP/nextcloud`,
`HTTP/forgejo`, `HTTP/airflow`, and `HTTP/harbor`. Linux services run under
dedicated POSIX users and read only their own root-owned keytab. Keycloak
confidential clients use distinct IDs such as `kc-orion-release`; Kubernetes
service accounts use names such as `ksa-orion-release`. Provisioning records the
allowed AD-to-Keycloak-to-Kubernetes mapping, token exchange audience, rotation
owner and denied mappings. No shared password connects the three systems.

## Keycloak Organizations And Clients

The `keplerops` realm contains:

- federated AD employees and groups;
- one `partners` organization for invited external reviewers;
- OIDC clients for WorkHub, Nextcloud, Zammad, Forgejo, JupyterHub, Label
  Studio, MLflow proxy, Airflow, Harbor, Grafana, Ghost administration, Mautic,
  and Odoo where the application adapter below supports federation; and
- confidential service clients corresponding to the service principals above.

Partner invitations grant only:

- the participant's own partner portal and mailbox thread;
- a named WorkHub partner project;
- a named Nextcloud review room;
- public service catalog and review-window metadata; and
- operation-specific grants explicitly earned later.

No partner role maps to an AD group or generic internal user role.

## Authentication And Provisioning Adapters

| Application | Human authentication | Role/resource enforcement | Provisioning and logout |
|---|---|---|---|
| Stalwart/Roundcube | Employee LDAP bind to AD through Stalwart; partner/Cinder local mailbox identity | Mailbox and alias ACLs in Stalwart | Idempotent mailbox sync; Roundcube logout ends IMAP/web session |
| Redmine/WorkHub | Native AD LDAP | Redmine project memberships synchronized from named AD groups | Provisioning adapter creates/removes memberships; no claimed OIDC support |
| Nextcloud | Keycloak OIDC through maintained OSS login app | Native Nextcloud groups, room/share ACLs and object ownership | Keycloak back-channel logout plus local session expiry |
| Zammad | Keycloak SAML for staff/partners; anonymous public intake | Native organizations, roles, groups and ticket ownership | SAML single logout where supported; adapter reconciles organizations |
| Forgejo | Keycloak OAuth2 | Native teams, repository and package-token scopes | OAuth session logout plus team-sync job |
| JupyterHub | Keycloak OIDC via `GenericOAuthenticator` | Hub groups, named profiles, PVC and mount policy | Hub logout revokes session; kernels keep no bearer token after stop |
| Label Studio Community | Keycloak session at oauth2-proxy | Provisioned local project role and object ACL checked by the application/API gateway | Adapter creates bounded local identity; proxy logout and local session expiry |
| MLflow | Keycloak session at oauth2-proxy; application tokens for API/workloads | Gateway path policy plus MLflow experiment/artifact permissions | No claim of native OIDC; local token rotation and proxy logout |
| Airflow | Keycloak OAuth through its supported auth manager | DAG/run roles and API authorization | OAuth logout and role reconciliation |
| Harbor | Native Keycloak OIDC | Project roles, robot accounts, repository/tag permissions | OIDC logout and project-role sync |
| Grafana | Native Keycloak OAuth | Organizations, folders, data-source and dashboard permissions | OAuth logout and role mapping |
| LibreChat | Native Keycloak OIDC | Conversation ownership and server-side tool policy | OIDC logout; no client-only authorization |
| Ghost | Distinct local synthetic staff accounts | Native owner/editor roles and content ownership | Provisioned from communications assignments; native logout |
| Mautic | Keycloak SAML | Native roles, campaign ownership and API ACLs | SAML logout where supported; role sync |
| Odoo Community | OCA `auth_oidc` with Keycloak | Odoo groups, record rules and company/tenant boundary | OIDC logout and explicit group mapping |
| Langflow | Anonymous participant flow; local internal admin | Flow ID, worker boundary and internal admin role | Disposable campaign-overlay instance; no federation assumption |

Caddy/oauth2-proxy authenticates but does not silently replace application
authorization. API routes either carry a verifiable identity to an application
that enforces resource ACLs or are denied. The provisioning adapter is ordinary
infrastructure code, never a challenge success service.

## Workstations And Kerberos

`kali01` is Cinder-owned and is never domain joined. `review01` and employee
desktops are Ubuntu or Kali-derived Linux guests joined with realmd/SSSD and
PAM. A domain login creates a Kerberos credential cache owned by that user;
browser SPNEGO is enabled only for approved `*.corp.keplerops.lab` services.
Machine keytabs are root-only, local home directories and browser profiles are
per user, and sudo is denied except for named workstation support actions.

The `review01` compromise exposes only the assigned review user's files,
browser session, Kerberos cache and package/model-loader permissions. It does
not expose a domain-admin credential, another employee profile, host
virtualization, or the cell control plane. Rebuild removes the computer account,
keytabs, caches and local profile before a fresh machine account is joined.

## Mail Identity And Routing

- PowerDNS publishes per-range public/Cinder MX, SPF, DKIM and DMARC records;
  Samba DNS remains internal AD authority.
- Stalwart provisions employee addresses from AD and local external-review,
  Cinder, notification and synthetic-recipient mailboxes from source manifests.
- Employee SMTP submission uses authenticated mailbox identity; service mail
  uses a named credential and envelope allowlist. DKIM signs each domain.
- Outbound delivery is limited to range-owned/synthetic domains except for the
  participant's ordinary Internet research access. No scored operation sends
  mail to a real person or commercial mailbox.
- Challenge-critical recipients read actual IMAP messages, preserve headers and
  attachments, and reply through SMTP. Mailpit is not used.
- Thread IDs, Message-IDs, delivery status, DKIM results and recipient action
  records are visible through normal mail/application audit surfaces.

## Application Authorization

| Surface | Baseline principal | Normal scope |
|---|---|---|
| Public site/client repository | Anonymous | Published pages and artifacts only |
| Partner intake | Anonymous then partner identity | Own cases, uploads and status |
| WorkHub internal | AD employee groups | Assigned projects, issues, approvals and runbooks |
| Nextcloud | AD/partner groups | Named rooms and shares |
| Forgejo internal | AD/repository teams | Named projects and package workflows |
| JupyterHub | AD workspace group | Own persistent volume plus mounted scoped project data |
| Label Studio | Annotator/contributor role | Named project tasks and exports |
| MLflow | Reader, maintainer or service token | Named experiments, runs, aliases and artifacts |
| Airflow | Viewer or runner | Named DAGs and run actions |
| Harbor | Review or release project role | Named repository paths and tag/signature actions |
| Argo CD | Release service | Declared canary application only |
| OPA release service | Requester/approver/signer roles | Separate actions with immutable audit |
| Business systems | Human or canary service role | Named synthetic tenant and bounded actions |
| Observability | Scoped viewer | Services and traces available to the earned role |

## Foothold Grant Realization

| Route | Concrete earned state | Provisioning and proof | Reissue/reset behavior |
|---|---|---|---|
| Public-flow exploit | `svc-orion-integration` job token plus execution in `integration01` | Token minted for successful live integration job; job and token audit agree | Successful grant is checkpointed; disposable worker may rebuild and deterministically reissue equivalent scope |
| Partner document | Keycloak `partners` member plus named Nextcloud room ACL | Zammad triage creates invitation and room through normal APIs | Accepted document, invitation and room persist |
| Social/deepfake | `partner-reviewer` organization membership | Recipient browser accepts real thread/media and issues Keycloak invitation | Accepted thread and invitation persist or are reissued from the accepted recipient decision |
| Malicious link | Bounded `orion.package-review` WorkHub capability plus disposable execution | Browser/local-agent trace and 0.1.26 callback bind to one review request; the credential opens one private native project | Failed workspace/callback is removed; accepted bounded identity and issue persist |
| Malicious package | Forgejo contributor plus package-review token | Accepted reviewer job creates repository team membership and bounded token | Accepted package/repository grant persists |
| Agent clickbait/tool | Catalog-owner token plus accepted tool version | Compatibility trace and catalog record identify exact participant endpoint/version | Accepted catalog record and token persist |

## Session Contract

Participant-earned browser access must survive ordinary use:

- employee and partner SSO idle timeout: 60 minutes;
- SSO maximum session: 12 hours;
- application access token: 15 minutes with refresh token where appropriate;
- refresh/session maximum: 12 hours;
- operation-scoped service tokens: minimum 60 minutes unless the operation is
  explicitly about token expiry;
- review jobs and hardware leases have independent bounded lifetimes; and
- all timeouts are visible in normal account or audit state.

No participant-facing session silently expires in ten minutes. Services must
either share Keycloak logout/refresh semantics or clearly prompt for normal
reauthentication without losing earned state.

## Negative Authorization Contract

For every earned principal, QA must prove at least:

1. one intended allowed action;
2. one adjacent service denied by audience;
3. one same-service resource denied by role or object ACL;
4. no directory, object-store, Kubernetes, or management-plane enumeration
   beyond the operation's intended scope; and
5. reset/reissue does not broaden rights or revoke a prior successful grant.

The access-prerequisite matrix is not accepted until every logical grant has a
passing positive and denied negative test against this architecture.
