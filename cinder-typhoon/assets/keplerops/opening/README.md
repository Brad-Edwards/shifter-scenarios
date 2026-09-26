# KeplerOps opening assets

These files are the authored inputs for the initial FieldKest developer
workspace and its source, CI, support and local-workbench services. Their
runtime destinations are declared by the KeplerOps opening content modules;
this directory is not copied wholesale into any participant system.

Generated binary artifacts are rebuilt deterministically from the manifests in
`k-dev/generation` and checked against the digests declared in the SDL. Service
contracts and operator tests are not participant content.

