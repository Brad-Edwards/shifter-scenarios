# KeplerOps Fleet Capacity Model

The machine-readable planning envelope is
[`build/gcp/fleet-capacity-profile.json`](../build/gcp/fleet-capacity-profile.json).
Run:

```bash
python3 build/gcp/fleet_capacity.py
```

## Authority and portability

This is capacity and provider-planning evidence for the disposable GCP golden
realization. It is not ACES semantics, pack-local runtime control, or a
reference backend allocation contract. ACES governs portable placement,
isolation, shared-service, capability, and lifecycle intent; this profile
projects one way the golden provider could satisfy that intent.

A future delivery backend does not consume or copy this profile. It must admit
the capabilities required by the released ACES document, materialize and
control the scenario accordingly, and expose sufficient evidence to compare
its realized range with the golden range's declared observable contract.
Provider topology, quota shape, host packing, and allocation algorithms may
differ.

The profile distinguishes 200 allocated ranges, 100 active ranges, and 60
simultaneously busy participants. Those are separate multipliers:

- range prefixes, subnets, identities, and secrets scale with total allocated
  ranges;
- hosts, vCPU, memory, and disks scale with active ranges;
- inference throughput scales with simultaneously busy participants;
- VPCs, firewall policy, artifact repositories, and GPU workers scale by fleet
  or deployment cell, never by range.

The current planning bound uses two deployment cells, one range subnet per
allocated range, seven real kernels per active range, and a shared inference pool.
With 25 percent headroom it calculates 2 VPCs, 250 subnets, 260 firewall rules,
875 instances, 6,500 vCPUs, 24,000 GiB memory, 128,000 GiB persistent disk,
875 range-host service accounts, 9,750 range secrets, and an eight-L4 maximum
Cloud Run GPU envelope. The seven range kernels are the packed
application carrier, separately trusted nested-worker carrier, proof/control
carrier, AD domain controller, workforce workstation, ML-engineering
workstation, and participant endpoint.

The firewall total is ten fixed cell-policy rules plus 250 range-isolation
rules. One isolation rule admits only the source CIDR and target tag for one
range. It therefore scales once per allocated range, not once per logical
route, workload, service, or route direction.

These values are planning bounds, not measurements. The report deliberately
sets `capacity_proven` to false while any demand input is not measured, a
provider quota is unknown, or a known quota needs expansion. The only retained
account limit is the previously observed 500-rule global firewall quota; a
read-only quota refresh on 2026-07-24 failed because the current gcloud
principal lacked `compute.projects.get` on `prod-ksqdkj`.

The profile forbids VPCs, fixed firewall policy, artifact repositories, and
GPUs from using either total-range or active-range multipliers. The separately
named isolation rule is the only permitted range-scaled firewall resource. The
model requires all protections to remain present and caps the total firewall
envelope at 320 rules. This prevents a return to one VPC, route-pair firewall
rules, one repository, or one GPU per range.

Before a readiness claim, replace every `planning_bound` resource with measured
p50/p95/max demand from representative ranges, record current regional and
global quotas, exercise startup/reset waves, and rerun the model. Quota
expansions are then the positive differences in
`quota_expansions_required`; unknown quota values remain explicit rather than
being guessed.

## Golden cell lifecycle

The GCP source has separate cell and range lifecycles. A cell variable file
declares its project, cell ID, region, participant source CIDRs, and
range-to-subnet map. The cell launcher:

1. creates the shared VPC, subnets, fixed and range-isolation policy, state
   bucket, and Artifact Registry repository;
2. renders the RAES realization and publishes every immutable image once;
3. validates the resulting digest lock; and
4. activates the digest-pinned shared vLLM service with its private
   `run.app` DNS zone.

Run it with operator-owned state outside the pack:

```bash
build/gcp/cell/launch.sh \
  --var-file /operator/keplerops-cell.auto.tfvars.json \
  --state /operator/keplerops-cell.tfstate
```

Its JSON output provides `range_subnet_self_links`,
`shared_model_service_name`, and `shared_model_service_url`; the final
`image_lock=` line names the cell image lock. Pass the selected subnet,
shared-model outputs, and that lock to `build/launch.sh`. Range launch never
publishes images and never creates or destroys cell resources.

The range application carrier is the only Cloud Run invoker. The gateway asks
the GCE metadata server for a Google-signed identity token whose audience is
the exact cell model URL, caches it only until shortly before expiry, and sends
it on model requests. Cloud Run validates the caller identity. The model
service has no MinIO credential, range database, alias store, receipt key, or
reset-generation input. Each range separately materializes the verified
teacher artifact into its own MinIO surface for challenge workflows.
