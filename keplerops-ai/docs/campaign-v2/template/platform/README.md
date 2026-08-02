# KeplerOps campaign-v2 platform plane

This directory materializes the clean platform and release plane described by
the campaign-v2 contracts. It targets the existing single-node `k3s01` guest
(`192.168.78.30`, k3s `v1.33.2+k3s1`, 4 vCPU/16 GiB) and installs:

- Argo CD with a constrained `orion-platform` AppProject;
- cert-manager and KServe in `RawDeployment` mode;
- the KServe control plane needed to admit the campaign's exact clean
  release-risk model after m07 establishes its training lineage;
- OPA with a generic immutable-release policy;
- LiteLLM backed by Vertex AI GLM 5 through renewable GCE workload identity;
- a minimal LangGraph API and standards-based MCP streamable HTTP server;
- step-ca signer enrollment and cosign blob signing helpers.

The bundle contains no campaign state, challenge logic, flags, proof broker,
or hidden verifier. Core installation deliberately creates no release-risk
`InferenceService`: an unsigned placeholder is not a valid clean-enterprise
model identity.

## Deploy

Run from the existing template host after foundation and `k3s01` are healthy:

```bash
cd keplerops-ai/docs/campaign-v2/template/platform
sudo ./scripts/deploy-to-k3s01.sh
```

The deploy helper builds the shared agent and vision images, imports them into k3s
containerd, copies this directory to `/opt/keplerops-platform`, and runs the
idempotent core installer. It does not seed Argo or deploy a release-risk
model. It also copies the existing step-ca root and `step`
client from `kep-v2-step-ca` when that container is available. No registry is
required for the two local images on the single-node range.

The admitted GLM 5.2 assistant identity uses Vertex AI's
`zai-org/glm-5-maas` model. A small
in-cluster OpenAI adapter obtains renewable access tokens from the nested
host's GCE workload identity; no service-account key is stored in the range.
The template host service account therefore requires `roles/aiplatform.user`.
An operator can override the admitted endpoint when needed:

```bash
sudo ORION_ASSISTANT_BASE_URL=http://MODEL_HOST:PORT/v1 \
  ORION_ASSISTANT_API_KEY=synthetic-or-provider-key \
  ./scripts/deploy-to-k3s01.sh
```

The endpoint is expected to serve the model name selected by
`ORION_ASSISTANT_UPSTREAM_MODEL`.

## Clean release materialization

After campaign modules m01-m07 have converged, the shared
`scripts/materialize-clean-release.sh` entry point reads m07's canonical
`baseline-export-sha256`. The candidate builder selects only a finished MLflow
run with that exact export digest and matching Forgejo/lakeFS/provenance
lineage. It builds the digest-addressed image and immutable candidate; the
promotion helper writes the rendered KServe definition to Forgejo, pins Argo
to the resulting commit, admits it through KServe, and signs the release.
The orchestration then captures and signs the running Vertex GLM 5.2 identity,
activates both identities in the business plane, and runs continuity and full
readiness before m08 begins.

Resume reuses an existing candidate only when its files and m07 baseline join
exactly. It reuses a release only when its signature, candidate, GitOps,
KServe, and live model joins already pass; otherwise it rebuilds or promotes.
Manual GitOps adoption remains available:

```bash
sudo GITOPS_REPO_URL=http://10.61.40.20:3000/OWNER/REPO.git \
  GITOPS_REVISION=0123456789abcdef0123456789abcdef01234567 \
  /opt/keplerops-platform/scripts/configure-gitops.sh
```

Set `ARGO_REPO_USERNAME` and `ARGO_REPO_TOKEN` for a private repository. The
script creates an Argo repository Secret without persisting the credential to
this bundle. Argo then adopts the bootstrap-applied `InferenceService` and
reconciles it from the pinned revision.

## Release record

`scripts/release-orion.sh` accepts immutable stage identities as environment
variables, canonicalizes a release record with `jq -S`, obtains OPA approval,
creates an in-toto Statement, signs it with cosign, and verifies the resulting
signature. It writes only to `RELEASE_OUTPUT_DIR` (default
`/var/lib/keplerops-platform/releases/<release-id>`). Run
`scripts/release-orion.sh --help` for the required fields.

The script does not commit, push, deploy, or claim transparency publication.
The deployment handoff is the rendered GitOps patch it emits. A
Rekor-compatible service and an OCI registry are not present in the current
template, so transparency inclusion and registry-side cosign signatures remain
explicit integration blockers.

The local cosign key remains encrypted at rest. Its public-key digest is bound
into `signer-identity.json`, which is signed and verified with the short-lived
`svc-orion-signer` key issued by step-ca. Release signing only occurs after an
OPA allow decision.

## Readiness

On `k3s01`:

```bash
sudo /opt/keplerops-platform/scripts/readiness.sh --core
sudo /opt/keplerops-platform/scripts/readiness.sh
```

Core mode checks Kubernetes, Argo CD, cert-manager, KServe controllers, OPA,
LiteLLM process health, LangGraph, MCP, vision, and local signing material; it
does not accept any release-risk workload. Full mode additionally verifies the
signed current release and assistant records, rejects placeholder identities,
performs a real assistant completion, and requires exact release-to-Argo and
release-to-KServe revision/model/image/live-runtime joins.

## Known integration blockers

- The template currently has no OCI/Harbor registry. Local image import is
  appropriate only for the single-node baseline; multi-node scale requires a
  digest-addressed registry.
- Vertex GLM access depends on the template host service account retaining
  `roles/aiplatform.user` and the Vertex AI API remaining enabled.
- No Rekor-compatible transparency service is present. Cosign produces and
  verifies a local bundle, but cannot prove log inclusion.
- Existing Caddy and DNS files are outside this directory and have no Argo,
  LiteLLM, MCP, or model routes. Services are cluster-internal except the Argo
  CD NodePort (`30080`) until those clean-plane routes are added.
- The foundation Caddy uses its own internal CA while signer enrollment uses
  step-ca. Forgejo over HTTPS needs Caddy's root CA installed in Argo; the
  documented direct internal HTTP URL avoids pretending the trust roots agree.
- Argo CD starts with its upstream bootstrap administrator. Keycloak OIDC and a
  dedicated `svc-orion-release` credential require an existing realm client
  and secret that are not supplied by the campaign-v2 template yet.
- Namespace ingress is restricted, but egress remains open so Helm and an
  operator-selected assistant endpoint can work. Destination-specific egress
  policy requires the admitted endpoint address and internal registry routes.
