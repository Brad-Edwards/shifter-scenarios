FROM ghcr.io/autonomy-logic/openplc-runtime:v4.3.2@sha256:378deec33b371eb09f8344e714d88b48efc7387f631f793371ba9f6a6e381c9f
# The upstream plugin assigns an unused Python attribute. Set the actual
# asyncua application identity so the endpoint description matches its cert.
COPY patch_opcua_identity.py /tmp/patch_opcua_identity.py
RUN /workdir/venvs/runtime/bin/python3 /tmp/patch_opcua_identity.py
# Bake the plugin configuration so OPC UA is enabled after every container
# recreate. Without this the runtime copies plugins_default.conf on first
# start (OPC UA disabled) and OPC UA only starts after upload_fixture.py
# writes the enabled configuration — a step that does not run on recreate.
COPY plugins.conf /workdir/plugins.conf
