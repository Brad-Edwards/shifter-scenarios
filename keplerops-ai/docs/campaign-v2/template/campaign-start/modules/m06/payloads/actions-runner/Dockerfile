FROM moby/buildkit:v0.25.1-rootless AS buildkit
FROM keplerops/forgejo-runner:campaign-v2-clean
COPY --from=buildkit /usr/bin/buildctl /usr/local/bin/buildctl
USER 0:0
RUN /opt/kepler-ci/bin/pip install --no-cache-dir \
      numpy==2.2.6 \
      onnxruntime==1.22.1 \
      tokenizers==0.21.4
USER 1000:1000
ENV BUILDKIT_HOST=tcp://cinder-buildkit:1234
