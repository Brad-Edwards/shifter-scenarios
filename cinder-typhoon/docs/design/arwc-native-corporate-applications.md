# ARWC corporate application migration

Issue #403 uses stock ERPNext, Nextcloud, PostgreSQL, Metabase and Gitea behind
the existing native IT edge. These products own their normal UI, API, users,
permissions, search, history and errors. Seed scripts use supported imports,
administration commands and APIs. They add no participant-facing application.

| Product | Hostname | Records and native interfaces |
| --- | --- | --- |
| ERPNext | `erp.arwc.test` | Company, departments, suppliers, items, assets, maintenance, purchasing and approvals through Frappe documents and workflows. |
| Nextcloud | `documents.arwc.test` | Existing business documents, drawings and their revisions through WebDAV and native sharing. |
| PostgreSQL | private IT network, 5432 | Planning, allocation, meter and reconciliation tables with separate writer and reader roles. Explicit grants expose only approved reporting views. |
| Metabase | `reports.arwc.test` | Saved questions and dashboards over the read-only planning role. Its own PostgreSQL application database stores users and report state. |
| Gitea | `engineering.arwc.test` | Engineering projects, configuration, native Git history and review records. |

All backends attach only to the internal IT network. Nginx serves each product
through an explicit TLS virtual host. These services gain no control-network
route and cannot write to the OT historian or controller.
Gitea uses native HTTPS Git, including clone, fetch and push. SSH is disabled
in this layout because the edge does not publish an SSH listener.

The company remains Alterra Regional Water Company, with Pine and River cost
centres. Existing named staff, supplier agreements, Cairn Reach assets, work
references, allocations and tariffs remain consistent across products. Native
ERPNext maintenance and purchasing documents replace the authored portal's
records; real transactions own state and permissions.

Existing authored material supplies ordinary surrounding records. The first
imports cover the business, maintenance, engineering and planning workflows.
Department and project groups provide ordinary access. Sensitive records use
native explicit sharing or product roles. The migration does not create an
arbitrary group for each reader-list combination. It does not add a mail server.

Every product uses its own persistent volumes and credentials. Supported seed
operations must be safe to repeat. Reset drops only native IT product state and
replays the same seed. History examples are created through native updates,
uploads or Git commits, rather than by altering product history tables.

The existing services remain until their replacements and affected card paths
are verified. Card rebinding and final retirement are tracked by issue #407;
the existing OT challenge conversions retain their difficulty and evidence.

References: [Gitea Docker](https://docs.gitea.com/installation/install-with-docker/),
[Metabase Docker](https://www.metabase.com/docs/latest/installation-and-operation/running-metabase-on-docker),
[Nextcloud installation](https://docs.nextcloud.com/server/stable/admin_manual/installation/command_line_installation.html),
and [Frappe REST API](https://docs.frappe.io/framework/user/en/api/rest).
