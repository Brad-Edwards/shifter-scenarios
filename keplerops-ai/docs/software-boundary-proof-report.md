# Software Boundary Live-Build Report

Software-foundation expansion expands the retained `gcp_full` range from the 15-node challenge
kernel to the complete SDL 0.73.0 software foundation. This is a pragmatic
pre-playtest build report, not a golden claim and not a challenge proof report.

## Scope and authority

The modular ACES SDL remained the only logical source. Its expanded realization
declares 46 real software features, 28 VM assets, ten networks, service ports,
routes, workload identities, runtime secrets, content bindings, and immutable
image sources. Terraform and the image publisher consumed the owner-only
rendering of that SDL; no topology, software-inventory, or runtime-image
manifest was added.

The build used the existing `prod-ksqdkj` project and retained range
`kep-455-r1`. It created no project, user account, billing attachment, or
parallel tenant. The final image lock contains all 28 runtime images and nine
auxiliary images as exact registry digest references.

## Runtime implementation structure

Service decomposition removes the shared gateway/proof/policy monolith as a delivery risk
without creating another scenario authority. `keplerops-runtime/app.py` is now
only a FastAPI composition root. Shared configuration, authentication, storage,
clients, telemetry, policy, catalog, and proof code live under
`keplerops_runtime/foundation` and `keplerops_runtime/proof`; challenge behavior
is split by the same Module 01 through Module 10 boundaries used by the modular
ACES SDL. All four runtime-derived Dockerfiles copy that package.

A recursive source contract fails when any runtime Python file exceeds 500
physical lines. Route-set validation preserves every prior endpoint, with the
source-implemented synthetic-spearphish campaign as the only addition. This is
a maintainability and build-integrity change; it does not add topology,
software inventory, challenge semantics, or participant proof outside the SDL,
and it does not convert the retained one-pass software gate into a golden claim.

## Live result

On 2026-07-19 the retained range reached the following bounded result:

- all 28 SDL-declared VMs were present and `RUNNING`;
- all 13 newly introduced nodes passed one focused real service-health gate;
- the 15 retained challenge-kernel nodes were not restarted merely to validate
  this expansion;
- the canonical seeder reconciled 61 SDL-derived secret bindings, reusing
  existing versions and adding only missing versions;
- the reviewed Terraform expansion and follow-up plans contained zero deletes
  and zero VM replacements; and
- the final source/state reconciliation changed only updateable startup
  metadata and did not reboot a node; the subsequent refresh-backed plan
  reported no changes.

The new-node gate covered these real surfaces:

| Asset | Focused live gate |
|---|---|
| `research-index-01` | OpenSearch cluster health and seeded index |
| `range-dns-01` | authoritative CoreDNS health and readiness on the SDL address |
| `public-sites-01` | NGINX discovery site health |
| `scan-services-01` | both bounded NGINX scan targets |
| `platform-impact-01` | contained-impact API readiness |
| `platform-ml-01` | document/vision workbench readiness |
| `mail-server-01` | Stalwart live health |
| `webmail-01` | rendered Roundcube plus real SMTP submission observed through IMAP |
| `text-generation-01` | local llama.cpp text-generation health |
| `image-generation-01` | OpenVINO FLUX.1 service readiness with PostgreSQL and MinIO dependencies |
| `platform-camera-01` | HTTPS/aiortc camera container health |
| `policy-lab-01` | isolated OPA policy-lab health |
| `platform-agent-01` | LangGraph API, isolation API, edge registry, detached rootless worker engine, and pinned worker preload |

## Defects closed during the gate

The one-pass live gate found and closed integration defects instead of treating
VM status as software proof:

- legacy Terraform startup-script state was migrated to updateable metadata
  without replacing retained VMs;
- CoreDNS binds its SDL-declared address instead of conflicting with the COS
  host resolver;
- Roundcube receives the writable application layer and correct internal port
  its upstream entrypoint requires;
- the mail readiness runner receives SDL-derived peer mappings and only the CA
  material required for its real SMTP/IMAP check;
- the bounded worker uses an ephemeral Docker client configuration and the
  restricted Artifact Registry address; and
- the nested rootless socket is normalized to the dedicated supplemental group
  before either controller starts.

## Evidence and limits

The final source gate passed all 301 build tests in one run, Terraform
formatting/validation, and the ACES, contract, oracle, portfolio, and GCP
validators. The retained live gate was one pass per new node. It did not run a
10/10 campaign, restart all services, or replay previously passing Modules 08
through 10.

This proves that the declared software foundation can be instantiated as real
software and that each new node reaches its local dependency-aware readiness
boundary. It does not prove participant usability, challenge quality, receipt
issuance through the new surfaces, reset closure for every new owner, or
end-to-end attack-path reliability. Those remain playtest, participant
walkthrough, scoped reset, and challenge implementation work. The pack remains
`draft`; no golden status is claimed.
