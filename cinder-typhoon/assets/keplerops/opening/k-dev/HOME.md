# Rowan's FieldKest workstation

The connector checkout is under `work/fieldlink-connector`. Release-review
exports, samples and the local helper are kept under `work` as well.

The internal service paths used by the team are recorded in
`work/service-notes.md`.

Internal services use the workstation CA at
`~/.local/share/keplerops/ca.crt`. The usual command-line clients already trust
it. The local helper listens only on `127.0.0.1:8701`; its request examples are
in `work/local-helper.md`.

The support portal was closed before the workstation was handed over. Chromium
retained its ordinary profile under `~/.config/chromium/Default`.
