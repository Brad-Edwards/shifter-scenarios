# FieldLink native cloud, data and assistant

Issue 401 replaces the remaining cloud, stored-data and assistant product
facades. This phase covers ordinary application operation and connections.
Challenge changes remain paused.

| Product | Native responsibility | State |
| --- | --- | --- |
| K3s | One Kubernetes server, namespaces, RBAC, Jobs, CronJobs and logs | Native server and local workload volumes |
| PostgreSQL | Relational company records in a separate database and role | Existing PostgreSQL volume |
| SeaweedFS | Native S3 objects, versions, exports and backup files | One node with persistent native storage |
| AnythingLLM | Users, workspaces, conversations, retrieval and tools | Native storage and built-in LanceDB |
| Ollama | Local inference from the existing Qwen weights | Native model store |

Use the upstream single-server container pattern for K3s. Its required
privileged container stays on the existing isolated development VM; ordinary
workloads receive restricted namespace policy and scoped RBAC. Keep the admin
kubeconfig private. The participant receives only the intended developer
configuration through a missing-only profile seed. Do not publish a dashboard
or introduce an admission service.

Keep the existing PostgreSQL service running. Add a separate company-data role
and database through normal SQL administration. Native TLS, SCRAM and database
permissions protect the connection; the existing edge passes the PostgreSQL
protocol through unchanged. Neither the data role nor its client configuration
contains identity or workplace database authority.

Use a single official SeaweedFS process for its supported native S3 service.
Keep product-managed object metadata and versions in persistent storage. Native
clients use ordinary S3 requests and product authorization, without replacement
JSON object or backup routes.

AnythingLLM connects directly to Ollama and uses its built-in LanceDB. Import
the existing `Qwen/Qwen2.5-3B-Instruct` weights at revision
`14d7620ba47cf51be0b176e14e27e38a34d4ff88` through upstream llama.cpp conversion and quantization into GGUF, followed by
Ollama's supported local import. This Ollama release does not directly import
the retained Qwen2 Safetensors architecture. Keep inference on CPU with one parallel request, a bounded
context and native quantization where supported. Preserve the old model files
and stop the replaced model process before loading the native model. Do not
change the model silently or add an external inference/vector service.

The existing HTTPS edge serves fixed native application names and ports.
Applications retain their own UI, API, errors and normal accounts. Only the
genuine FieldLink support action remains an assistant integration. No token or
session exchange service is required.

## Lifecycle and resources

Build and import only on `cinder-fieldlink-dev` in `prod-mgau4w`. The initial
capacity check found 12 GB available RAM and 28 GB free disk. Native node
scheduling also requires free disk above the unchanged kubelet pressure
thresholds; the development boot disk is expanded to 100 GB for the complete
product set and a private backup. Pull pinned
images before starting services; check actual memory after importing the model.
Do not run both old and new model servers. Coordinate public DNS, desktop,
edge or PostgreSQL changes with the active QA window.

Keep all native product state in named volumes. Initial imports fill missing
state only; ordinary restarts preserve users, records and user configuration.
Use manual setup/reset steps and product-native export/restore tools. No bake,
CI build pipeline or additional orchestration framework is required. QA checks
normal product operation, roles, connectivity and persistence through the
participant desktop; final pristine initialization remains a separate check.

References: [K3s single-server container pattern](https://github.com/k3s-io/k3s/blob/main/docker-compose.yml),
[Kubernetes Pod Security admission](https://kubernetes.io/docs/concepts/security/pod-security-admission/),
[PostgreSQL TLS](https://www.postgresql.org/docs/16/ssl-tcp.html),
[SeaweedFS S3](https://github.com/seaweedfs/seaweedfs/wiki/Amazon-S3-API),
[AnythingLLM Docker](https://github.com/Mintplex-Labs/anything-llm/blob/master/docker/HOW_TO_USE_DOCKER.md),
and [Ollama local import](https://docs.ollama.com/import).

## Development disk growth

The qualified clone uses `/dev/sda1` with ext4. After the guarded cloud disk
increase, verify that the block device is 100 GiB and that this is still the root
partition. If the partition has not yet grown, the standard online steps are:

```bash
sudo apt-get install --no-install-recommends cloud-guest-utils
sudo growpart /dev/sda 1
sudo resize2fs /dev/sda1
df -h /
```

The small native growth utility avoids an interactive partition prompt. This
procedure completed without an application restart. Keep normal kubelet storage
thresholds; the bootstrap waits for native disk pressure to clear and verifies
the qualified client image through the native CRI before reporting workload
readiness. Its archive uses K3s's existing watched offline image directory, so
K3s owns import and pinning across startup and cache recovery. See the upstream
[image import procedure](https://docs.k3s.io/add-ons/import-images).

## Current operation

Docker's internal-network filter can reject routed traffic before it reaches the
range router. `native-platform/host-routing.py` uses Docker's supported
`DOCKER-USER` hook only for same-bridge transit between the five declared private
router networks. It validates the actual project, addresses and bridge identities.
The router retains its existing port and role rules; host inter-bridge traffic,
external addresses and other ranges receive no exception. Startup, reset and
recovery reconcile only this range's own chain against the current bridge IDs.
See [Docker's firewall guidance](https://docs.docker.com/engine/network/firewall-iptables/).

Use the guarded development wrapper for access and source synchronization. The
old golden deployment script is disabled. Build changed images on the development
VM, then coordinate any application, DNS, edge, desktop or PostgreSQL change with
QA. The native product helpers initialize databases before dependent applications
and Kubernetes credentials before the missing-only desktop seed.

The retired Python cloud, workload, data and assistant product services are no
longer started. The runner retains only genuine isolated report and package
execution; its former command, workload and completion APIs are removed. Existing
challenge callers of those interfaces require later content work, which remains
paused. Do not add compatibility routes for them.

Use the [preserved reset runbook](../../build/keplerops/native-platform/preserved-reset.md)
to make a consistent private backup before any destructive development reset.
Keep the original model and offline Kubernetes images cached on the VM. Reset
clears mutable product seed markers and regenerates native workspace credentials;
ordinary service restarts preserve user changes. Restore the accepted working
state after QA checks fresh initialization. ARWC and its earned destination state
remain outside this reset.
