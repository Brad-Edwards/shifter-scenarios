# Binding the cinder-typhoon-direct pack

Use `cinder-typhoon-direct.binding.json` with pack version 0.1.0 and adapter
`panw.cinder-typhoon-direct` version 0.3.1. The adapter binding contains only
the three compiled node addresses. Register
`cinder-typhoon-direct.image-mappings.json` through BigRAE's RAES Image Registry
to map the SDL sources to the exact private images in `prod-mgau4w`.

Pack content digest:
`sha256:29b50b546906a5e7ccaa55b1653481df6d6dc55c3815d294f1a915be5767ddbf`.

Adapter worker:
`ghcr.io/paloaltonetworks/shifter-scenarios/runtime-adapter@sha256:cabeb7b75667678f78fb325253ce41fc96c8d8eaa16e5c1de4b2adc20165026a`.
Install it with
[`cinder-typhoon-direct.manifest.json`](../runtime-adapter/cinder-typhoon-direct.manifest.json).

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
the bake records. Do not copy the image mappings into the adapter binding;
BigRAE's image registry owns image selection and realization.
