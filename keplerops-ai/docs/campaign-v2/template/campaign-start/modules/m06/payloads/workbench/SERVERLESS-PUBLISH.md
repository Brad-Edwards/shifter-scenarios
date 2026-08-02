# Cinder Serverless Publication

Cinder repositories can build an OCI image in Forgejo Actions, push it to
the `cinder` Harbor project, and deploy the immutable digest to the `cinder`
Knative namespace. The runner exposes a namespace-bounded publisher over SSH.

1. Build a service that listens on port 8080 and has `/health` return a response
   identifying the source revision.
2. Push `registry.keplerops.lab/cinder/<repository>:<tag>` with the Harbor
   credentials installed as `CINDER_REGISTRY_USER` and
   `CINDER_REGISTRY_PASSWORD` Forgejo Actions secrets.
3. Resolve the pushed manifest digest and run:

   `ssh -i /run/cinder-publisher/id_ed25519 -o StrictHostKeyChecking=yes -o UserKnownHostsFile=/run/cinder-publisher/known_hosts cinder-publisher@192.168.78.30 "deploy <service> registry.keplerops.lab/cinder/<repository>@sha256:<digest> <domain>.cinder.lab"`

4. Preserve the Forgejo commit, Actions run, Harbor digest, returned Knative
   revision, domain, TLS fingerprint, first request, visible scale-to-zero, and
   post-cold-start request in the lifecycle submission.

The publisher rejects other namespaces, mutable image references, unscoped
domains, and service names outside the Cinder publication contract.

Build the image with OCI label `org.opencontainers.image.revision` set to the
exact Forgejo commit. The relay health response must be JSON containing the
same value as `source_revision` so source, image, and live revision stay linked.
