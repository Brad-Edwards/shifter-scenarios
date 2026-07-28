# Polaris final manual participant walkthrough

- schema: `polaris.aws-event.manual-walkthrough-report/v1`
- runtime_profile_id: `aws_event`
- runtime_source: `aws-range/` + `build/build-v1.tar.gz`
- pack_version: `0.5.0`
- participant_started_at: `2026-07-28T17:25Z`
- participant_completed_at: `2026-07-28T17:41:57Z`
- teardown_verified_at: `2026-07-28T17:45:44Z`
- manual_verdict: `PASS`
- manual_teardown: `PASS`
- post-fix_pack_version: `0.5.0`
- post-fix_automated_started_at: `2026-07-28T17:48:01Z`
- post-fix_automated_completed_at: `2026-07-28T18:20:46Z`
- post-fix_automated_rehearsal: `PASS`
- post-fix_reset: `PASS`
- post-fix_teardown: `PASS`
- static_checks: `PASS`
- overall_verdict: `PASS`

The range was built from the pack version above with the pack-local
`aws_event` entrypoint. Operator channels were limited to provisioning, health
observation, trusted SSH host-key binding, diagnostics after a participant
failure, and teardown. Every scenario action entered through A14's public
key-authenticated SSH endpoint as the unprivileged `kali` user.

The exact participant command sequence and expected outputs are the copied,
pack-adapted walkthroughs under [`docs/walkthroughs/`](walkthroughs/README.md).
No SSM command, host Docker access, Terraform output, generated credential,
root/SYSTEM management shell, direct database console, or test harness was
accepted as participant proof.

## Manual proof

| Stage | Walkthrough | Result |
| --- | --- | --- |
| Participant start | `00-range-access-aws-event.md` | PASS — unprivileged A14 entry and warm-up recovery |
| Target picture | `flags-01-06-osint.md` | PASS — 6/6 canonical recoveries |
| Front Office and SCADA | `flags-07-19-front-office.md` | PASS — 14/14 canonical recoveries |
| Lab | `flags-20-30-lab.md` | PASS — 12/12 canonical recoveries |
| Bunker | `flags-31-36-bunker.md` | PASS — 6/6 canonical recoveries |

All 38 canonical recoveries and all five SDL objective stages completed.
Direct A14-to-Lab and A14-to-SCADA access failed as required. A9 was
unresolvable and unreachable from A14 before the participant-triggered
blackout, then became reachable through the range-local splice afterward.

## Defects, fixes, and reruns

1. The Lab guide's plain `git log` opened a pager and consumed the next pasted
   command. The pack guide now uses `git --no-pager`; deleted-history recovery
   was rerun and passed.
2. The Bunker guide claimed bare `ssh root@splice-relay` selected the
   range-provided key, but A14 carried no matching SSH config entry. The
   participant-owned `~/.ssh/splice_relay` key was present and valid. The guide
   now selects it explicitly with `ssh -i`; A9 entry was rerun and passed.

No range service, content, identity, route, objective, or reset implementation
defect was found.

## Post-fix automated proof

The post-fix pack source ran through the complete automated `aws_event`
rehearsal. Initial participant recovery, negative gates, the blackout splice,
all 38 canonical recoveries, reset, post-reset start-state/controller/brain
checks, teardown, empty Terraform state, and empty tag-scoped live inventory
all passed.

## Teardown

The manual range was destroyed after completion. Terraform state was empty,
and an independent tag-scoped inventory check found no remaining EC2, VPC,
subnet, security-group, route-table, internet-gateway, volume, S3, IAM role, or
instance-profile resource for the run.

## Copied readiness checklist

This is the run-specific copy of `docs/golden-readiness-checklist.md`; the
source checklist remains unchecked.

### Golden definition of done

- [x] The declared range applied from a clean checkout using committed pack content.
- [x] The profile was isolated from shared infrastructure with range-scoped ingress.
- [x] Final pack-level authenticity and maturity were reconciled without a golden promotion; see `final-reconciliation-report.md`.
- [x] The declared build entered the participant start state without participant-side repair.
- [x] The participant execution surface was documented and reachable.
- [x] The full intended event path reached every required objective from participant context.
- [x] Negative gates prevented premature access to Lab, SCADA, and Bunker paths.
- [x] The post-fix automated rehearsal passed against the same profile.
- [x] This durable, sanitized report records the manual evidence.
- [x] Manual-range teardown left no live resources behind.

### Final manual participant walkthrough protocol

- [x] Stood up the declared `aws_event` profile from the documented build entrypoint.
- [x] Entered solely through the participant execution surface.
- [x] Executed the intended happy path manually, command by command.
- [x] Used operator channels only for provisioning, diagnostics, observation, and teardown.
- [x] Repaired each discovered guide defect on the branch and reran the affected step.
- [x] Completed the path after the final repair.
- [x] Ran the post-fix automated rehearsal and static checks.
- [x] Tore down the manual range and independently verified cleanup.
- [x] Reported exactly what was manual, automated, and left for final maturity reconciliation.
