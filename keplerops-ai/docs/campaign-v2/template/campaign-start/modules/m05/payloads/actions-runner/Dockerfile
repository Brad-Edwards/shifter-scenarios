FROM moby/buildkit:v0.25.1-rootless AS buildkit
FROM keplerops/forgejo-runner:campaign-v2-clean

COPY --from=buildkit /usr/bin/buildctl /usr/local/bin/buildctl

USER 1000:1000
ENV HOME=/home/runner
ENV BUILDKIT_HOST=tcp://m05-buildkit:1234
