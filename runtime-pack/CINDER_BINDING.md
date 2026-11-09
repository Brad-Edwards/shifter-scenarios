# Binding the cinder-typhoon-direct pack

Use `cinder-typhoon-direct.binding.json` with pack version 0.1.0 and adapter
`panw.cinder-typhoon-direct` version 0.3.0. The binding names the three exact
private custom images in `prod-mgau4w`; it does not use image families.

| Target | Image | Machine | Disk | Capability |
| --- | --- | --- | --- | --- |
| Training | `cinder-training-event-20261109-02` | `e2-standard-2` | 40 GB `pd-balanced` | `preconfigured-machine-host` |
| KeplerOps | `cinder-keplerops-event-20261109-02` | `e2-standard-4` | 80 GB `pd-balanced` | `preconfigured-machine-host` |
| ARWC | `cinder-arwc-event-20261109-02` | `e2-standard-4` | 80 GB `pd-balanced` | `standard` |

Training readiness manifest:
`77a86d8595bcda3654cd0b1d38356dad1cfe0b9aa08305cdfc8af1e3de87f8cc`.

KeplerOps readiness manifest:
`a6054e790b1e3860a70ad66d60c67dd07abda21cf99b1a9c0b7ca5a7e10faa14`.

Before installation, compare the three image names and numeric image IDs with
the bake records. The adapter worker image digest is added here after the worker
image is published.
