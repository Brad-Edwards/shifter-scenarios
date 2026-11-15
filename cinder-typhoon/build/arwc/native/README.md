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
sudo bash manage.sh seed-corporate-documents
sudo bash manage.sh seed-reports
sudo bash manage.sh seed-engineering
sudo bash manage.sh seed-dmz
sudo bash manage.sh seed-portal
sudo bash manage.sh seed-early-cards
sudo bash manage.sh seed-identity
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

The corporate terminal is `workplace.arwc.test`, reached from the engineering
desktop using `ssh -i ~/.ssh/arwc-corporate morgan@workplace.arwc.test`.
The participant's private key stays in that engineering home. Startup installs
only its public key in the corporate workstation and registers the workstation's
public host key. The terminal has no sudo or forwarding. Normal `kinit`, `klist`,
`kdestroy`, Git and verified HTTPS clients run in its corporate context using
`/etc/krb5.conf`; KDC access does not add a network interface to the OT desktop.
Use the normal workforce principal and password, not an operator keytab.

Nextcloud's native `/cron.sh` companion uses the same pinned image, product
volume and private backend network. Startup selects native cron mode for
regular background housekeeping. The configured 30-day version retention
remains unchanged. This follows the upstream [Docker cron example](https://github.com/nextcloud/docker)
and [background job guidance](https://docs.nextcloud.com/server/latest/admin_manual/configuration_server/background_jobs_configuration.html).

Imported workforce users retain Keycloak's stock `default-roles-arwc` role for
ordinary own-account pages and credential management. It does not confer realm
administration. For an existing import missing this baseline, the explicit
`seed-identity.py --repair-account-access` operation restores only that role,
additively, without reseeding users/documents or changing passwords and sessions.

Generated credentials and CA material stay in `.operator`, excluded from Git
and source archives. Only the three PostgreSQL init-role password files belong
to the pinned image's PostgreSQL user; each is mode `0400`. The public CA copy
in the participant desktop is readable. Private keys are not delivered there.

Prepare and start native IT before rebuilding the customer connector. Its
retained handover reads only the generated `supplier-onboarding.json` and the
public root. The connector's `ARWC_NATIVE_OPERATOR_DIR` defaults to
`./native/.operator` relative to the parent ARWC Compose project; set it to
the native IT operator directory when the source trees are separate. The
handover supplies Jules's real account material. It does not exchange the
connector capability for another product's session or broader authority.

The engineering desktop mounts only the connector volume's `handover` subdirectory
read-only at `/var/lib/fieldlink-connector/handover`. Its ordinary `fieldlink`
login joins that directory's read group; neither connector receipts, candidates,
private customer state nor keys are mounted. Files appear only after genuine
customer delivery. `customer-transition.json` identifies the retained service,
and `corporate-session` carries its earned read capability. The authoritative
supervisory zone resolves `customer-handover.arwc.test` to `172.29.63.28`;
a fixed socat listener passes only port 8443 to `10.77.60.20:8443`, retaining
the connector's original end-to-end TLS identity. The relay's corporate address
is `10.77.60.16`; it has no host ports, keys, state volumes or forwarding.
The connector keeps its original networks and gains no supervisory interface.
The desktop trusts only the public customer-integration root in addition to the
native IT root. Docker Compose's documented read-only volume `subpath` feature
provides this filesystem boundary; it does not expose the complete connector volume.
See <https://docs.docker.com/reference/compose-file/services/#volumes>.
Before the first desktop start, `workstation/prepare-handover.sh` creates only
an empty `handover` directory if absent. Image initialization and desktop setup
call it before Compose; it neither creates earned files nor changes existing
files. Start the parent ARWC Compose project to include `handover-edge`; its
ordinary startup and retained reset use that checked service definition.

`early-card-evidence.py` compares W01-W03 submissions with a separately
collected, fresh `arwc.native-early-observation/v1` product snapshot. The
snapshot carries native ERPNext User, Task, Project, File, DocShare and Version
records; Nextcloud file IDs, contents, shares and version downloads; and native
PostgREST schema/results plus observed denial responses. It records the
instance, collection time and source digest. Keep this operator evidence
separate from the participant submission. The checker reads only these inputs
and cannot change products or manufacture a successful action.

The obsolete `a-distribution` W33 rehearsal facade has been removed from the
restored development VM and its old base/compatibility Compose state. The
retirement preserved all 52 other running containers, including the qualified
native dispatcher, OpenPLC, FUXA and historian. No OT operation or reset was
required. Current source and the W33 retirement manifest already exclude its
Dockerfile/controller; do not restore those deleted files.

Fresh PostgreSQL initialization loads the approved DMZ reporting view after
its underlying planning tables. Explicit reset also reapplies that view and
its narrow read-only grant. Ordinary `up` does not reseed product data.

Coordinate the test window and follow the [private backup and recovery steps](preserved-reset.md) before reset:

```sh
sudo bash manage.sh reset cinder-arwc-native
```

Reset removes this native IT project's volumes and replays initialization and
all product seed steps and the DMZ view grants. The database initializes its approved read-only
DMZ views before PostgREST starts. For an existing native IT database, run
`seed-dmz` once after installing its new secret mount. Reset does not reset
the qualified OT project. Company data,
department sharing, planning reports and engineering repositories must pass
participant checks after reset before this stack is accepted for delivery.

`seed-corporate-documents` moves only original archive members whose content
hash matches the ARWC-owned document package. It preserves their bytes and
uses the intersection of original per-record readers when identical content
has multiple source entries. Unassigned members from other business areas are
not imported. The destination `Retained corporate records` and all its parents
must be unshared. Native per-file, read-only user shares enforce the original
boundaries; an inherited or broader existing share stops the import. Existing
mapped workforce users and their passwords are preserved. New ordinary users
use the existing product provisioning pattern and the existing `Staff` group;
no synthetic permission groups are created.
