FROM moby/buildkit:v0.25.1-rootless AS buildkit
FROM ghcr.io/sigstore/cosign/cosign:v2.4.1 AS cosign
FROM mikefarah/yq:4.44.6 AS yq
FROM keplerops/forgejo-runner:campaign-v2-clean

COPY --from=buildkit /usr/bin/buildctl /usr/local/bin/buildctl
# The blueprint drift audit (kep-m05-f/g) verifies the signed public blueprint
# with `cosign verify-blob`; the drift report is not produced without cosign on
# the runner host.
COPY --from=cosign /ko-app/cosign /usr/local/bin/cosign
# The agent-config publish workflow (kep-m05-m) validates agent.yaml with yq;
# without it the reconcile job fails at the validation step.
COPY --from=yq /usr/bin/yq /usr/local/bin/yq

USER 1000:1000
ENV HOME=/home/runner
ENV BUILDKIT_HOST=tcp://m05-buildkit:1234
