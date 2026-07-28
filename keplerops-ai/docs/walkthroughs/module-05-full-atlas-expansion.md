# Module 05 Full-ATLAS Expansion Walkthrough

Pre-playtest source walkthrough for Module 05 expansion. The ACES SDL fragments
`module-05-agent-persistence-full-atlas-expansion-a.sdl.yaml`,
`module-05-agent-persistence-full-atlas-expansion-b.sdl.yaml`, and
`module-05-agent-persistence-full-atlas-expansion-c.sdl.yaml` are authoritative.

All paths enter through the participant gateway. The runtime records real
platform-agent actions and participant/reset scoped state before
`/v1/persistence/platform/attempts` can emit a receipt.

## Challenge surface

| Challenge | Participant action | Runtime surface |
|---|---|---|
| `kep-m05-f` | Acquire the live public agent blueprint and match it to the active platform revision. | `POST /v1/persistence/expansion/actions` with `challenge_id=kep-m05-f`. |
| `kep-m05-g` | Discover live agent configuration and scoped access material. | Expansion action for `kep-m05-g`; proof requires two server-observed events. |
| `kep-m05-h` | Reuse generation-scoped access material for one authorized AI operation. | Expansion action for `kep-m05-h` with the scoped token returned by `kep-m05-g`. |
| `kep-m05-i` | Replay a synthetic web session in a distinct browser session. | Expansion action for `kep-m05-i` with distinct original/replay session IDs. |
| `kep-m05-j` | Validate access material found in a participant-reachable service artifact. | Expansion action for `kep-m05-j`. |
| `kep-m05-k` | Invoke a real platform-agent tool and validate its downstream access material. | Expansion action for `kep-m05-k`, which runs `query_json@1.0.0`. |
| `kep-m05-l` | Use the contained worker path to recover synthetic OS credential material. | Expansion action for `kep-m05-l`, which creates a disposable platform-agent worker. |
| `kep-m05-m` | Persist changed behavior through the platform-agent configuration service. | Expansion action for `kep-m05-m`, which writes and activates a configuration revision. |
| `kep-m05-n` | Deploy a local rogue agent on the disposable worker and recover the contained marker. | Expansion action for `kep-m05-n`. |
| `kep-m05-o` | Establish a contained reverse channel and execute a retrieved command. | Expansion action for `kep-m05-o`, backed by platform-agent relay events. |
| `kep-m05-p` | Exchange command and result through the normal AI service API. | Expansion action for `kep-m05-p`, backed by encoded relay task/result events. |
| `kep-m05-q` | Automate the web assistant relay path without using the API-token shortcut. | Expansion action for `kep-m05-q`, backed by relay and export events. |

## Negative controls

- Tokens are scoped to range instance, participant, and reset generation.
- Same-session cookie replay fails `kep-m05-i`.
- Management shells do not satisfy `kep-m05-l`.
- Direct API calls are rejected for `kep-m05-q`; the proof expects browser relay evidence.

## Validation status

This source slice uses focused domain, API-contract, SDL, portfolio, oracle, and
file-size validation. It is not a participant-proven or golden claim.
