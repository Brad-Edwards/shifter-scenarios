# Orion Partner Evaluation Process

Release Engineering accepts partner model candidates and compatible helper
packages as **Evaluation Intake** records in Orion Release Operations. Each
record must include one `submission.json` attachment, a digest, model or package
card, license, SBOM digest, reproducible smoke test, and native relations to its
completed access records.

The queue journals every transition through New, Queued, Running, and a terminal
state. The evaluation workbench downloads the recorded candidate digest. Helper
reviews resolve the partner-published `orion-eval-utils` release from the
earned `publisher/stable` devpi index only after consuming the exact M02-l
acceptance at the exact commit named by the earned M02 entitlement in
`keplerops/orion-partner-contributions:accepted/<review-attempt>-<wheel-sha256>.json`.
Contributor, index, accepted callback, signed wheel digest, and
SBOM/signature/key digests must match that immutable Forgejo blob and commit; a
directly attached wheel or preaccepted registry release is never installed. Static
analysis and integration are separate disposable workers. Their runtime reports
include kernel, cgroup, mount, seccomp, process, and network facts so integration
failures can be reproduced without guessing one marker.

Public Preview flow metadata identifies the exact Langflow release. Protected
component validation is restricted to Release Engineering, while public
temporary-flow builds remain available for partner compatibility checks.
