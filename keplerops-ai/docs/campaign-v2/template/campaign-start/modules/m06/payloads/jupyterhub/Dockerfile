ARG JUPYTERHUB_BASE_IMAGE
FROM ${JUPYTERHUB_BASE_IMAGE}
RUN python -m pip install --no-cache-dir jupyterhub-kubespawner==7.0.0 jupyterhub-dummyauthenticator==0.3.1 kubernetes==33.1.0
COPY payloads/jupyterhub/jupyterhub_config.py /srv/jupyterhub/jupyterhub_config.py
COPY payloads/workbench/START-HERE.md payloads/workbench/SERVERLESS-PUBLISH.md /opt/cinder-seed/
COPY integrations.json /opt/cinder-seed/integrations.json
WORKDIR /srv/jupyterhub
CMD ["jupyterhub", "-f", "/srv/jupyterhub/jupyterhub_config.py"]
