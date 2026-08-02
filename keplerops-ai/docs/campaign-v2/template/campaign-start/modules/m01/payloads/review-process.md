# Orion Partner Evaluation Process

Release Engineering accepts partner model candidates and compatible helper
packages through the Orion Review Room. Each submission must include a digest,
model or package card, license, SBOM, reproducible smoke test, and relay URL for
job notifications.

The evaluation workbench downloads the submitted bytes and uses the loader and
dependency versions in the repository lockfile. Static inspection and isolated
execution are separate jobs. Their runtime reports include kernel, cgroup,
mount, seccomp, process, and network facts so integration failures can be
reproduced without guessing.

Public Preview flow metadata identifies the exact Langflow release. Protected
component validation is restricted to Release Engineering, while public
temporary-flow builds remain available for partner compatibility checks.
