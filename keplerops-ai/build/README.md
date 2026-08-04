# KeplerOps GCP build source

This directory implements GCP provider binding's `gcp_full` provider binding. It creates
a namespaced, disposable tenant inside an existing GCP project: a custom VPC and subnets, route-derived
firewalls, keyless per-asset identities, private runtime nodes, a source-limited
participant workstation, immutable Artifact Registry images, and deterministic
start-state/lifecycle tooling. It expands the canonical modular ACES root at
[`../sdl/keplerops-ai.sdl.yaml`](../sdl/keplerops-ai.sdl.yaml) with the exact
PyPI package `raes==2.0.0`. The renderer writes a mode-0600 ephemeral
Terraform input; no committed provider topology, inventory, or build contract
exists.

The pack remains `draft`. Automated rehearsal adds the Kasm-only automated rehearsal,
and manual walkthrough has completed the generation-55 manual participant path. Its
post-manual static checks, canonical reset, evidence reconciliation, and
Phase-E teardown pass. The later corrected integrated Kasm run passed all ten
module checks and all 60 original item receipts after Module 01's corrected
qualification, and its canonical reset passed cleanup and stale-state checks.
The current SDL carries 134 native challenge contracts: 40 participant-proven,
29 automated-proven, 65 source-implemented pre-playtest, plus one remaining
planned design in the complete library. Final playtest calibration, release
hardening, and golden reconciliation remain open.

## Prerequisites

- Terraform 1.6 or newer, Packer 1.11 or newer, Python 3.11 or newer, and an
  already-authenticated `gcloud` CLI. Build and lifecycle entrypoints pass the
  current access token transiently; they never initiate login or credential
  repair.
- Permission to administer range resources and use Cloud Build in the supplied
  existing project. The build does not create, attach billing to, or delete a project.
- The existing project ID and an operator-approved participant
  source CIDR. World-open participant ingress is rejected.

Build the immutable outer-host image from the committed Packer definition. The
temporary builder network must provide source-bounded SSH ingress and package
egress; those controls are supplied as explicit tags and are not created by the
pack. Pass `--use-iap` when the builder principal and network provide IAP
instead:

```sh
build/gcp/build-nested-host-image.sh \
  --project-id prod-ksqdkj \
  --image-name keplerops-nested-host-v20260728 \
  --network keplerops-555-a \
  --subnetwork kep-555-a-r01 \
  --network-tag keplerops-image-builder
```

Run the complete isolated build-contract suite through its committed dependency
set:

```sh
build/test.sh
```

No repo-root `.env`, service-account key, CLI token, generated participant key,
or hidden content source is used. Runtime image inputs are revision/digest
pinned by native feature sources, build provenance, and dependencies in
`../sdl/modules/environment.sdl.yaml`; the open model file set is pinned by the
ACES-bound `../assets/model-artifacts/model.yaml` content artifact.
Bootstrap retrieves both text and binary Secret Manager values through an
owner-only bind-mounted `--out-file`; binary research keys never pass through
terminal/stdout encoding.
The dedicated nested range host enables unprivileged user namespaces because
the bounded-worker engine uses rootlesskit inside its isolated outer container.
That host setting is scoped to the single-tenant range host; participant
workloads remain rootless and the worker engine is disconnected from the outer
Docker bridge after initialization.
The private nested bridge also proxy-ARPs the Google link-local metadata address
for Windows guests and returns only stable guest identity, network context, and
an empty startup-attribute set. The outer host retains its real GCE metadata
route; the compatibility surface exists only to complete the public image's
specialize phase before the authored WinRM bootstrap takes control. Secret
reads are limited to each guest's authoritative SDL secret-access bindings, and
guest-attribute writes are bound to the fixed source address of that guest.

The generated realization also drives every VM's TCP/UDP host-port allowlist,
firewall protocols, disk policy, TLS seed inventory, evidence-producer token
inventory, and health expectations. Adding an SDL node therefore does not
require a parallel asset, certificate, or service-port list. The initial
software-foundation batches add OpenSearch, CoreDNS, two real NGINX surfaces,
the contained impact platform, and the source-trained CPU document/vision model
workbench. The communications batch adds real SMTP/IMAP/webmail, compact local
text generation, and persistent CPU image generation; these batches
intentionally add no challenge or award logic. The context batch adds one
SDL-built sidecar image on `repo-ticket-01`: an authenticated integration API,
a confined file-ingest worker, and an incremental PostgreSQL-to-OpenSearch and
WorkHub synchronization worker. Gitea and Redmine create their scoped synthetic
runtime credentials in-world; Keycloak and PostgreSQL access is projected from
native SDL dependencies and Secret Manager grants.
The camera batch adds an HTTPS-only browser surface on the data/workflow network,
uses host networking for routable WebRTC ICE candidates, and forwards only fresh
decoded frames to the real CPU vision workbench. Its focused browser smoke is a
single proof of media negotiation and retained frame content, not a reliability
campaign.

## Entry points

```sh
build/launch.sh \
  --project-id prod-ksqdkj \
  --range-instance kep-355-a1 \
  --participant participant-01 \
  --participant-source-cidr 203.0.113.10/32 \
  --range-subnet-self-link \
    https://www.googleapis.com/compute/v1/projects/prod-ksqdkj/regions/europe-west4/subnetworks/kep-cell-01 \
  --range-subnet-cidr 10.72.0.0/24 \
  --runtime-repository-id keplerops-runtime \
  --shared-model-service-name keplerops-model-cell-01 \
  --shared-model-service-url \
    https://keplerops-model-cell-01-abc123.europe-west4.run.app \
  --image-lock /operator/keplerops-image-lock.json \
  --windows-image projects/prod-ksqdkj/global/images/keplerops-windows-v1 \
  --nested-host-image \
    projects/prod-ksqdkj/global/images/keplerops-nested-host-v20260728 \
  --range-host-ip-offset 10 \
  --research-profile off

build/health-check.sh --range-instance kep-355-a1 --participant participant-01
build/reset.sh --range-instance kep-355-a1 --participant participant-01
tests/run-nested-golden-proof.sh \
  --project-id prod-ksqdkj \
  --range-instance kep-355-a1 \
  --participant participant-01 \
  --participant-source-cidr 203.0.113.10/32
build/export-telemetry.sh \
  --range-instance kep-355-a1 \
  --participant participant-01 \
  --output /operator/evidence/kep-355-a1-telemetry.tar
build/cleanup.sh --range-instance kep-355-a1 --participant participant-01
```

`--range-host-ip-offset` defaults to `10`, preserving the historical range-host
address. When multiple retained playtest ranges share the same cell subnet, give
each concurrent range a distinct offset inside the subnet so the packed host does
not collide with another operator's VM.

The nested golden proof entrypoint runs the static pack contract, the integrated
Kasm participant rehearsal, every focused expansion runner, and two canonical
reset/health cycles. Its challenge sets contain 134 unique realized challenge
IDs after accounting for the ten intentional core/expansion overlaps. It leaves
the retained range in a clean, health-checked generation for playtesting.

On the golden GCP profile, range health also requires the loopback-only green
activity sidecar to report its RAES clock, lifecycle, generation, and action
count. The sidecar is paced by the compiled simulated workday, drains through
the normal range-ops quiesce hook, and loses its durable snapshot during the
normal reset. A targeted operator diagnostic may trigger one due occurrence
through the authenticated loopback `POST /v1/run-once`; this is service
readback only and is never challenge or participant-path proof.

`--research-profile off` is the default and leaves encrypted full-content
capture disabled. `--research-profile full-content` enables the SDL-declared
prompt, completion, tool call, tool result, terminal command, terminal
input/output, terminal-session lifecycle, browser navigation/download,
Jupyter notebook/file save, workstation filesystem, Airflow workflow
state/artifact, and selected HTTP body capture signals without changing the
CTFd challenge bundle.

After rebuilding the retained tenant with participant telemetry implementation's runtime images, run the
participant-equivalent telemetry proof without creating or destroying a
project, account, or billing relationship:

```sh
tests/run-telemetry-rehearsal.sh \
  --project-id prod-ksqdkj \
  --range-instance kep-356-b1 \
  --participant operator \
  --participant-source-cidr 203.0.113.10/32
```

This enters through Kasm, exercises a quick inference path, triggers and polls
the real Airflow DAG over the participant subnet's scoped TCP/8080 route with
its planted credential and writes the trained adapter into an Airflow-owned
runtime directory, proves 4318/4319 and research
HTTP paths are unavailable from the participant surface, injects collector
failure, repeats inference and receipt verification, measures enabled/disabled
gateway p95 with paired `on/off/off/on` 100-request windows, and validates the
exported event/manifests/missingness bundle. The strict telemetry overhead gate
is below five percent. Runtime producers keep event delivery off the request
path, reuse one bounded mTLS connection pool, and cache the immutable validated
research contract so connection setup and YAML parsing do not contend with
participant inference. Gateway calls to policy, model, and proof backends also
reuse bounded async connection pools instead of reconnecting several times per
inference. The performance sample accepts only valid responses from
the real model-evasion inference path but does not condition latency on whether
the stochastic model outcome satisfies the challenge; attack success remains a
separate required functional gate. Each participant program has a ten-minute
deadline so the 100-request sample cannot be misclassified as a failed marker
on a loaded range.

The sanitized durable result from the passing live run is
[`../docs/telemetry-rehearsal-report.md`](../docs/telemetry-rehearsal-report.md).

To run the automated participant rehearsal against an already-deployed range
without relaunching it, explicitly retain the tenant for Phase E:

```sh
tests/run-golden-rehearsal.sh \
  --project-id prod-ksqdkj \
  --range-instance kep-356-b1 \
  --participant operator \
  --participant-source-cidr 203.0.113.10/32 \
  --use-existing-range \
  --retain-until-phase-e
```

`--use-existing-range` never invokes `launch.sh` and is rejected unless Phase E
retention is also selected. The rehearsal still runs canonical health and reset
checks; teardown remains exclusively a later `cleanup.sh` action.

The sanitized durable result for module 02's passing manual walkthrough,
reliability campaign, integrated rehearsal, reset, and telemetry checks is
[`../docs/module-02-proof-report.md`](../docs/module-02-proof-report.md).

`launch.sh` first applies only the tenant network/registry foundation, builds
or mirrors every runtime image through Cloud Build, records resolved digests in
gitignored owner-only state, validates that lock, then creates runtime nodes.
Bootstrap-time public downloads and mutable image tags are not used.
The pack-root [`.gcloudignore`](../.gcloudignore) excludes `build/` from every
Cloud Build source archive because runtime Dockerfiles consume only the
SDL-declared source under `assets/`, `ctfd/`, `sdl/`, and `telemetry/` plus the
root ACES accessor. Generated Terraform providers, plans, state, image locks,
operator evidence, and credentials therefore never enter a runtime image build
context.

The same generated ACES realization owns the workload credential plan. Native
SDL dependencies identify the Module 10 gateway's read access to the artifact
store and write/verify access to the contained exfiltration sink. The renderer
projects those relationships together with the baseline component needs into
the Secret Manager member set consumed by Terraform; `main.tf` does not carry
a separate asset-to-secret map.

The foundation also reserves the participant workstation's external address
before secret seeding. That address is included only in the workstation TLS
certificate, and KasmVNC serves the generated range certificate. The rehearsal
trusts the range CA in an ephemeral browser profile; it does not disable
certificate validation.

Reset is fail-closed: it disables writes and receipts, increments the receipt
generation, resets every canonical owner, then requires negative gates and
health before returning to ready. Cleanup destroys only the namespaced tenant
resources and verifies that the tenant VPC is absent. It retains the supplied
project and never performs project or billing lifecycle operations.
The proof health endpoint constructs the complete 60-row challenge/flag/hint
join, so an incomplete SDL participant contract cannot pass reset readiness
while receipt issuance is unavailable.

## Participant-run telemetry

Participant telemetry implementation adds a separate observational plane without changing proof
authority. Runtime services export traces over internal mutual TLS on port 4318
and strict operational events over internal mutual TLS on port 4319. The
participant subnet has no route to either listener, and research paths return
404 on the participant-facing proof port. Collector, queue, or research-store
failure is fail-open for inference, workflows, proof, reset, and teardown.

`export-telemetry.sh` uses the existing owner-only Terraform state and IAP
operator channel. It creates a deterministic mode-0600 operational archive
containing pseudonymous ordered events, missingness, the schema/data dictionary,
resolved image digests, model/adapter/dataset/challenge/oracle/instrumentation
digests, and checksums. To export explicitly enabled full-content signals, add
`--content-output /operator/evidence/kep-355-a1-content.tar`; that archive is
separate, remains encrypted, and never contains the content key. The committed
Terraform defaults disable every full-content signal independently.

The proof runtime also includes `research_cli.py readback` for operator-only
reconstruction checks before archive handoff. It verifies the SDL-required
bundle members, checksums, manifest digests, ordered events, missingness, and
network-flow completeness records. For full-content bundles, readback verifies
ciphertext by default; adding `--decrypt-content` uses the range-local
content key to prove plaintext reconstruction by digest and byte count, and
`--include-content` is required before raw base64 plaintext is emitted.

Before export, the operator refreshes the proof node's digest-only image
manifest from the owner-only local lock. The host configuration directory stays
root-only; the non-secret manifest is mode `0644` because Docker presents this
single-file read-only bind mount as `root:root` to the non-root proof process.
The validated JSON is written through the existing host inode so a running bind
mount observes it. If the mounted digest is stale or unreadable, export restarts
and health-checks only the proof container before collecting the bundle.
Export destinations are cleared inside the proof container's writable bind
namespace before the fail-closed exporter creates them; host and container path
names are never assumed to be interchangeable.

The same export queries session-bounded VPC flow and firewall-decision logs in
bounded time batches, maps private addresses to topology asset ids, discards
unrelated project traffic, and destroys the raw owner-only temporary responses
after producing `network-flows.jsonl`. Operational output never contains
participant or service IP addresses. If Cloud Logging is partially unavailable,
export still completes and marks network capture partial/incomplete with batch
failure counts in `missingness.json`; if all batches fail, it marks network
capture unavailable/incomplete.

Reset records close/open lifecycle markers on a best-effort basis around the
canonical generation transition. Prior-session research data is retained for
export outside the reset-owned participant state. Cleanup still destroys all
range-local collectors and buffers; an archive copied to the explicit operator
destination is outside that tenant lifecycle.

## Fleet capacity planning

Enterprise and fleet design replaces multiplication of the proof topology with an explicit
total/active/busy fleet model:

```sh
python3 build/gcp/fleet_capacity.py
```

The source profile is
[`gcp/fleet-capacity-profile.json`](gcp/fleet-capacity-profile.json), and the
calculated assumptions and readiness boundary are documented in
[`../docs/fleet-capacity-model.md`](../docs/fleet-capacity-model.md).

The command exits nonzero for malformed profiles, insufficient deployment-cell
capacity, forbidden total- or active-range VPC/firewall/repository/GPU scaling,
missing shared-resource protections, or a fleet firewall envelope above the
policy maximum. A successful calculation is not a capacity proof:
`readiness.capacity_proven` remains false until every demand input is measured,
every relevant provider quota is known, and no quota expansion remains
outstanding. This is planning evidence for the disposable GCP golden
realization, not ACES semantics or a future backend allocation contract.
