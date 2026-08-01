# Materialization And Scale Contract

## Scope

This document states what any Shifter materializer must preserve for KeplerOps
AI Systems. It does not prescribe or implement Shifter's fleet scheduler. The
golden candidate and a 200-range event may use different physical packing while
remaining logically equivalent.

## Range Cell

A range is one isolated **cell slot**, not one cloud VPC and not necessarily one
outer VM. A backend may pack multiple cell slots onto a large nested-virtualized
host when it preserves the boundaries below.

Each slot contains:

- one isolated container network and persistent volume set for the per-range
  enterprise services in `component-catalog.md`;
- nested `dc01` and `dc02` guests for the real Samba AD forest;
- a nested graphical `kali01` guest;
- a nested `k3s01` guest or an equivalently isolated nested Kubernetes node;
- disposable `review01` and `integration01` guests created only while their
  queues require them; and
- per-range routes, DNS zones, PKI, identities, application databases, buckets,
  queues, repositories, models, flags, logs and business state.

These are logical/nested roles, not seven billable cloud instances per range.
The golden build may use one outer nested host for one slot; production may pack
several slots per larger host. The backend must not expose host or neighboring
slot administration to a participant.

## Isolation Classes

| Class | Examples | Sharing rule |
|---|---|---|
| A: range mutable | AD, mail, app databases, buckets, queues, repositories, prompts, retrieval, memories, models, flags, logs, business effects | Never shared across range identities. May use a shared physical database engine only with independently authenticated databases/roles and proven denial across tenants. |
| B: range execution | Kali, k3s namespace/node, disposable workers, CI/evaluation/training jobs | Scheduled on shared physical hosts with VM/container/cgroup/network isolation; no cross-range mounts, credentials, process visibility or metadata access. |
| C: immutable compute | GLM 5.2 weights, admitted victim foundation weights, read-only package/image caches | May be shared. Requests carry range identity; prompt/cache/log state is partitioned or disabled and mutable outputs return to Class A. |
| D: exclusive leased hardware | labgrid benches, camera, actuator, device | Shared serially through opaque exclusive leases; no overlapping range access or prior media. |
| E: Shifter control | provisioning, CTF score, organizer state | Outside the scenario trust boundary and never accepted as participant proof. |

## Network And Naming

- Backend-managed network collections contain repeated per-slot overlays and
  subnets. There is no VPC-per-range requirement.
- Zone policy compiles from the service matrix in
  `enterprise-architecture.md`; there are no bespoke per-operation firewall
  rules.
- Every range uses the same private hostnames under its isolated resolver view.
  Public range names map through backend ingress using an opaque range ID.
- AD DNS remains authoritative for `corp.keplerops.lab`; PowerDNS owns public
  and Cinder zones. Conditional forwarding is explicit.
- East-west traffic is denied except for catalogued service flows. Cross-slot
  traffic is denied before application authentication.

## Resource Envelope

The design target per simultaneously active slot, before measured tuning, is:

| Resource | Steady-state target | Burst/on-demand target |
|---|---:|---:|
| General CPU | 6 vCPU equivalent | 16 vCPU equivalent during CI/training/evaluation |
| RAM | 20 GiB | 32 GiB while one disposable worker and one model job run |
| Thin-provisioned persistent disk | 120 GiB | 180 GiB including participant artifacts and model revisions |
| Local GPU | 0 | 0; scheduled jobs use Class C shared accelerators |
| Disposable nested guests | 0-1 running | 2, queue controlled |

These are admission targets, not quota claims. Implementation measures the clean
baseline, graphical desktop, critical route, distillation, and full-catalog
peaks before the backend chooses host sizes, oversubscription, or cloud quota.
A candidate outside the envelope is a capacity finding; it does not silently
drop enterprise services.

For 200 active ranges, the materializer must admit all 200 slots plus shared
inference and hardware queues from measured envelopes. It may add outer hosts,
pack multiple slots per host, and scale shared pools. It may not reinterpret the
requirement as fewer active ranges.

## Shared Inference Contract

- Each range and user receives a distinct short-lived credential and request
  identity; no event-wide bearer token is exposed.
- Fair scheduling prevents one range from starving others. Per-request maximums
  protect service health, but the campaign imposes no puzzle-like query budget.
- Provider prompt logging and training use are disabled where supported;
  application and gateway logs contain metadata/digests, not protected prompt
  bodies.
- Prefix/KV/result caches are disabled across ranges or keyed by range and
  deleted at teardown.
- Victim application prompts, RAG, memory, tools and credentials remain in the
  per-range gateway; only the resolved inference request reaches shared compute.
- Cost/availability challenges target per-range Orion runtimes and cannot
  consume the shared event pool.
- Pool replicas are independently health checked, and loss of one replica
  cannot broaden authorization or expose another range's requests.

## Capacity And Isolation Proof

Before event readiness, the backend proves:

1. 200 slot manifests can be admitted under actual project/region quotas;
2. representative concurrent desktops remain usable;
3. critical-route web, mail, CI, model and business workflows meet their SLAs;
4. shared inference remains fair and range-isolated at the expected request
   concurrency;
5. a hostile range cannot resolve, route to, authenticate to, list, read,
   infer, or observe another range's Class A/B state;
6. destroying one cell removes all of its mutable state without affecting
   another cell or shared immutable weights;
7. physical reservations are exclusive and queue wait is visible; and
8. a failed outer host can be replaced from source without treating its image
   as the only copy of a range fix.

The golden range proves participant semantics and logical boundaries. The
production backend owns fleet packing and quota acquisition, but it must meet
this contract without changing the scenario's participant-visible behavior.
