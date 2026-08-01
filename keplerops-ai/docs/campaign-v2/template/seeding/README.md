# Campaign v2 clean-enterprise seeding

This directory materializes the ordinary application state specified by the
campaign-v2 enterprise architecture. It creates users, groups, projects,
mailboxes, and routine company content. It does not create flags, planted
weaknesses, challenge endpoints, attack artifacts, or participant shortcuts.

All credentials in `config.env` are synthetic training credentials committed
for deterministic range construction. They are not production secrets.

## Run

From this directory:

```bash
./validate.sh
./seed.sh
```

Run one or more reconcilers by name when diagnosing a service:

```bash
./seed.sh keycloak-samba forgejo nextcloud
```

The scripts use the parent template's exact compose invocation: the pinned
`component-lock.env`, `compose.foundation.yaml`, and `compose.enterprise.yaml`.
Environment variables set by the caller take precedence over `config.env`.

## Seeded state

| Seeder | Native interface | Ordinary state |
| --- | --- | --- |
| `keycloak-samba` | Keycloak `kcadm.sh` | `keplerops` realm, read-only Samba AD provider, group mapper, full user sync |
| `forgejo` | Forgejo admin CLI and REST API | administrator, five employees, `keplerops/orion-public`, public README |
| `redmine` | Rails runner | administrator, five employees, private Project Orion and memberships |
| `nextcloud` | `occ`, WebDAV, OCS Share API | five employees, `orion-internal`, shared Orion Review Room |
| `zammad` | Rails runner | administrator, five employees, Orion Support group and agent access |
| `stalwart` | Stalwart management REST API | `keplerops.lab` and `cinder.lab`, deterministic corporate and partner mailboxes |
| `odoo` | Odoo CLI and `odoo shell` | initialized `business` database, base company, administrator |
| `ghost` | Ghost Admin API with session authentication | owner setup, company title, published operational baseline |
| `mautic` | Mautic console | installed baseline, administrator, migrations, plugins, cleared cache |
| `business-workflows` | Product REST/XML-RPC/WebDAV/S3 APIs | bounded Unleash, Odoo, Ghost, Mautic, Zammad, Redmine, Nextcloud, RabbitMQ, Qdrant, and lakeFS clean records |

Create operations are guarded by native lookups. Mutable records are reconciled
where the product exposes a supported update path. Mautic's installer only runs
when `config/local.php` is absent. Stalwart principals are create-if-absent
because the management contract in the pinned 0.13.3 image does not provide a
stable declarative replacement operation for secrets.

## Runtime assumptions

1. Run on the Linux Docker host from a checkout containing the parent template.
   The host must have `bash`, Docker Compose v2, `curl`, `jq`, and `base64`.
2. Start the foundation and enterprise compose services first. Database entrypoint
   initialization in `db-init/` must have completed successfully.
3. Provision both Samba domain controllers and their baseline users/groups before
   running `keycloak-samba`. Keycloak must be able to reach
   both `ldaps://dc01.corp.keplerops.lab:636` and
   `ldaps://dc02.corp.keplerops.lab:636` from its identity network. The guest
   reconciliation step installs both Samba CA certificates into Keycloak's
   supported PEM truststore directory before enterprise startup.
4. The host must be able to route to the template's Docker bridge addresses used
   by the HTTP seeders. Override individual `*_URL` values when the host uses a
   different reachable address. The `Host` and `Origin` headers remain the
   product's configured enterprise names.
5. The component pins in `component-lock.env` are part of the API contract. In
   particular, the Stalwart script targets the legacy `/api/principal` management
   API exposed by the pinned 0.13.3 image. Revalidate the seeder before changing
   that image pin.
6. Keycloak LDAP mode is deliberately `READ_ONLY`: Samba owns employee identity
   lifecycle and passwords. The full sync is expected to fail loudly if Samba,
   its bind DN, or the network path is unavailable.
7. Forgejo's first run must occur before any unrelated process creates the
   `range-admin` account. The CLI creates that account as an administrator;
   subsequent runs rotate its synthetic password through the same CLI.
8. Ghost and Mautic installation is intended for a new clean data volume. Once
   installed, supported migration/content APIs are used on repeat runs; the
   scripts do not destroy or recreate product databases.
9. `business-workflows` is deliberately excluded from the default seeder list
   because it also requires the engineering/data Compose layer. Run it after
   MinIO, lakeFS, and Qdrant are ready; the gate-10 acceptance script does this
   automatically.

`validate.sh` is offline. It checks shell parsing, runs ShellCheck when present,
and validates the static Stalwart principal configuration. It does not prove
that containers, guest networks, LDAP, or product migrations are ready; those
checks happen during `seed.sh` and fail at the owning component.
