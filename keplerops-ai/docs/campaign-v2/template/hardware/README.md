# KeplerOps Physical Lab Client

The participant workstation reaches the labgrid coordinator on the isolated
hardware network. `LG_COORDINATOR` is preconfigured; normal reservation,
acquisition, driver, video, SSH, and release commands run directly from Kali.

The workstation copies the bench SSH identity from its provisioned
read-only mount into the participant account at startup. The normal labgrid
environment for bench control is `/etc/labgrid/participant-remote.yaml`.

The clean-enterprise acceptance path reserves one operational, non-spare place
through the pool tags, acquires it with the opaque reservation token, and
releases it. Physical-operation acceptance additionally executes the current
liveness, camera, actuator, light, telemetry, and evidence contract against a
real exporter-backed place.
