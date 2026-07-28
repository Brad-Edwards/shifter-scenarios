# `oracle/` - KeplerOps Private View Boundary

This directory contains no scenario specification. KeplerOps objectives,
evidence requirements, score metrics, participant challenge copy, flag
delivery, proof events, research capture policy, and MITRE ATLAS bindings all
live in the modular ACES SDL.

RAES 2.0.0 governs module-level ATLAS tactics through
`sdl/keplerops-ai.sdl.yaml`. The additional pinned 173-technique catalog is an
operator-only ACES `content` dataset because RAES 2.0.0 has no native
technique-level field. Challenge-specific technique implementation evidence is
carried on governed `x-keplerops:challenge` extensions.

This README only marks the private-view boundary. Runtime and validation
consumers use `aces_contract.py` to derive bounded operational projections from
the SDL; no file under this directory is an alternate source of truth.
