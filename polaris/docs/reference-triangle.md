# Polaris reference-triangle design

This document defines the one Polaris reference triangle:
`build/` creates the declared participant start state, `tests/` executes the
same objective path from A14, and `docs/walkthroughs/` is the manual
command-by-command form of those tests.

The event build, automated rehearsal, mandatory final manual walkthrough,
reset, teardown, and sanitized reports are shipped and reconciled.
`pack.yaml.contents.reference_triangle` is therefore `true`. The pack remains
`draft` because shipped-layer presence is not a waiver of the authenticity and
host-boundary requirements for higher maturity.

## Runtime profiles

Both profiles bind the stable ids in the canonical SDL. Neither may remove a
logical component.

### `local_degraded`

`build/docker-compose.yml` is a fast-feedback source binding. Outside the
event range it is explicitly degraded because it does not, by itself, provide:

- the real adjacent Windows Server A2 forest;
- a dedicated cloud isolation boundary;
- automated participant gateway/access handoff;
- a production splice watcher and secret-file handoff;
- participant-equivalent automated or manual proof.

Component probes and operator-driven `docker exec` remain useful diagnostics.
They do not establish objective success or golden readiness.

### `aws_event`

The live event binding is the proven compact Polaris event layout:

- one dedicated VPC, /28, route table, gateway, and security group per
  rehearsal, with participant ingress restricted to the runner's public /32;
- one range host running the complete 17-service compose topology;
- one range-local Windows Server 2022 BOREAS forest/DC;
- ephemeral key-authenticated SSH/RDP participant access to A14;
- the event-derived, digest-pinned artifact at `build/build-v1.tar.gz`;
- range-local splice credentials and a closed-at-start blackout watcher;
- pack-local provisioning, health, reset, rehearsal, and teardown source.

This profile proves the event runtime only. It is not the future
golden binding: the authored fictional OT simulations are not a
vendor-supported hardware twin, and one compose host does not realize every
SDL host boundary as separate infrastructure. The pack remains `draft`.

`tests/aws_event_rehearsal.py` creates the standalone event layout from the
pack's Terraform and event artifact. It sends the value-blind participant
program over A14's public SSH channel, checks every canonical flag recovery
plus negative gates, resets the range, repeats start-state checks, destroys the
range, and independently verifies that no live tagged EC2, S3, or IAM
resources remain. SSM is confined to provisioning, health observation, reset,
and teardown.

## Participant start-state closure

The event build completes before participant handoff. It creates every required
host, domain join, identity, service, share, route, tool, artifact, synthetic
credential, and initial objective state. It then publishes one range-scoped
participant access binding to A14 through a browser terminal, SSH/RDP gateway,
VPN/jump path, or equivalent declared `participant_access_mode`.

This closes the event path but does not make its authored industrial services
authentic vendor twins or establish golden status. SSM, cloud console,
Terraform output, generated passwords, operator SSH keys, root/SYSTEM,
`docker exec`, and database consoles remain operator mechanisms
for provisioning, diagnostics, reset, observation, and teardown. They cannot
be used as a participant step or proof surface.

## Path coupling

| SDL objective | Build/start-state responsibility | Automated participant leg | Manual walkthrough leg |
| --- | --- | --- | --- |
| `establish-target-picture` | A14 access; A0 site/files; range DNS | Replace/extend A0 and DNS component probes with participant commands from A14 and safe objective receipts. | Migrate the participant commands corresponding to `docs/walkthroughs/flags-01-06-osint.md`. |
| `compromise-front-office` | A1 mail, A2 AD, A3 intranet, A4 shares, identities, synthetic clues | Exercise the intended enterprise actions from A14; component health and CTFd readback remain subordinate. | Migrate the matching front-office actions from `flags-07-19-front-office.md`, excluding SCADA actions into the next objective. |
| `extract-leviathan` | A16 pivot, A6 workstation, A7 Gitea, A8 PostgreSQL, planted data and clients | Enter lab only through A16 and reach the objective in participant privilege; assert A14-to-lab denial. | Migrate the A16/A6/A7/A8 command path from `flags-20-30-lab.md`. |
| `lights-out` | A15 pivot, A5 industrial binding, range-local terminal state, closed splice | Enter SCADA only through A15; assert the pre-blackout A14-to-A9 denial and post-blackout reachability after participant execution. | Document the A15/A5 commands and the observed range-local splice transition. |
| `seize-autonomous-platform` | A9 gateway, A10–A13 industrial/controller bindings and reset state | Enter bunker only through A9 after the splice; execute controller actions and reach the independent objective verdict. | Migrate the participant commands from `flags-31-36-bunker.md`. |

Build, test, and walkthrough references use the same `runtime_profile_id`,
asset ids, objective ids, and pre/post-splice state ids. Tests must observe
start state; they must not create the clue, credential, route, identity,
service, artifact, or objective state they are meant to verify.

## Required validation layers

The design closes statically and then live:

1. released `aces-pack-validate` and `aces-pack-release`;
2. pack completion, provenance, visibility, containment, and leak gates;
3. the Polaris SDL/Compose binding test;
4. provider render/validate checks before mutation;
5. component readiness and reset diagnostics;
6. automated degraded event-path rehearsal against `aws_event`;
7. manual happy-path walkthrough from A14, command by command;
8. automated rehearsal rerun after manual fixes;
9. teardown and no-resource-left verification;
10. a sanitized rehearsal report.

Durable evidence may contain stable ids, timestamps, counts, statuses, bounded
digests, and verdicts. It must not contain raw credentials, flags, answers,
private keys, operator commands, generated passwords, Terraform output, raw
SSM/service responses, or participant-identifying data.

## Maturity gate

The current event source, automated rehearsal, mandatory manual participant
walkthrough, and final reconciliation report are the durable reference
authorities. They agree on the 38-recovery path, reset, and teardown, so
`contents.reference_triangle: true` is accurate. `pack.yaml.status: built` and
`pack.yaml.status: golden` remain prohibited until an authentic industrial
binding and the required host boundaries are implemented and the full
readiness checklist is proven against that binding.
