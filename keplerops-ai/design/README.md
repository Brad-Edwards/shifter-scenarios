# `design/` - Design Boundary

This directory contains human implementation-progress records only. The
modular [`../sdl/`](../sdl/) tree is the sole logical scenario authority; no
topology, software inventory, planned-asset projection, or provider build
contract belongs here. Provider realizations consume the expanded ACES SDL
directly.

The authoritative challenge allocation and actual implementation state are the set of 60 challenge behavior
specifications imported by
[`../sdl/keplerops-ai.sdl.yaml`](../sdl/keplerops-ai.sdl.yaml).
Each governed challenge extension records its status, primary
ATLAS techniques, manual walkthrough, and automated proof binding. No separate
implementation ledger is maintained.
[`../docs/challenge-portfolio.md`](../docs/challenge-portfolio.md) is its human
design rendering; its capacity table names conditional node additions for agent
execution, training, candidate serving, and CTF event correlation. A module
issue must either add the relevant nodes, software features, services, and
routes to the ACES environment module, or attach measured evidence that the
existing SDL-declared node meets isolation, concurrency, latency, and reset
requirements. Until that decision is made, the candidate is not silently
treated as implemented.
