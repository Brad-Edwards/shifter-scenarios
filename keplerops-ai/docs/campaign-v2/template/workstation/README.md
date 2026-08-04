# Participant Workstation Access

The workbench publishes the established workstation services on the carrier
host:

| Access | Host endpoint | Participant username |
|---|---|---|
| XRDP | `${PARTICIPANT_RDP_BIND_ADDRESS:-0.0.0.0}:${PARTICIPANT_RDP_PORT:-3389}` | `kasm-user` |
| Kasm/noVNC browser | `https://${PARTICIPANT_WEB_BIND_ADDRESS}:443/` | `kasm_user` |

Both use the synthetic password stored at
`state/workstation/participant-password`. On GCE-backed template ranges,
startup derives `PARTICIPANT_WEB_BIND_ADDRESS` from the carrier's primary IPv4
address and publishes Kasm/noVNC on port `443`, matching the Terraform
`participant_endpoint` output. The generated browser certificate includes the
carrier bind address and the GCE external address when metadata is available.
A Guacamole-compatible gateway can target the XRDP endpoint from the carrier.

For operator access to a carrier that is intentionally bound to loopback, use
the existing SSH/IAP path and forward both services:

```bash
gcloud compute ssh CARRIER_NAME \
  --project PROJECT_ID \
  --zone ZONE \
  --tunnel-through-iap \
  -- -N -L 13389:127.0.0.1:3389 -L 18443:127.0.0.1:8443
```

Connect an RDP client to `127.0.0.1:13389`, or open
`https://127.0.0.1:18443/` in a browser. Shifter may override
`PARTICIPANT_RDP_BIND_ADDRESS`, `PARTICIPANT_WEB_BIND_ADDRESS`,
`PARTICIPANT_RDP_PORT`, and `PARTICIPANT_WEB_PORT` when its cell-local access
gateway owns exposure.

After startup, validate and display the contract with:

```bash
sudo /opt/keplerops-v2/scripts/workstation-access.sh check
sudo /opt/keplerops-v2/scripts/workstation-access.sh show
```
