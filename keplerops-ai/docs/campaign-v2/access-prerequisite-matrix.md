# Access And Prerequisite Matrix

## Purpose

The participant never receives a generic "internal access" grant. Every
foothold earns a named identity or artifact with explicit service scope. This
matrix connects the Act 3 routes to discoverable Act 4 work and prevents hidden
access assumptions.

The logical grants below are architecture requirements. The enterprise design
must realize them through normal directory groups, application roles, service
accounts, invitations, repositories, and sessions.

## Act 3 Route Grants

| Route | Earned principal or asset | Exact initial scope | Accessible continuation | Intermediate continuation | Later branch value |
|---|---|---|---|---|---|
| `kep-m01-i` then `kep-m01-j` | `svc-orion-integration` job token and integration-worker execution | Current integration job, artifact handoff, scoped Kubernetes namespace read, Preview service metadata | `kep-m05-f` private blueprint drift lead | `kep-m04-g` runtime-to-artifact lineage | Model pipeline and worker credential branch |
| `kep-m02-h` | External partner identity, Nextcloud review room, indexed document and collection IDs | Own partner room, cited triage answer, own ticket, bounded shared review material | `kep-m03-g` cited source inventory | `kep-m03-h` Qdrant-chunk-to-object provenance | RAG, data, and contribution branch |
| `kep-m02-i` then `kep-m02-j` | `partner-reviewer` Keycloak identity and private review-window context | Partner portal, own mailbox thread, WorkHub partner space, evaluation onboarding, published service catalog | `kep-m04-f` normal compatibility batch | `kep-m08-k` fresh Preview prediction export | Human trust, teacher access, and release-review branch |
| `kep-m02-k` | Disposable reviewer-workstation execution plus real bounded `orion.package-review` capability | Reviewer WorkHub identity, local agent workspace, package-review queue, private project metadata | `kep-m05-j` notebook residue lead | `kep-m05-i` session-in-trace investigation | Identity, endpoint, and agent branch |
| `kep-m02-l` | External contributor identity, package-review token, Forgejo contribution repository | Own package namespace, assigned repository, CI result, bounded developer-review status | `kep-m05-f` private/public configuration lead | `kep-m05-g` private trust-boundary investigation | Software and model supply-chain branch |
| `kep-m02-m` | Agent-tool catalog token and accepted attacker-hosted tool | Own catalog record, compatibility traces, bounded integration fixture, tool version history | `kep-m04-j` catalog capability trace | `kep-m05-k` tool credential behavior | Agent-tool poisoning and release-assistant branch |

## Grant Composition

The complete campaign expects participants to perform all Act 3 operations,
but no single route may strand them. Each successful route exposes at least one
Accessible and one Intermediate Act 4 continuation. Those continuations reveal
why other footholds remain valuable rather than pretending one token opens the
entire company.

Grants compose through ordinary identity and application behavior:

- directory identities acquire additional groups only through invitations,
  role assignments, or recovered authorization material;
- service-account tokens remain scoped to their namespace and workload;
- browser sessions do not automatically reveal underlying passwords or service
  tokens;
- repository and package tokens authorize only their documented namespace and
  workflow;
- catalog tokens authorize only owned tool records and compatibility runs; and
- workstation execution provides the local user's sessions and files, not a
  universal company credential.

## Exact Discovery Rules

Every continuation has an in-world clue available within the earned scope:

| Continuation | Starting clue | Expected participant inference |
|---|---|---|
| `kep-m03-g` | Triage answer cites a protected source inventory URI | Follow the normal citation and inspect what sources back the answer. |
| `kep-m03-h` | Source inventory names a Qdrant collection and document | Retrieve the cited chunk metadata and derive the no-list object key. |
| `kep-m04-g` | Integration handoff names the serving run and namespace | Join process, service, MLflow source, and object digest. |
| `kep-m05-f` | Public blueprint digest differs from the integration or contribution record | Locate the owning private configuration and generate a real drift comparison. |
| `kep-m05-g` | Drift report names the private trust boundary and owning deployment | Investigate the private capability or credential exposure without searching a manifest for a flag. |
| `kep-m05-h` | The `kep-m05-g` drift path exposes a rendered MLflow application token with explicit audience and scope | Test that exact token only against MLflow, then verify adjacent audiences reject it. |
| `kep-m05-i` | Reviewer trace references a browser session artifact | Recover and validate the session through the normal application. |
| `kep-m05-j` | Reviewer workspace history identifies a prior notebook mount | Inspect the ordinary local residue under the compromised user. |
| `kep-m05-k` | Catalog trace shows which credentials a tool receives at invocation | Invoke the accepted tool and observe its real credential boundary. |
| `kep-m08-k` | Partner review page documents the Preview revision and query policy | Make and export one fresh revision-linked prediction. |

## Identity And Session Durability

Successful route state follows `campaign-state-contract.md`:

- accepted identities and grants persist;
- disposable recipient and reviewer environments may be rebuilt;
- an earned browser session may be reissued through a durable attacker-visible
  artifact when its workstation is reset;
- accepted documents, packages, tools, repositories, rooms, mail threads, and
  collection IDs persist; and
- failed attempts cannot revoke or overwrite a prior successful route.

## Architecture Acceptance Gate

Before the enterprise architecture is accepted, every row above must map to:

1. an exact directory group, application role, token audience, or session;
2. the owning OSS service;
3. provisioning source and initial ACL;
4. the operation that earns it;
5. the normal record that proves it was earned;
6. reset and reissue behavior; and
7. at least one participant-equivalent authorization test and one denied
   negative test.
