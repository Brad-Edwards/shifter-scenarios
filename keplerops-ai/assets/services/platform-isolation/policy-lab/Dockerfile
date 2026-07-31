ARG OPA_IMAGE=openpolicyagent/opa@sha256:44f0f4b1c09260eaf5e24fc3931fe10f80cffd13054ef3ef62cef775d5cbd272
ARG BASE_IMAGE=python@sha256:5f55cdf0c5d9dc1a415637a5ccc4a9e18663ad203673173b8cda8f8dcacef689
FROM ${OPA_IMAGE} AS opa
FROM ${BASE_IMAGE}

RUN groupadd --system --gid 65532 keplerops \
    && useradd --system --uid 65532 --gid keplerops --home-dir /nonexistent keplerops \
    && install -d -o keplerops -g keplerops -m 0700 /var/lib/keplerops-policy-lab

COPY --from=opa /opa /usr/local/bin/opa
COPY assets/services/platform-isolation/policy-lab/opa-config.yaml /etc/keplerops-policy-lab/opa-config.yaml
COPY assets/services/platform-isolation/policy-lab/policy-lab.rego /etc/keplerops-policy-lab/policy-lab.rego
COPY assets/services/platform-isolation/policy-lab/system-authz.rego /etc/keplerops-policy-lab/system-authz.rego

USER 65532:65532
EXPOSE 8182
HEALTHCHECK --interval=10s --timeout=3s --retries=6 \
  CMD ["python3", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8182/health', timeout=2).read()"]
ENTRYPOINT ["/usr/local/bin/opa"]
CMD ["run", "--server", "--addr=0.0.0.0:8182", "--authentication=token", "--authorization=basic", "--config-file=/etc/keplerops-policy-lab/opa-config.yaml", "/etc/keplerops-policy-lab/policy-lab.rego", "/etc/keplerops-policy-lab/system-authz.rego"]
