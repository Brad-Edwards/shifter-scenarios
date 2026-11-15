# FieldLink native identity and workplace

Issue 400 moves identity, certificate enrollment, staff work and customer support
into native products. Issue 399 remains open for its remaining card and reset
qualification; that work does not block this product setup.

## First slice

Reuse the qualified ARWC Keycloak 26.4.7 and step-ca 0.28.4 image pins and their
normal import, PostgreSQL, HTTPS and certificate patterns. Reuse FieldLink's
existing PostgreSQL service with separate least-privilege application databases
and users. The existing Nginx edge supplies fixed native vhosts; it does not
translate identities, tokens, sessions or product API responses.

| Product | Native owner | Persistent state |
| --- | --- | --- |
| Keycloak | Staff identities, realm clients, roles, groups, tokens and events | Its own PostgreSQL database; supported initial realm import. |
| MIT Kerberos | The existing KEPLEROPS.TEST realm, principals and real tickets | Existing KDC database and keytabs; preserve keys and principal history. |
| step-ca | Enrollment, provisioners, policy, signed certificates and native errors | Its own native CA configuration, signing keys and database. |
| Kanboard | Staff projects, tasks, reviews, notes, assignments, files and activity | Its own PostgreSQL database plus native uploaded files. |
| osTicket | Customer cases, users, threads, attachments and assignment history | MariaDB plus the application's native attachment state. |

Keycloak and step-ca backends use the existing private foundation data network.
Identity HTTPS names resolve to the native edge, while an explicit Kerberos
name resolves to the retained KDC. Update authoritative DNS and desktop static
hosts together, so the browser cannot silently reach the retired Python IdP.
The CA vhost uses a certificate issued by the actual enrollment CA; its public
root is supplied through ordinary workstation trust. Existing product keys and
trust remain stable unless a separately coordinated migration requires changes.

The first participant checkpoint checks native Keycloak login, account/realm
metadata, native tokens and role boundaries, the actual Kerberos service, and
real step-ca enrollment with a normal client. Then expose native Kanboard and
osTicket and migrate useful workplace records through supported product setup
and administration mechanisms. Reuse existing workforce, case and attachment
assets; retire replaced Python surfaces and their obsolete files.

## Boundaries and qualification

Keep only the genuine FieldLink diagnostic and customer delivery integrations.
Do not add a session exchanger or an API that impersonates any native product.
Use native account and authorization boundaries; inherited source or publishing
rights do not automatically grant identity, CA or help-desk administration.

Each product keeps ordinary UI, API, protocol, data, history and error behavior.
QA operates through the participant affordances and receives directions to the
reviewed native paths. Source/build preparation can continue during another
slice's QA window; coordinate identity, DNS, desktop, CA and shared edge changes
before applying them. Build on the isolated FieldLink development VM only.

Affected card mappings and difficulty research must precede changes to those
cards. Native product visibility alone does not establish full card acceptance.
Restart persistence and a final pristine reset must reproduce the migrated
native state before issue 400 closes.

## Manual identity deployment

Use the development-range wrapper to synchronize committed source and build on
`cinder-fieldlink-dev`. Do not use this procedure against the golden range.
Coordinate the DNS, desktop and shared edge window before applying it.

1. Run `generate-operator-material.sh` from the FieldLink build directory. It
   preserves the private bootstrap account inputs and existing CA keys, prepares
   the native realm import and creates missing native enrollment CA material.
2. Build `fieldlink-dns`, `k-identity` and `k-dev` with the existing Compose file.
   Pull the pinned Keycloak and step-ca images. Run
   `native-workplace/bootstrap-databases.sh` to initialize the existing PostgreSQL
   volume's separate native application databases. Fresh PostgreSQL volumes use
   the same supported initialization SQL automatically.
3. Start the native identity services and recreate DNS and the existing edge.
   Recreate the desktop only in its agreed window and reapply its private
   development login with `manage.sh desktop-login fieldlink prod-mgau4w`.
4. Supply the native enrollment CA's public root through ordinary desktop trust.
   Ask QA to check actual native account login, protocol behavior, enrollment and
   retained state. Product health alone does not establish participant acceptance.

Nginx receives only its leaf certificate/key and the explicitly required public
roots. It receives neither CA's signing keys, password, private configuration or
database. Development peer overrides remain in the existing private `.env`;
loading an alternate Compose environment must not discard that mapping.

References: [Keycloak administration](https://www.keycloak.org/docs/latest/server_admin/),
[Keycloak hostname and proxy settings](https://www.keycloak.org/server/reverseproxy),
[step-ca configuration](https://smallstep.com/docs/step-ca/configuration/),
[Kanboard PostgreSQL](https://docs.kanboard.org/v1/admin/postgresql/), and
[osTicket installation](https://docs.osticket.com/en/latest/Getting%20Started/Installation.html).
