# Cinder Forgejo → Harbor → Knative

1. Create a repository with the assigned Forgejo identity
   `cinder-field-operator`. Commit a container listening on port 8080 whose
   `/health` JSON contains the exact Forgejo commit as `source_revision`. Add
   OCI label `org.opencontainers.image.revision` with the same value.
2. Request that repository's registry identity with
   `curl -fsS --user cinder-field-operator:Cinder-Field-Operator-Git-V6n4Qs8p -X POST https://releases.cinder.lab/v1/repositories/REPOSITORY/credentials`.
   In Forgejo Actions, use `buildctl --addr tcp://cinder-buildkit:1234 build`
   with the checked-out directory as the local context. Push only
   `registry.keplerops.lab/cinder/<repository>:<tag>`. The two Harbor secrets
   exist only on that Forgejo repository and the Harbor robot is restricted to
   `cinder/<repository>`. Resolve and retain the manifest digest.
3. Publish a harness release first. It must bind the successful Actions run,
   exact source commit, Harbor digest, harness manifest, and executable
   `ci/validate-orion-harness`. Use `ci/harness-release.yml`; upload its exact
   digest map as `kep-m06-q-provenance/provenance.json`, and supply that file's
   SHA-256 to the release request. Save the returned record and exact SHA-256.
4. Stage the Knative service through the forced-command Cinder deployment
   gateway:

   ```sh
   ssh -i ~/.cinder/publisher/id_ed25519 \
     -o UserKnownHostsFile=~/.cinder/publisher/known_hosts \
     cinder-publisher@192.168.78.30 \
     "deploy SERVICE IMAGE@sha256:DIGEST DOMAIN.cinder.lab COMMIT HARNESS-URL HARNESS-SHA256"
   ```

   The command accepts no shell syntax. It reacquires the harness record,
   verifies commit/image/actor continuity, creates the Knative Service and
   DomainMapping, and creates a service-specific ingress/egress NetworkPolicy.
5. Complete Cinder Domains as separate native actions: Keycloak-backed account,
   domain, PowerDNS records, Stalwart mail name, live service body, ACME order,
   and the exact live certificate. Save the immutable ownership manifest URL
   and SHA-256.
6. Record the real first-request → zero-replica → cold-start cycle:

   ```sh
   ssh -i ~/.cinder/publisher/id_ed25519 \
     -o UserKnownHostsFile=~/.cinder/publisher/known_hosts \
     cinder-publisher@192.168.78.30 \
     "lifecycle SERVICE COMMIT IMAGE@sha256:DIGEST DOMAIN.cinder.lab OWNERSHIP-URL OWNERSHIP-SHA256 HARNESS-URL HARNESS-SHA256"
   ```

   Read the resulting immutable record from
   `https://knative.cinder.lab/v1/lifecycles/<lifecycle-id>`.
7. For staging, the deployed image must be a Cinder-controlled LiteLLM front
   exposing only `glm-5.2`. Keep its route credential separate from the
   upstream edge credential. Commit the Cosign public key beside the source;
   do not supply an arbitrary key URL. The signed manifest binds commit, image,
   route, staged object digests, domain ownership, Knative lifecycle, and
   harness release.

Deleting a failed deployment is allowed. Once a lifecycle record exists, the
publisher refuses deletion; full-range reprovisioning is the only operation
that removes an accepted endpoint.
