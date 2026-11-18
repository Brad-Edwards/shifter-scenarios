# Binding the cinder-typhoon-direct pack

Use `cinder-typhoon-direct.binding.json` with pack version 0.1.9 and adapter
`panw.cinder-typhoon-direct` version 0.3.2. The adapter binding contains only
the three compiled node addresses. Register
`cinder-typhoon-direct.image-mappings.json` through BigRAE's RAES Image Registry
to map the SDL sources to the exact private images in `prod-2hl4ce`.

Pack content digest:
`sha256:35db7192b4afc64fa51065d839d0be37a597767de460ad7e0f64e5f26612c913`.

Adapter worker:
`ghcr.io/paloaltonetworks/shifter-scenarios/runtime-adapter@sha256:7b2071a27958ae3bab71f5fff072cb41fbe3d9095cf35b20ef675b79641161d8`.
Install it with
[`cinder-typhoon-direct.manifest.json`](../runtime-adapter/cinder-typhoon-direct.manifest.json).

Training and KeplerOps image source commit:
`d595137fcf093c2105b20c7488716a7d46d37fbf`.

ARWC image source commit:
`1eb9dbbe415f2ed7efb7d4715b30b3bc66abfaeb`.

| Target | Image | Numeric image ID | Machine | Disk | Capability |
| --- | --- | --- | --- | --- | --- |
| Training | `cinder-training-event-20261117-01` | `7824232850606066145` | `n2-standard-2` | 40 GB `pd-balanced` | `preconfigured-machine-host` |
| KeplerOps | `cinder-keplerops-event-20261117-03` | `1569265548428132476` | `n2-standard-8` | 100 GB `pd-balanced` | `preconfigured-machine-host` |
| ARWC | `cinder-arwc-event-20261117-03` | `1634262727332550818` | `n2-standard-4` | 80 GB `pd-balanced` | `standard` |

Training readiness manifest:
`77a86d8595bcda3654cd0b1d38356dad1cfe0b9aa08305cdfc8af1e3de87f8cc`.

KeplerOps readiness manifest:
`a6054e790b1e3860a70ad66d60c67dd07abda21cf99b1a9c0b7ca5a7e10faa14`.

Participant candidate manifest:
`c64b952d29732320f77ce1cec6d42e5991f5b70cab929365026e6e5c700b8e87`.

Release manifest:
`9d1f5520ed7e778d293624b1d361ecb3ebe1373b3ee5b23e2354f84c1f9707c3`.

Before installation, compare the three image names and numeric image IDs with
the `prod-2hl4ce` image records. Do not copy the image mappings into the adapter
binding; BigRAE's image registry owns image selection and realization.
