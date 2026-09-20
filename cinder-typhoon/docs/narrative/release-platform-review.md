# Release and platform content review: issue 117

Author-only record. Opening state: 08:30 on 16 September 2026, UTC−04:00.

## Fit and adversarial review before authoring

The accepted base is commit `631dfa1`, including product and quality content
from `1ac57ee`. All 220 accepted revisions target FieldKest 4.9.1. The thirty
support-linked assessments remain deferred or declined. The seven platform
staff retain their workforce identities, reporting lines, and writing profiles.

The initial review identified these risks and set the following content rules:

1. Acceptance is not release evidence. Each release bundle must name accepted
   product records and exact engineering revisions. Build, publication, and
   qualification readback must follow the latest acceptance in that bundle.
2. Product 4.9.1 is distinct from the active customer's `FLK-7.4.2` service
   revision and `@keplerops/fieldlink-connector` package line. Ordinary release
   qualification must not replace those records or close their support cases.
3. A service inventory can accidentally invent infrastructure. Use existing
   logical source, build, registry, preview, workplace, and backup owners.
   Workplace records describe their work; they do not create service authority.
4. Backup checks need a named dataset and bounded recovery evidence. Use the
   existing workplace document collection, a selected document manifest, exact
   bytes and digests, and explicit sample-restore scope. Do not claim full
   disaster recovery from a successful sample.
5. Routine changes do not justify endless discussion. Use compact machine
   events, short human exchanges, and longer threads only for a decision,
   exception, or handover. Count distinct messages separately from retained
   copies. Document any allocation adjustment with its milestone effect.
6. Scheduled work can be mistaken for completed work. Retain cancelled windows,
   failed attempts and their follow-up, provisional notes, final notes, and
   actual outcomes. Deferred work must have no publication or deployment claim.
7. Department-wide copies would expose unnecessary detail. Limit each history
   to its working owners, approver, and relevant evidence readers. Existing
   private Evan/Noor correspondence remains private and unchanged.

## Finished content and allocation

The histories run from 1 June through 11 September 2026. They reuse the five
accepted FieldKest repositories and the seven platform staff.

| Delivered item | Count |
| --- | ---: |
| Release qualification histories | 60 |
| Maintenance histories | 24 |
| Sample recovery histories | 24 |
| Capacity reviews | 12 |
| Distinct logical messages | 1,572 |
| Human messages | 1,212 |
| Machine notices | 360 |
| Retained KeplerOps mailbox copies | 3,144 |
| Documents, including manifests, logs, and workbooks | 530 |
| Calendar items | 84 |
| Published qualification bundles | 54 |
| Accepted revisions in published bundles | 199 |
| Deferred bundles / accepted revisions held | 6 / 21 |
| Failed builds followed by a successful retry | 6 |
| Completed / deferred maintenance changes | 20 / 4 |
| Recovery checks needing a corrected selector | 2 |
| Recorded / deferred capacity decisions | 10 / 2 |

The document count comprises 360 release documents, 96 maintenance documents,
48 recovery documents, 24 capacity documents, and two shared registers. Each
release includes a qualification manifest, proposed and final notes, a change
request, an event log, and a handover. The manifest pins the exact accepted
engineering revisions and the SHA-256 digests of their shipped quality results.
Release artifacts here are finished qualification manifests and records, not
new executable software distributions. The operating records describe internal
qualification selection and readback; they do not assert customer deployment.

The initial allocation of approximately 4,500 messages is adjusted to 1,572.
The 120 histories need 8–24 messages each: routine completion is short, while
failed builds retain diagnosis, retry decisions, and subsequent results.
Reaching 4,500 within these histories would require an average of 37.5 messages
per history or an unrelated new stream of traffic. The slice instead retains
the substantive discussions and distinct machine events. This reduces the
milestone's combined message allocation by 2,928; that difference remains
unallocated. It is not silently assigned to another slice or counted through
mailbox copies. This slice does not establish the milestone-wide mail target.

## Finished-content adversarial review

The review compared normal releases, deferred windows, failed builds, each
maintenance family, recovery samples, and capacity disagreements. It checked
the rendered payloads as well as authoring records. Corrections included:

- Recovery drafts repeatedly asked whether a sample meant a full restore.
  Exchanges now discuss particular entries, byte lengths, reader checks, and
  sample ordering. Reports retain an explicit sample-only recovery limit.
- Several release drafts gave everyone the same cadence. Evan now keeps a
  deliberate proposal and finish, Isabel asks narrower questions, and Iris
  concentrates on handover. Noor's shift notes remain short; Jamie records
  spoken decisions, Jalen names the next action, and Jonas reports the result.
- Repeated capacity misunderstandings made colleagues look inattentive.
  Only one ordinary correction remains; other reviews discuss real staffing
  limits. Two extra-slot requests stay deferred instead of ending in agreement.
- A maintenance report initially used its later administrative closing time as
  the observation time. The result now records the observation before the
  report is published. Approval identities match the actual decision sender.
- Attachment serialization previously labeled every attachment as Markdown.
  It now uses the declared JSON, CSV, plain-text, or Markdown media type. Exact
  bytes are preserved; existing attachments receive the same format correction.
- Standalone calendar copies exceeded the native pack member limit. All 84
  complete RFC 5545 items now reside in the workplace document source package,
  with their exact times, cancelled or confirmed states, and intended readers.
  They need no duplicate pack members.

The service inventory refers to existing logical owners in author-only joins.
Visible records use natural service names. Recovery samples reference existing
workplace documents and preserve their byte lengths and digests. Reports carry
sample metadata, not copies of the restricted source documents. The four
maintenance deferrals preserve the previous measured state. None of the thirty
upstream support assessments gains release evidence or a closure claim.

## Validation and limits

The focused validator checks acceptance, exact revisions and quality-result
digests, publication and selection order, machine values, backup bytes,
capacity arithmetic, cancelled calendars, attachment dates, and readers.
Ten corruption cases exercise these boundaries. The full narrative validator
also checks serialized mail, MIME types, retained copies, ownership, and source
versions. Native validation checks the complete campaign and the eight existing
workplace readback contracts using `raes==5.0.0` and `raes-env-packs==6.1.0`.

The world release is `release-platform-2026-09-16/v1`; its scenario overlay is
empty. Source packages keep their existing staff-system owners, observed
readback requirements, and `realization: {default: open}` semantics. Challenge
logic, service revisions, package names, routes, and authorities are unchanged.
Static validation does not establish live deployment or runtime readback.
