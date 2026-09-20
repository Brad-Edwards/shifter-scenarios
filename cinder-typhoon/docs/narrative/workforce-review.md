# Workforce content review: issue 112

Author-only record. The reference state is 08:30 on 16 September 2026, UTC−04:00.
This review precedes the workforce asset pass and will record the final audit.

## Before authoring

The accepted cast has six KeplerOps employees, eight ARWC employees, and Jules,
who works for Veybridge. The twelve department budgets require 58 additional
KeplerOps employees and 222 additional ARWC employees. Jules must stay outside
both totals and have no principal-company mailbox or staff-directory entry.

The existing assets give ten cast members actor IDs. New employees need stable
workforce identifiers but no actor IDs, starting accounts, challenge grants, or
new machines. Rowan remains a developer rather than a manager; Mina reports to
a shift supervisor, Owen to a distribution supervisor, Rosa to a customer-service
supervisor, and Luc to a general manager. Those relations constrain the new
reporting tree. KeplerOps was founded in 2016; ARWC incorporates earlier Pine
and River service histories. Hiring everyone in 2026 would contradict both.

The current staff contacts expose name, address, department, and job. A complete
directory may add work team, manager, and work location. Hire history, personal
notes, equipment details, and access approvals require narrower readers. Shared
mailboxes and meeting rooms are not employees. A field worker's ordinary record
is more likely a rota, handover, or equipment request than a daily office thread.

The current four native content collections already use the staff/business
workplace nodes and digest-bound sources. The new sources must preserve the
`realization: {default: open}` posture, service readback, and existing challenge
facts. A directory source should be distinct from restricted employment records
so materializers cannot mistake broad staff visibility for personnel access.

## Review decisions

- Use exactly 294 employee records with a non-cyclic manager tree and the twelve
  fixed headcounts. Retain the fourteen established employee names and roles.
- Keep employee records, directory records, shared mailboxes, and the external
  contractor as different kinds of identity.
- Make a public staff directory and department contact pages; keep tenure,
  prior roles, onboarding, and equipment records with explicit readers.
- Give all new people a short author-only context and writing note. Give any new
  speaker used repeatedly a sample and review their mail across media.
- Freeze actual source bytes and digests, then validate joins and audiences
  against the source files and compiled SDL. Static checks do not demonstrate a
  running service.

## After authoring

The roster has 64 KeplerOps and 230 ARWC employees in the twelve specified
headcount groups. It retains all fourteen established employees and all ten
actor IDs in the original cast source. Jules remains an external Veybridge
correspondent. Four retained shared mailboxes are not employees. The reporting
tree has two roots, no cycle, and supervisors within each company. Team sizes
range from one office coordinator to twenty-two people in a plant or distribution
team; teams do not all have the same shape.

An initial date audit found three KeplerOps start dates preceding Leah's March
2016 founding. They were moved into April 2016 before the files were frozen.
The final start dates run from Mina's recognized Pine service in 2007 through
the 2026 intake. Current-role dates never precede start dates or follow the
snapshot. Forty staff have a recorded June assignment change; twenty-eight have
individual change records, and the restricted registers retain all forty prior
assignments. The 2026 starters have matching starting records and induction
appointments. The appointment time, attendee, manager, and publication date
remain tied to the roster.

The public contact CSVs and fifty-two department/role pages show work contacts,
teams, bases, and managers. Two personnel registers, eighteen starting records,
twenty-eight assignment-change records, and forty equipment requests are in
separate employment collections with exact named readers. A staff directory
reader does not inherit personnel access. Equipment serials, assignment names,
and calendar invitees are joined to the same roster identities. The distribution
groups describe staff, department, and team membership; they grant no challenge
role. No actor, objective, route, or starting account was added.

The first bulk mail review found subject/body mismatches in generic handover
threads, repeated short replies, and office phrasing in field correspondence.
The case text was revised around eight kinds of actual staff work and its open,
deferred, or confirmed state. All forty team-lead opening messages were then
edited individually. Thirty-seven new speakers with eight or more messages have
profiles and exact samples in [workforce-voices.md](workforce-voices.md). A final scan
found 1,366 distinct bodies among the 1,400 new messages; the remaining repeats
are short routine replies, with no body repeated more than three times. Thread
lengths vary from two to five messages, and field teams use shift, job, depot,
or service-point records rather than an office-only correspondence pattern.

Quoted-name searches for the thirty-seven profiled new speakers on 20 September
2026 found exact matching people for two proposed names. Those identities were
renamed to Lara Velswick and Niko Rensart, and both replacements were screened.
The inspected results contained no further exact match. This is a collision
screen, not a claim that no one anywhere uses a name. No real biography or
contact was used. A final casing pass also corrected eight template-lowercased
names and twenty-four month references in the messages.
The final visible-text scan found no mention of Cinder Typhoon, flags, challenges,
scenario authoring, OpenRAE, or issue 112 in the new mail and workforce documents.
The ownership inventory maps every source record and generated artifact to the
environment baseline. Its scenario overlay has no addition or replacement.

## Delivered counts and checks

| Measure | This slice | Pack total after the slice |
| --- | ---: | ---: |
| Employees | 280 added | 294 |
| Distinct logical messages | 1,400 | 1,475 |
| Retained mailbox copies | 3,220 | 3,399 |
| Source documents | 140 | 155 |
| Restricted employment business records | 88 | 88 |
| Calendar appointments/invitations | 18 | 21 |
| Staff directory CSVs | 2 complete | 2 |
| Digest-bound native workplace sources | 4 added | 8 |

The 140 new source documents comprise fifty-two department contact and team
role pages plus eighty-eight employment records. The employment records comprise
two personnel registers, eighteen starter records, twenty-eight team moves, and
forty equipment requests. Calendar appointments and directory CSVs are counted
separately, and a copied message is never a second logical message.

The asset validator checks exact RFC 5322 bytes, reply chronology, retained
mailbox membership, source digests, document formats and readers, department
headcounts, manager chains, company founding and employment dates, staff pages,
register joins, starter records, calendar files, and ownership inventory.
The pinned RAE parse, composition, compilation, and pack validation checks are
recorded in [SDL validation](../sdl-validation.md). These static checks establish
the shipped content and declarations. A running workplace adapter and deployment
readback remain later delivery work; no runtime proof is claimed here.
