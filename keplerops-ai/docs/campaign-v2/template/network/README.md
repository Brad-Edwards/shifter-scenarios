# Clean-enterprise network enforcement

The Compose zone bridges provide addresses and service discovery. They do not,
by themselves, provide workload isolation. `compose-flows.tsv` is the admitted
workload graph, and `apply-compose-policy.sh` turns that graph into a
default-deny `DOCKER-USER` policy.

The enforcer enables `br_netfilter` so the policy also sees traffic switched
between containers on one bridge. It admits named service-to-service flows,
denies every undeclared path between `kep-v2-*` networks, admits the small set
of declared host or public-egress paths, and then denies other container
egress. External ingress still reaches published Caddy, Forgejo, Prometheus,
and step-ca ports through Docker's normal DNAT rules.

Nested guests are restricted sources, not a trusted network. Docker publishes
Qdrant, Redis, RabbitMQ AMQP, and WorkHub only on the libvirt gateway at
`192.168.78.1:16333`, `:16379`, `:15673`, and `:13000`. `DOCKER-USER` admits
only the declared source guest and translated container-port pairs, then
denies the entire `192.168.78.0/24` guest subnet access to every other managed
Docker address. The baseline checks the positive gateway paths, neighboring
unpublished ports, direct bridge-address denial, and rejection of each
publication from guests outside its declared workflow.

Install the unit only after the clean services have been initialized:

```bash
sudo network/install.sh
sudo baseline/network-segmentation.sh
```

The watcher reapplies the policy when managed containers start or stop. It also
discovers Jupyter single-user containers by their native
`hub.jupyter.org/username` label and grants only the declared research-service
paths. Re-run the baseline after changing a service network, destination port,
or flow.

Use `apply-compose-policy.sh remove` for an explicit rollback. Reconciliation
must treat a missing unit, disabled `br_netfilter`, or a failed adjacent-denial
probe as a build failure.

The Kubernetes manifest intentionally governs the three enterprise-owned
namespaces: `orion-platform`, `orion-runtime`, and `cinder`. Chart-owned control
planes (`argocd`, `cert-manager`, `knative-serving`, `kourier-system`, and
`kserve`) are not assigned guessed policies here; their generated manifests and
version-specific control flows must be reviewed before those namespaces can be
made default-deny.
