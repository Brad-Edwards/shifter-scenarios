FROM ghcr.io/autonomy-logic/openplc-runtime:v4.3.2@sha256:378deec33b371eb09f8344e714d88b48efc7387f631f793371ba9f6a6e381c9f
# The upstream plugin assigns an unused Python attribute. Set the actual
# asyncua application identity so the endpoint description matches its cert.
COPY patch_opcua_identity.py /tmp/patch_opcua_identity.py
RUN /workdir/venvs/runtime/bin/python3 /tmp/patch_opcua_identity.py
