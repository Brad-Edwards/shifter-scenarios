# KeplerOps registry foundation assets

`generation/build_registry_assets.py` deterministically produces the exact
K05-K08 registry seed and the corresponding Rowan workstation supplement.
The generated archives are the realization artifacts bound by the SDL content
modules; their unpacked inputs are described in `artifact-manifest.json`.

Regenerate from the repository root with:

```sh
python3 cinder-typhoon/assets/keplerops/registry/generation/build_registry_assets.py
```
