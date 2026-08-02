# Orion MCP dependency adoption

The staging consumer admits changes through dependency-update pull requests.
Each proposal resolves an immutable npm integrity, verifies the Cinder
maintainer's detached signature, and runs the package's advertised tests. After
merge, `adoption/manifest.json` preserves the first useful release's source PR,
merge commit, signed tarball digest, registry integrity, and installed digest.

Later releases use the same proposal path. Model-card checks load only the
version and integrity present on `main`.

Successor proposals also run a black-box integration probe. The candidate must
preserve the public `inspect_model_card` result while sending the private card
field to the callback named by `ORION_MODEL_CARD_CALLBACK`. The proposal audit
records only the callback body digest; the private field itself remains in the
protected release workflow.
