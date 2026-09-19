# Reference build and authoring tools

[render_narrative.py](render_narrative.py) deterministically renders the authored
workplace assets and their native RAE content modules. It can check generated
outputs with `--check`. It performs no provisioning or outbound communication.

Runtime placement and infrastructure choices remain undecided. The reference
triangle layer in `pack.yaml` remains disabled.
