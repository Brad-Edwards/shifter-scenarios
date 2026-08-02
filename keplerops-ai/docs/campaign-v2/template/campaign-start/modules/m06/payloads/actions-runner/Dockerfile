FROM moby/buildkit:v0.25.1-rootless AS buildkit
FROM keplerops/forgejo-runner:campaign-v2-clean
COPY --from=buildkit /usr/bin/buildctl /usr/local/bin/buildctl
USER 1000:1000
ENV BUILDKIT_HOST=tcp://cinder-buildkit:1234
