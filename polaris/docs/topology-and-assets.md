# Polaris topology and asset design

This is the Polaris operator design. The canonical logical topology is
`sdl/polaris-operation-northstorm.sdl.yaml`; this document explains its
realization plan but does not define a second topology.

Polaris remains `draft`. A source binding means implementation material exists,
not that the component has passed participant-equivalent live proof.

## Logical range boundary

Every mutable path-critical component is owned by one `range_id` and
participant namespace. The repeated `boreas.local` name is safe only because
each range owns its forest, DNS answers, routes, splice state, content state,
objective receipts, and reset lifecycle.

| SDL network id | Logical CIDR | Start-state membership | Route policy |
| --- | --- | --- | --- |
| `shared-net` | `172.20.0.0/24` | A0, DNS, A14 | Range-local OSINT and participant access only. |
| `corporate-net` | `172.20.10.0/24` | DNS, A1, A2, A3, A4, A14, A15, A16 | A14 may reach corporate services; no implicit route to lab, SCADA, bunker, or splice. |
| `lab-net` | `172.20.30.0/24` | DNS, A6, A7, A8, A16 | A16 is the only corporate-to-lab pivot. |
| `scada-net` | `172.20.40.0/24` | A5, A15 | A15 is the only corporate-to-SCADA pivot. |
| `bunker-ot-net` | `172.20.50.0/24` | A9–A13 | Internal; A9 is the only entry. |
| `splice-link` | `172.20.60.0/24` | A9 at boot; A14 after the local blackout | Closed at start. The range-local A5 terminal state authorizes A14 attachment; reset removes it. |

Missing routes are denied. The event profile tests representative allowed
and denied flows before and after the splice transition. A DNS name is the
stable participant binding when a provider cannot preserve a logical address;
provider addresses never create new logical asset ids.

## Component inventory

The source column names the current single owner. `build/` is a realization
input; it must not become a second authored-content store during reorganization.

| SDL id | Role and required real services | Current source/content owner | Event-profile realization and status |
| --- | --- | --- | --- |
| `a0-boreas-web` | Public Boreas site and OSINT files over HTTP | `build/a0/`; `content-packages/polaris/{boreas-org-chart,boreas-annual-report,boreas-dns-zone}/` | Range-local Linux web service with deterministic planted files. |
| `dns-boreas` | Authoritative range DNS | `build/dns/`; `boreas-dns-zone` package | Range-local DNS on shared, corporate, and lab networks. Source exists; all records must resolve only inside the owning range. |
| `a1-mail` | SMTP, IMAP, and webmail | `build/a1/`; `content-packages/polaris/mail-seed/` | Real mail services with seeded synthetic mailboxes. Source exists; initialization and reset must be deterministic. |
| `a2-dc01` | BOREAS Windows AD DS, DNS, Kerberos, LDAP, SMB, GC | `aws-range/a2_*.ps1`, bootstrap scripts, and `boreas-ad-seed` | One real Windows Server 2022 forest/DC per range. Shared forests and Samba are forbidden substitutes. |
| `a3-intranet` | Boreas intranet HTTP application | `build/a3/`; `intranet-env` package | Range-local application with its intentional weaknesses and data seeded by the build. |
| `a4-fileshare` | SMB shares and ACLs | `build/a4/`; `content-packages/polaris/smb-share/` | Real SMB service with Public, HR, Procurement, IT, and Executive share state restored by reset. |
| `a5-scada-gw` | HMI and Modbus interlock | `build/a5/`; `scada-hmi-json` and service source | The fictional NORTHSTORM generator service used in the live event range; it is not represented as a real vendor product or hardware twin. |
| `a6-eng-ws01` | SSH engineering workstation and planted research material | `build/a6/`; Tanaka, MIDNIGHT-7, Nielsen, Jenkins, and deleted-video packages | Range-local workstation reached only through A16, with identities, permissions, tools, and artifacts created at build time. |
| `a7-git` | Gitea repositories | `build/a7/`; `content-packages/polaris/gitea-seed/` | Real Gitea, attached only to `lab-net`, initialized without manual database registration. |
| `a8-research-db` | PostgreSQL research compartments | `build/a8/`; `content-packages/polaris/research-db-seed/` | Real PostgreSQL with deterministic roles, grants, procedures, and data. |
| `a9-splice-landing` | SSH gateway into bunker OT | `build/a9/` and splice-watcher inputs | Range-local gateway on bunker and splice networks. Its participant key must be delivered by file/secret binding, never Compose environment or operator output. |
| `a10-tail-ctrl` | Tail Modbus controller state | `build/a10/`; `modbus-tail-registers` | Fictional NORTHSTORM controller with resettable register state. |
| `a11-leg-ctrl` | Leg Modbus controller state | `build/a11/`; `modbus-leg-registers` | Fictional NORTHSTORM controller with resettable gait state. |
| `a12-arms-ctrl` | Arms Modbus controller state | `build/a12/`; `modbus-arms-registers` | Fictional NORTHSTORM controller with resettable nonce state. |
| `a13-brain-main` | NORTHSTORM controller protocol and objective state | `build/a13/`; `brain-protocol-seed` | Fictional range-local controller service. It must remain truthfully labelled and resettable; it is not a vendor simulator. |
| `a14-kali` | Participant attacker surface with SSH/RDP and offensive tools | `build/a14/`; `kali-start-here` and `kali-welcome` packages | One range-scoped participant environment exposed through ephemeral key-authenticated SSH/RDP. |
| `a15-ops-eng01` | Corporate/SCADA operations workstation | `build/a15/`; `scada-hmi-json` | Exclusive SCADA pivot. The build creates the local account, intentional elevation path, SCADA client material, and both network attachments. |
| `a16-research-analyst01` | Corporate/lab analyst workstation | `build/a16/`; A16 entrypoint content | Exclusive lab pivot. The build creates the local account, A6 key binding, PostgreSQL client material, Git tooling, and both network attachments. |

The Compose file carries inert `polaris.asset` labels. The static topology test
uses them to prove that every Compose service resolves to one SDL node and that
its network addresses match the SDL. A2 is the sole expected adjacent VM.

## Identity, credential, and tool closure

The SDL owns the stable identities: the `boreas` AD domain; the Administrator,
employee, service, Kali, Jenkins, and narrow A6 research accounts; and their
authentication or dependency relationships. The current synthetic literals and
their discoverable sources remain in `design/shared-constants.md`, component
entrypoints, and content packages under the single-owner asset rule.

The event build creates every identity and places each required credential or
derivation clue in-world. It must not require Terraform output, a generated
operator password, SSM history, a root shell, a database console, or the
repo-root `.env`. Real provider tokens and generated participant private keys
remain outside committed content and outside argv, environment dumps, tags,
logs, reports, and participant exports.

A14 must contain the tools needed by the documented path. A15 must contain the
SCADA client surface. A16 must contain SSH, Git, and PostgreSQL client
bindings. A9 must contain the bunker network tooling. Exact tool and image
versions are pinned source bindings rather than new SDL ids.

## Content, shares, and datasets

Every SDL `content` id joins to one current package owner:

- A0: organization chart, annual report, and DNS zone;
- A1: synthetic mailboxes and attachments;
- A2: AD OUs, groups, users, SPNs, privileges, and policy state;
- A3: the planted application environment file;
- A4: the share tree and ACL mapping;
- A6: simulation archives, MIDNIGHT-7 results, workbook, Jenkins material, and
  deleted encrypted media;
- A7: the seeded Gitea repositories and history;
- A8: compartment roles, procedures, records, and cryptographic material;
- A15: SCADA client configuration;
- A10–A12: resettable controller register state;
- A13: controller protocol configuration;
- A14: participant start and welcome material.

`assets/README.md` defines the ownership rule. A package is not copied: its
current source moves, all consumers change in the same slice, and the old owner
is removed. Publication and safety review remain controlled by
`docs/provenance-ledger.yaml`.

## Objective and dependency closure

The five SDL objective ids remain the topology-facing outcomes:

1. `establish-target-picture`;
2. `compromise-front-office`;
3. `extract-leviathan`;
4. `lights-out`;
5. `seize-autonomous-platform`.

The dependencies preserve the campaign shape: target picture precedes front
office; lab extraction and blackout can proceed after front-office compromise;
both are required before bunker seizure. CTFd is not objective truth. The
private oracle owns the hidden path, affordances, evidence predicates, negative
gates, and verdict logic; the flag and challenge contracts own the CTFd
projection over those verdicts.

## Final realization status

| Obligation | Current authority and status |
| --- | --- |
| Canonical topology and asset ownership | SDL plus this design; shipped. |
| Hidden path, affordances, objective oracle, and validation joins | `oracle/`, `aces_contract.py`, and `validation/`; shipped private/operator source. |
| Flag/challenge/CTFd coupled layer | `flags/`, `challenges/`, and `ctfd/`; shipped. |
| Delivery/audience bundles | `profiles/`; five supported content bundles. |
| Event build and participant entry | `build/` plus the precise `aws-range/` source indexed by the compatibility manifest; supported degraded binding. |
| Automated event-path rehearsal | `tests/aws_event_rehearsal.py` and `docs/aws-event-rehearsal-report.md`; passed. |
| Final manual participant walkthrough from A14 | `docs/walkthroughs/` and `docs/aws-event-manual-walkthrough-report.md`; passed. |
| Maturity, release boundaries, evidence, and teardown | `docs/final-reconciliation-report.md`; reconciled, with maturity retained at `draft`. |

The current `aws_event` row is a complete event runtime, not the
doctrine-complete golden profile. Until every path-critical component has its
authentic binding and that binding passes the same live proof, the pack remains
`draft`.
