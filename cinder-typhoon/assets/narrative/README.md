# Workplace story assets

This collection realizes the [worldbuilding draft](../../docs/narrative/README.md)
as correspondence and records people can encounter inside the companies.

The collection contains 19,647 distinct authored messages, 4,048 source documents,
staff directories for all 294 employees, and 169 calendar items. The
workforce slice added 1,400 messages and 140 documents to the earlier story
collection. The business slice adds 1,600 messages and 89 documents for twelve
KeplerOps utility accounts and seven other established partner relationships.
The support slice adds 5,500 messages, 500 case records, 78 supporting
documents, and 64 implementation or onboarding appointments for the twelve
utility customers. Its 30 accepted engineering escalations remain unresolved.
The engineering slice adds 5,500 messages and 720 documents; product and quality
adds 4,000 messages and 1,976 documents. Release and platform adds 1,572 messages,
530 documents, 120 operating histories, and 84 calendars. Its
[review record](../../docs/narrative/release-platform-review.md) explains the
message allocation, accepted revisions, held bundles, and validation limits.
It keeps the eight ordinary stories. Jules and the new external contacts remain
outside both employee directories.

The [character writing slice](../../docs/narrative/voice-review.md) selects 30
samples from the original story collection: nine unchanged messages, fourteen
revised messages, and seven new messages. It extends the existing fifteen
profiles in place. The other 45 original messages remain unchanged. Private
profiles, sample annotations, ownership,
and base-version records stay under `docs/narrative/` and are not deployed.

## Sources and outputs

| Location | Purpose |
| --- | --- |
| `authoring/people.yaml` | Fictional people, addresses, and departmental correspondents. |
| `authoring/workforce.yaml` | Full employee roster, reporting tree, distribution groups, tenure, and author-only writing notes. |
| `authoring/workforce-actions.yaml` | Author-only join index for the workforce correspondence. |
| `authoring/business-network.yaml` | Author-only organizations, contact profiles, agreement terms, and accepted activity. |
| `authoring/support-intake.yaml` | Author-only joins for support cases, separate customer/internal threads, attachments, and appointments. |
| `authoring/release-platform.yaml` | Author-only release acceptance joins, operating states, recovery samples, logical service owners, and counts. |
| `authoring/mail-*.yaml` | Authored message text, dates, recipients, reply relationships, and attachment references. |
| `authoring/documents*.yaml`, `documents/` | Inline or file-backed authored documents, titles, display paths, and intended readers. |
| `authoring/calendars*.yaml` | Historical operating windows and agreed, cancelled, or tentative arrangements as of the snapshot. |
| `generated/messages/` | Individual RFC 5322 review files for the earlier story messages. Workforce, business, and support RFC 5322 bytes are in the mail source packages to keep the pack under its file limit. |
| `generated/directories/`, `generated/calendars/` | CSV contacts and original RFC 5545 calendar files. Bulk operating calendars are complete items in the document source package. |
| `generated/packages/` | Eight self-contained JSON source artifacts for native RAE content declarations. |
| `artifact-catalog.json` | Exact source-name/version to pack-relative file mapping and SHA-256 digests. |
| `story-coverage.json` | Author-only map from narrative threads to records and retained copies. |

Only the eight package payloads are bound into the world. Authoring metadata,
coverage records, and this README are not part of a staff mailbox or document
library. The original documents and source mail are also available for review.

Rebuild from the repository root using the validation environment:

```sh
python cinder-typhoon/build/render_narrative.py
python cinder-typhoon/build/render_narrative.py --check
python cinder-typhoon/tests/validate_narrative.py
```

PyYAML is included in the existing pinned SDL validation requirements. Rendering
is deterministic and local; it sends no mail and creates no target accounts.

## Native RAE binding

The `narrative-keplerops` and `narrative-arwc` modules each declare four native
`content` datasets: mail, documents, directory, and employment. They target the
existing staff and business systems respectively. Each uses RAE's
`service_materialization` contract for a
named `workplace` service, with `ensure-owned-items`, rejection of unowned
collisions, and canonical content-digest readback.

A native `Source` identifies a package by name and version. The version includes
the SHA-256 of the package bytes; `artifact-catalog.json` resolves that exact pair
to a shipped file. This catalog is the pack's artifact lookup convention, not an
additional RAE field or an assumption that the parser fetches source bytes.
The author validator joins those references to the actual files and the compiled
content placements.

The named service has a logical TCP 443 binding on each existing node. It adds
no node, subnet, access route, or supplied credential. RAE's service declaration
does not itself authorize traffic. Host operating systems, software products,
physical hosting, and participant replication retain their open declarations.

Eight observed-state readback assertions require authorized-reader visibility of
the exact content collections. They are materialization checks, separate from
challenge completion; they add no objectives or prerequisite gates. The eventual
adapter must implement the formats below and prove readback. Static validation
establishes the authored and compiled contracts, not a running workplace service.

## Payload formats

`cinder-mailbox-set/v1` is a pack-specific content format carried by native RAE
`dataset` and `Source` fields. The JSON object contains:

- `snapshot`: the authored opening time, with an explicit fictional local offset.
- `messages`: unique Message-IDs, the exact ASCII RFC822 serialization including
  encoded Unicode and MIME attachments, and each message's SHA-256.
- `mailboxes`: owners and their `INBOX`/`Sent` memberships by Message-ID.

The same exchange has identical bytes wherever retained. The materializer must
preserve ownership, folder membership, headers, bodies, reply chains, and
attachments. Access to one mailbox does not reveal the whole source collection.
External correspondence is retained at the principal companies; no supplier
mail environment is created by this collection.

`cinder-document-library/v1`, `cinder-staff-directory/v1`, and
`cinder-employment-records/v1` contain named items with title, relative display
path, media type, exact text, and explicit reader addresses. The directory source
is readable by same-company staff; individual employment records and induction
appointments require the listed staff identities. A materializer must enforce
those reader sets for every item, not expose the whole collection to a reader of
one item. The directory and employment packages carry exact department and team
reader-group memberships and an individual-identity requirement. Native RAE
marks mail, documents, and employment sensitive; source-package readers are the
pack's detailed access contract for the eventual workplace adapter.
These data formats are defined by this pack; RAE supplies their source, owner,
materialization, observation, and compilation semantics.

## Opening state and editorial scope

The snapshot is 08:30 on 16 September 2026, with a fictional local UTC−04:00
offset. Messages precede that instant. Invitations can concern later dates;
a tentative lunch remains tentative, and a planned workshop is not already over.
No timer runs these social events.

The documents and mail contain worldbuilding rather than required challenge
secrets. Personal interests do not become password clues. Private conversations
are kept with their participants, and general company documents have appropriate
staff audiences. Original actor and business identifiers remain stable while
screened display names and personal login spellings are aligned in the active
SDL, challenge cards, and technical data contract.
