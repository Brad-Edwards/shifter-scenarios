# ARWC native IT development

Run this stack only on `cinder-arwc-dev` in the approved development project.
Use the repository development-range skill for IAP access and source transfer.
The qualified OT stack remains a separate Compose project.

From this directory on the development VM, use:

```sh
sudo bash manage.sh build
sudo bash manage.sh up
sudo bash manage.sh seed
sudo bash manage.sh seed-documents
sudo bash manage.sh seed-reports
sudo bash manage.sh seed-engineering
sudo bash manage.sh seed-dmz
sudo bash manage.sh seed-portal
sudo bash manage.sh seed-early-cards
sudo bash manage.sh status
```

`build` downloads the pinned upstream images and builds the small BIND and
Kerberos images. `up` uses only installed images and waits for product health;
it neither builds nor pulls images. The seed commands use supported product
interfaces and leave existing records in place.

The participant engineering desktop uses the authoritative DNS service and
trusts the private CA. The native product hosts are `erp.arwc.test`,
`documents.arwc.test`, `reports.arwc.test`, `engineering.arwc.test`, and
`identity.arwc.test`. The DMZ hosts are `suppliers.arwc.test`,
`render.arwc.test`, and `read-data.arwc.test`. Existing OT short names remain
available.

Generated credentials and CA material stay in `.operator`, excluded from Git
and source archives. Only the three PostgreSQL init-role password files belong
to the pinned image's PostgreSQL user; each is mode `0400`. The public CA copy
in the participant desktop is readable. Private keys are not delivered there.

Coordinate the test window before reset:

```sh
sudo bash manage.sh reset cinder-arwc-native
```

Reset removes this native IT project's volumes and replays initialization and
all six product seed steps. The database initializes its approved read-only
DMZ views before PostgREST starts. For an existing native IT database, run
`seed-dmz` once after installing its new secret mount. Reset does not reset
the qualified OT project. Company data,
department sharing, planning reports and engineering repositories must pass
participant checks after reset before this stack is accepted for delivery.
