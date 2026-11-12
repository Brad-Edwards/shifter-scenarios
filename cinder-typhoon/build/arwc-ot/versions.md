# Qualified product versions

These inputs were exercised together on the dedicated compatibility VM.
Image references in `compose.yaml` and the Dockerfiles contain immutable digests.

| Product | Version | License at the selected release | Build input |
| --- | --- | --- | --- |
| OpenPLC Runtime | 4.3.2 | GPL-3.0-only | Official image plus the source-hash-guarded application-URI correction |
| OpenPLC Editor | 4.3.4 | GPL-3.0-only | Official Linux AppImage |
| FUXA | 1.3.5 | MIT | Official image plus its supported `node-opcua` 2.149.0 plugin |
| node-opcua | 2.149.0 | MIT | `fuxa-plugin/package-lock.json` |
| PostgreSQL | 18.6, trixie image | PostgreSQL License | Official image |
| Telegraf | 1.39.1 | MIT | Official image; native OPC UA input and PostgreSQL output |
| Eclipse Mosquitto | 2.0.22 | EPL-2.0 OR BSD-3-Clause | Official image; native TLS, password file, and topic ACL |
| Grafana OSS | 12.2.1 | AGPL-3.0-only | Official image and PostgreSQL datasource |
| Python fixture | 3.12.11, slim-bookworm | PSF-2.0; dependency licenses remain separate | Pinned base and `requirements.lock` |

License references: [Runtime](https://github.com/Autonomy-Logic/openplc-runtime/tree/v4.3.2),
[Editor](https://github.com/Autonomy-Logic/openplc-editor/blob/v4.3.4/package.json),
[FUXA](https://github.com/frangoteam/FUXA/blob/v1.3.5/LICENSE),
[node-opcua](https://github.com/node-opcua/node-opcua/tree/v2.149.0),
[PostgreSQL](https://www.postgresql.org/docs/18/license.html),
[Telegraf](https://github.com/influxdata/telegraf/blob/v1.39.1/LICENSE),
[Mosquitto](https://github.com/eclipse-mosquitto/mosquitto/blob/v2.0.22/LICENSE.txt),
[Grafana](https://github.com/grafana/grafana/blob/v12.2.1/LICENSE).

Preserve upstream notices and exact source references when distributing images.
The Runtime derivative includes a small patch; retain its upstream source and
patch with the image release. Grafana runs as a separate unmodified service.
The downstream bake must retain product notices and source availability information.

## Exact source inputs

| Source | Revision / SHA-256 |
| --- | --- |
| Runtime v4.3.2 | `9fb5e1a29b574806f5aea3a4e78202c7a5d658ee` |
| Editor v4.3.4 | `9e979504193b1fbacf87112822438664a1f7b11a` |
| FUXA v1.3.5 | `cf0a44c750c0ab89ef0e86ade9fb97fd0613ffca` |
| Editor AppImage SHA-256 | `b81863722d65eaa786f53234472601b649ea34a3f2f790f931beedaa7ec75fa0` |
| Original Runtime `server.py` SHA-256 | `544358a7a33fa3244dc6d4753253f17a6e7cdf01d04d5b004e16a8289c039f45` |

## Offline requirements

Download and build on the approved VM before removing Internet access. Keep
the complete official Editor AppImage, bundled toolchains, and extracted files.
Install its GTK, NSS, audio, GBM, DRM, X11, and Xvfb prerequisites during preparation.
The extraction avoids a FUSE dependency.

Bake the FUXA plugin during the image build. Its runtime plugin installer would
otherwise require npm access. Keep the locked dependency tree with the image.
Keep PostgreSQL, broker, collector, viewer, and fixture images in the private bake.
Runtime uses local product accounts and needs no external product account.

The offline Editor check uses an empty network namespace for compilation and
GUI startup. Container runtime checks use Docker internal networks. Installing
the complete participant workstation and its notices remains issue #368.
