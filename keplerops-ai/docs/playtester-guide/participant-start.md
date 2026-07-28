# Participant start guide

Give participants only the participant endpoint and spoiler-reviewed event
instructions. Do not provide operator proof reports, walkthroughs, hidden
predicates, Terraform output beyond the participant URL, receipt internals, or
challenge implementation notes.

## Participant entry

Participants enter through the Kasm browser workstation. The expected working
surface is inside the contained `*.keplerops.lab` environment.

Participants may use:

- the browser;
- the terminal;
- curl or Python from the workstation;
- in-world docs and portals;
- participant-owned agents, if the event rules allow them.

Participants should not use:

- GCP console, Terraform, or operator state;
- management-plane SSH;
- proof database internals;
- static flag extraction from repository content.

## Initial orientation

Tell participants that the range is an AI-security CTF-style environment with
multiple entry points. They do not need to drive an autonomous agent to make
progress, although the event may permit agent-assisted play.

Current recommended early starts:

- agent control;
- model evasion;
- retrieval/context poisoning;
- model-secret and privacy extraction.
