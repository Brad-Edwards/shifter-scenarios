# Reference build and authoring tools

[render_narrative.py](render_narrative.py) deterministically renders the authored
workplace assets and their native RAE content modules. It can check generated
outputs with `--check`. It performs no provisioning or outbound communication.

Runtime placement and infrastructure choices remain undecided. The reference
triangle layer in `pack.yaml` remains disabled.

`participant-surface/` defines and observes the pristine participant boundary.
`participant-runner/` streams the operator-authored known solution into that
unprivileged boundary without mounting test or repository files, and records a
credential-free structured acceptance report. Neither directory is participant
content or copied into scenario images.

`hint-delivery/` binds the three participant hint catalogs to one versioned
manifest and provides the facilitator release command. Release audits contain
only card/level metadata and content digests; unreleased hint text remains on
the operator surface.
