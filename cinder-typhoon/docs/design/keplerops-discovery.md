# KeplerOps participant discovery

This design defines how a participant moves from the supplied Rowan workstation
to the KeplerOps service interfaces without an exhaustive route catalog, blind
network discovery, or card-title route guessing. The author map remains a build
input. A range receives only the service-owned fragments needed to publish
ordinary client references.

## Trust boundaries and data flow

```text
author-only route map
        |
        | deterministic validation and split
        v
one client-reference fragment per service image
        |
        | unauthenticated GET /.well-known/fieldkest-client
        v
participant follows related references and normal response links
        |
        v
authenticated work and earned response values, including ARWC delivery
```

The author-only map is
`build/keplerops/authoring/client_documents.json`. It is the code-checkable
inventory used by validation, participant-surface review, and fragment
generation. No Dockerfile may copy that complete file. Generated fragments live
under `build/keplerops/runtime/client-references/`; each runtime image copies
only the fragment for the service it runs.

`HOME.md` supplies working-directory and trust-store guidance.
`work/service-notes.md` supplies the normal source client-reference entry point
and a small set of current source, CI, and support contacts. Those files are not
an attack-surface index. The source reference links the next ordinary service
references; recursive `related` links make every published reference reachable.

## Security invariants

1. The participant workstation contains neither `service-catalog.md` nor the
   complete author map.
2. No service image contains the complete author map or another service's
   fragment. A request with the wrong `Host` therefore cannot disclose another
   service's reference.
3. Every reference is reachable from the source reference through explicit
   `related` links. Discovery never requires port scanning, DNS brute force, or
   a card title.
4. Every request route used by the KeplerOps participant-boundary acceptance
   suite is resolved by a route key from the reference graph. Each method's
   inputs have specific citations in the provenance ledger.
5. K04's allocation boundary and sentinel are discoverable only by analysing
   and probing the supplied offline reproducer. State and completion routes,
   the worker lease, and descriptor values appear only in the earned descriptor
   response. Employee notes and client references contain none of those facts.
6. The two customer-delivery carriers are reached by ordinary graph branches:
   package publication and activation through the package reference, and
   diagnostic delivery through the support reference. Their authority and
   identifiers must still be earned from accepted responses.
7. The public client reference is available before route-specific
   authentication. Authentication still applies to the referenced operations.

## Failure behaviour

Fragment generation fails on a duplicate route key, an unknown related
reference, an unreachable service document, a missing or multiply assigned
image document, or generated-file drift. A service returns an unavailable or
not-found response when its fragment is absent, malformed, or does not own the
requested host. It never falls back to the author map or a built-in route.

Automated acceptance proves the graph is complete and executable from the
participant boundary. It does not prove that a fresh person finds the path
clear, fair, or appropriately difficult. CT-400 records that later human-plus-
agent observation.
