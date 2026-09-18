# Runtime cutover qualification

Status: pending. No live target or execution window has been assigned. Run the
complete matrix separately on AWS and GCP; a result on one provider does not
qualify the other. Keep all deployment identities and reproduction evidence here.

## Release inputs

Before executing, record the approved target, window, Shifter revision and deployed
image digests, SDK version and wheel hash, adapter wheel hash and registry digest,
pack canonical digest, guest image identifiers, and participant client version.
Use registry-resolved digests, not the local worker image ID in
`isolated-worker-evidence.json`. Rebuild the participant image with the pinned
client before qualification. Record the admin and participant roles without
retaining credentials or enrollment capabilities.

Confirm the normal tenant deployment provides the plugin controller, dedicated
sandbox nodes and required `gvisor` RuntimeClass. A missing runtime is a failed
prerequisite, never permission to use the default container runtime. Confirm
broker routing, trusted TLS, the approved model policy, and private management
connectivity through deployment readback.

## Per-provider execution

| Check | Required observation | AWS | GCP |
| --- | --- | --- | --- |
| Tenant authority | A non-staff organization admin installs a pack and an adapter through the tenant UI. An ordinary member and an admin of another organization cannot mutate or inspect the installation. | Pending | Pending |
| Independent installation | Pack upload alone creates no executable installation. Adapter installation uses its immutable image digest and explicit registry authentication where required. | Pending | Pending |
| Worker containment | Inspect the actual Job, admission outcome, node placement and runtime. No platform/cloud credentials, service-account token or host mounts reach the worker; undeclared network access fails. | Pending | Pending |
| Compatibility failure | An unsupported protocol or unavailable worker runtime stays visibly unready, with no guest resources created. | Pending | Pending |
| Binding and admission | Admin selects the exact pack digest, installed adapter version, host/directory targets and approved participant model policy. Missing, disabled, incompatible or ambiguous bindings fail before allocation. | Pending | Pending |
| Configuration | Launch realizes both guests and applies directory and host actions. The directory firewall posture is owned by the private adapter. Core changes only its management rule. | Pending | Pending |
| Participant readiness | Participant SSH uses the observed participant host key and declared account/port. Directory discovery and scenario entry work. Readiness follows successful configuration and verification. | Pending | Pending |
| Model request | The actual pinned client performs a permitted request and a local tool round trip through the broker. No provider credential is present in guest environment, arguments or adapter input. | Pending | Pending |
| Model enforcement | Wrong identity, disallowed model, exhausted budget and revoked grant are rejected. Accounting and revocation are observed at the broker, not inferred from client output. | Pending | Pending |
| Retry | Interrupt configuration at a controlled point, then retry through the supported product path. Owned resource and enrollment identity remain coherent; no duplicate resources or stale readiness result survives. | Pending | Pending |
| Cancellation | Cancel while configuration is pending. Late worker output cannot mark the cancelled operation ready; guest resources and grants reach the expected terminal state. | Pending | Pending |
| Disable and upgrade | Disable blocks new admission. Upgrade and pack replacement require explicit new bindings. Existing range inputs retain their original immutable identities. | Pending | Pending |
| Cleanup independence | Destroy an existing range after disabling its adapter and making its image unavailable. Core still revokes grants and removes the owned cloud resources. | Pending | Pending |
| Ownership conflict | Use an isolated synthetic conflict fixture to verify a mismatched resource ownership tag is refused before destructive mutation. Do not modify an unrelated range. | Pending | Pending |
| Final absence | Independently inventory the range scope after destruction, including guests, network resources and credentials; verify allocation release and no surviving model authority. Retain the bounded readback evidence. | Pending | Pending |

For each cell record the operation ID, expected and observed result, timestamps,
and a private evidence path. A failed cell remains open until repaired and rerun.
Avoid capturing raw prompts, answers, tokens or full environment dumps. Public
defects use synthetic reproductions and omit deployment and pack identities.

Pause/resume is not established by this matrix. Do not infer its support from
successful launch, retry or destruction. Any capability offered by the deployed
UI must have its own supported dispatcher and state-preservation evidence.

## Cutover decision

Both provider columns, worker registry delivery, guest image rebuilds and the
reviewed Shifter delivery must be complete before declaring this cutover ready.
The SDK may be supplied as a locally built, hash-recorded wheel; SDK publication
is not a prerequisite for qualification.
The local records establish package/plan/worker behavior only. They do not fill
any live cell. If the deployment still uses the retired guest role issuer, apply
the documented drain sequence using the previous release before its IAM removal.
