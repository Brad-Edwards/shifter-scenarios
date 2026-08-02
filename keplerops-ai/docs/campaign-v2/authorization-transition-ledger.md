# Authorization Transition Ledger

## Authority

This ledger is authoritative for every participant-earned identity, credential,
role, ACL or execution context. `operation-prerequisite-graph.md` is
authoritative for which prior operation an operation consumes. An operation not
listed below changes no authorization: it uses only its graph prerequisites and
creates an artifact, observation or state transition.

Implementation records every transition in normal AD, Keycloak, application,
Kubernetes or external-provider audit state. No score event or campaign
controller grants access.

## Start State

| Actor/credential | Allowed | Denied |
|---|---|---|
| Cinder participant local account on `kali01` | Desktop, browser, TTY, Internet, mission, public KeplerOps DNS, Cinder service links | KeplerOps employee/partner apps, range host/control plane, other ranges |
| Cinder Jupyter entitlement | Own workspace and training queue after `kep-m06-l` activation | Other participants, KeplerOps storage, shared inference administration |
| GLM entitlement | OpenCode and OpenAI-compatible GLM 5.2 requests under own user/range identity | Other users' requests/logs, victim credentials, pool administration |

## Earned Transitions

| Earned by | Actor and credential | Native granting event | Exact allowed resource/actions | Explicit adjacent denial | Persistence/reset |
|---|---|---|---|---|---|
| `kep-m06-n` | Cinder domain owner, Stalwart mailbox and PowerDNS API account | Registrar workflow creates zone, mailbox, certificate and ownership records | Own Cinder zone, mail identities and domain-bound services | KeplerOps/other-range DNS and mail administration | Persist; full reset deletes zone/account |
| `kep-m06-u` | Cinder Knative namespace credential | Forgejo Actions deploys signed participant image revision | Own namespace service/revision, domain route, logs and secrets | Cluster, victim namespaces and other Cinder namespaces | Successful revision persists; failed revision is replaceable |
| `kep-m06-v` | Participant-selected LiteLLM route credential and Cinder Knative service identity | Forgejo Actions builds the participant's pinned OSS LiteLLM source, Harbor records its immutable digest, and the Cinder publisher deploys that digest to the participant's TLS domain | Operate the participant's own model-proxy route over the scoped shared GLM entitlement and inspect its own source, revision and route state | Other Cinder routes, KeplerOps model endpoints, other ranges and shared inference-pool administration | Accepted revision persists; full reset removes the service and rotates its route credential |
| `kep-m01-j` | `svc-orion-integration` job token plus execution in `integration01` | Vulnerable Langflow job hands artifact to live integration worker | Current job, handoff prefix, Preview metadata, integration namespace read | Other jobs, model objects, secrets, arbitrary Kubernetes actions | Successful grant reissued equivalently if worker rebuilds |
| `kep-m02-h` | Keycloak partner user and named Nextcloud room ACL | Zammad intake accepts document and invokes normal partner invitation | Own ticket, partner WorkHub project, one room/share, cited triage record | Employee apps, other rooms/tickets, engineering/data/platform zones | Invitation/room persist |
| `kep-m02-j` | `partner-reviewer` Keycloak organization membership | Synthetic recipient accepts trusted mail/media thread and sends invitation | Own mail thread, review portal, evaluation onboarding, common review queue, Preview query policy | Employee AD groups, release signing, other partner records | Accepted thread/invitation persist or are reissued |
| `kep-m02-k` | Real `orion.package-review` WorkHub capability plus local execution as the assigned review user | Recipient opens participant URL in real Chromium/local agent and vulnerable 0.1.26 returns the capability | One private WorkHub project and its completed review issue | Other projects, root/sudo, domain admin, host/cell control | Accepted bounded identity and native issue survive disposable rebuild |
| `kep-m02-l` | Forgejo external contributor and package-review token | Accepted partner package review creates team membership | Own contribution repository/package namespace, CI status and bounded review metadata | Internal source outside assigned repository, registry release, signer | Membership/token persist; rotate to equivalent scope |
| `kep-m02-m` | MCP catalog-owner token | Compatibility worker accepts exact participant endpoint/version | Own catalog record/version, assigned fixture and compatibility traces | Other tools, victim credentials outside invocation, production agent config | Accepted record/token persist |
| `kep-m03-i` | Evaluation-reader Keycloak/local application role | Recovered stale runbook credential authenticates through normal login | Named evaluation onboarding, public/visible test metadata and vision privacy research interface | Hidden labels, model objects, release and write paths | Seeded account/session can be reissued |
| `kep-m05-h` | Rendered MLflow application token | `kep-m05-g` resolves the private rendered deployment value | Named MLflow experiment/run/artifact read | MinIO direct access, other MLflow projects, Airflow, Harbor | Token persists until full reset; browser/API sessions retry normally |
| `kep-m05-i` | Recovered support-user application session | Imported bounded cookie validates against exact application | Assigned support user's own Orion conversations and shared thread | Password, AD-wide access, other users, admin/settings | Durable session artifact; reset reimports same scope |
| `kep-m05-j` | Airflow viewer credential | Participant recovers ordinary notebook history residue | Named Orion DAG definitions, run history and logs | Trigger/edit, connections, variables, other DAG groups | Persist; rotate to equivalent viewer scope |
| `kep-m05-k` | Harbor review-project robot credential | Accepted MCP tool returns its real invocation credential | Pull/push in `orion-review/staging`, inspect tags/digests | Release project, signer, unrelated repositories | Persist; rotate to equivalent project scope |
| `kep-m05-l` | Compromised `svc-orion-trainer` application/Kubernetes workload token | MLflow 2.8.1 worker exploit reads the live projected credential | Read approved training/source data; contribute Label Studio rows and `training/contrib` lakeFS/DVC branches; write own MLflow runs/candidates; query teacher through training API; submit named support-export Airflow DAG writing only `egress-staging/{range}` | Hidden evaluation labels, arbitrary MinIO prefixes, signer key/API, OPA approve, Argo, business systems, Kubernetes control | Successful token checkpoint persists; worker rebuild reprojects equivalent claims |
| `kep-m08-k` | Partner Preview teacher-query entitlement | Review onboarding enables version-bound prediction export | Bounded normal Preview queries and own prediction export | Bulk victim data/model download, hidden tests, other users' predictions | Entitlement and exports persist |
| `kep-m03-b` | Trusted external upstream maintainer/release key | Useful benign release is adopted and maintainer trust is recorded | Own public package/model project, signed releases and update proposals | Victim internal repos, registries and deployment | Trust/release key persist |
| `kep-m05-e` | Internal MCP tool deployment identity | Accepted external contribution passes CI and normal catalog promotion | One internal tool source/image/config revision and its own deployment | Other agent tools, signer, unrelated secrets | Accepted version persists |
| `kep-m05-m` | Agent-config contributor revision | Compromised trainer/tool path submits signed GitOps change | Named agent deployment configuration and participant tool binding | Other applications/namespaces, cluster administration | Accepted revision immutable; failed reconciliation resets locally |
| `kep-m05-n` | Rogue agent Kubernetes service account | GitOps creates participant-defined agent workload | Own pod, assigned queues/tools and bounded workload identity | Node, other namespaces, release signer and arbitrary secrets | Workload persists until full reset; failed pod is recreated |
| `kep-m05-o` | Assigned review-user host shell | Participant tool escapes local agent sandbox and connects to Cinder relay | Review user's processes/files/cache and fresh commands on `review01` | Root, node/hypervisor, other workstations and management network | Successful execution evidence persists; disposable guest may rebuild |
| `kep-m09-h` | Public Forgejo/Harbor model publisher | Participant signs and publishes exact compromised artifact | Own public model project, immutable release and OCI/LFS objects | Victim internal registry, other public projects | Release/digest persists |
| `kep-m09-l` | Harbor staging tag writer | `kep-m09-k` review adoption plus `kep-m05-k` robot credential | Replace the one trusted staging tag and inspect its reconciliation | Release project, immutable retained versions, production canary | Successful replacement is retained as earned state |
| `kep-m09-a` | Candidate owner acting through compromised trainer credential | Normal candidate registration accepts `kep-m09-b` report and exact digests | Create own MLflow candidate and Harbor candidate image/compatibility label | Existing candidates, signer, approval, arbitrary release manifests | Candidate/digests immutable |
| `kep-m09-f` | One-candidate promotion capability in signed release record | `svc-orion-release` obtains `svc-orion-signer` signatures after OPA accepts c/d/e decisions | Ask release service to promote exactly the signed model/image digests to the designated canary once | Edit Git, another application/digest, call signer directly, reuse after success | Capability consumed; signed record persists |
| `kep-m09-g` | Participant-visible canary runtime/audit access | Release service uses scoped capability and Argo CD reconciles | Health, benign inference and scoped runtime inventory for exact candidate | Kubernetes administration, other applications and secrets | Running revision/checkpoint persists |
| `kep-m10-c` | `svc-orion-canary` pod execution | Digest-linked embedded code executes during normal load/inference | Current serving pod processes/files and bounded business-tool token | Kubernetes node/control plane, other pods/namespaces, signer | Pod can be replaced; successful causal evidence persists |

## Authorization Test Generation

For each row, implementation emits tests from the same manifest:

1. create or recover the actor only through the named operation;
2. perform one allowed native API/UI action;
3. deny one other resource in the same application;
4. deny one adjacent application's audience;
5. prove another range's equivalent resource cannot be resolved or addressed;
6. retry/reissue without broadening claims; and
7. verify teardown removes the principal, credential, local cache and durable
   range state.

An operation consuming a transition must name the actor in its QA preconditions.
The graph, this ledger and application provisioning manifest are reconciled
mechanically before candidate bake.
