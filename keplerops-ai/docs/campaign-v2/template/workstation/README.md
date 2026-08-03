# Participant Workstation Access

The workbench publishes the established workstation services on the carrier
loopback interface by default:

| Access | Host endpoint | Participant username |
|---|---|---|
| XRDP | `127.0.0.1:3389` | `kasm-user` |
| Kasm/noVNC browser | `https://127.0.0.1:8443/` | `kasm_user` |

Both use the synthetic password stored at
`state/workstation/participant-password`. The browser certificate is local to
the range, so direct access may require accepting that certificate. A
Guacamole-compatible gateway can target the XRDP endpoint from the carrier.

For operator access to a GCE carrier without opening new firewall ports, use
the existing SSH/IAP path and forward both loopback services:

```bash
gcloud compute ssh CARRIER_NAME \
  --project PROJECT_ID \
  --zone ZONE \
  --tunnel-through-iap \
  -- -N -L 13389:127.0.0.1:3389 -L 18443:127.0.0.1:8443
```

Connect an RDP client to `127.0.0.1:13389`, or open
`https://127.0.0.1:18443/` in a browser. Shifter may override
`PARTICIPANT_ACCESS_BIND_ADDRESS`, `PARTICIPANT_RDP_PORT`, and
`PARTICIPANT_WEB_PORT` when its cell-local access gateway owns exposure.

After startup, validate and display the contract with:

```bash
sudo /opt/keplerops-v2/scripts/workstation-access.sh check
sudo /opt/keplerops-v2/scripts/workstation-access.sh show
```
