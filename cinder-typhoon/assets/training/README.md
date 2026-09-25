# Training artifact placement

This is author documentation; do not publish it in the participant world. The
47 files below are exact initial content for the four Training systems and the
participant workstation. They are design inputs, not running services or a
golden range.

Native `content` entries embed the exact UTF-8 bytes in seven independently
imported modules. These source files are maintained authoring copies; tests
reject any byte, target, destination, ownership, digest, route, or access-mode
drift. There is no private include, loader, or SDL dialect.

| Source family | Owning node | Destination roots | Purpose |
| --- | --- | --- | --- |
| `workstation/` | `participant.kali` | `/home/cinder/` | Local opening document and stable service names. |
| `workbench/` | `training.t-workbench` | `/srv/cinder-workbench/`, `/var/lib/cinder-workbench/`, `/etc/cinder-workbench/` | Handover Git seed, tracker, dispatch site, retired courier client, diagnostic records, and exact service contract. |
| `accounts/` | `training.t-accounts` | `/srv/cinder-accounts/`, `/var/lib/cinder-accounts/`, `/etc/cinder-accounts/` | Candidate notes, directory client/data, account realm, handover, assignment records, and exact service contract. |
| `developer/` | `training.t-developer` | `/srv/cinder-developer/`, `/var/lib/cinder-developer/`, `/etc/cinder-developer/` | Forge seed, build record, sample package, registry/consumer data, current contract, and exact service contract. |
| `state/` | `training.t-state` | `/srv/cinder-state/`, `/var/lib/cinder-state/`, `/etc/cinder-state/` | Instrument captures, replay, live initial state, field guide, and exact service contract. |

The SDL binds published files to named application routes and private files to
service-owned state. Public files are root-owned mode `0444`; private seeds and
configuration are root-owned mode `0440` for the locked service group. Mutable
audit/session/publication/receipt/live-state directories are owned by the
locked service identity and have no static route. The workstation document is
owned by its local `cinder` user and is read-only.

The three repository seed files are ordinary JSON data. They specify exact Git
commit order, parents, authors, committers, UTC times, messages, file modes,
deletions, paths, and UTF-8 file bytes. A future builder constructs the real
repositories from that data and exposes the native read-only smart-HTTP routes.
The resulting commit object IDs are derived rather than invented.

Each private `service-contract.json` is application configuration, not an SDL
extension. It fixes the request decision order, response classes, mutable state,
audit fields, idempotency, authorization scope, persistence, isolation, and
other behavior that RAE's native application/runtime records associate with the
node. A manual implementation and an automated backend must produce the same
observable behavior.

The Training network is `10.77.40.0/24`: Kali is `.10`, Workbench `.20`,
Accounts `.30`, Developer `.40`, and State `.50`. Runtime endpoint declarations
also require the `*.training` names. The subnet is internal and has no
infrastructure link to KeplerOps or ARWC.

The initial tank JSON is loaded once during environment preparation. It is not
an HTTP operation or automatic restore mechanism. The service thereafter
persists live state separately. Static captures and the replay use distinct tank
identities and remain unchanged.

No KeplerOps or ARWC workplace collection is copied into Training, and none of
their assets has been relocated or repurposed. No service, repository, package,
process, or network has been built by this design work.
