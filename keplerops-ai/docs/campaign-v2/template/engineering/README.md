# Engineering and data plane

This layer adds the clean campaign-v2 engineering and data products to the
foundation Compose project. It uses ordinary upstream product UIs and APIs. It
does not add exercise proofs, challenge endpoints, vulnerable workers, or
simulated product substitutes.

## Start and verify

Run from any directory on the Linux Docker host:

```bash
./engineering/engineering.sh start
./engineering/engineering.sh health
```

`start` is idempotent. It starts the required foundation services, reconciles
PostgreSQL roles/databases, pulls pinned vendor images, builds the small local
derivatives, starts the layer, and reconciles devpi, MinIO, lakeFS, Airflow, and
DVC state. Set `ENGINEERING_HEALTH_ATTEMPTS` or `ENGINEERING_HEALTH_DELAY` to
extend the default 7.5 minute health window on a cold host.

The Compose invocation used by the script is equivalent to:

```bash
docker compose \
  --env-file engineering/component-lock.additions.env \
  --env-file component-lock.env \
  -f compose.foundation.yaml \
  -f compose.engineering.yaml ...
```

Copy the variables in `component-lock.additions.env` into the parent
`component-lock.env` when this overlay is promoted into the assembled template.
The additions file remains usable until that integration happens; values in the
parent lock file take precedence.

## Product endpoints

| Product | Cell endpoint | Initial administrator or publisher |
|---|---|---|
| devpi | `http://10.61.40.30:3141` | `publisher` / `KeplerV2-Training-Devpi-Publisher` |
| Verdaccio | `http://10.61.40.31:4873` | Create users with the normal `npm adduser` flow |
| Harbor | `http://10.61.40.32:8080` | `admin` / `KeplerV2-Training-Harbor` |
| JupyterHub | `http://10.61.40.33:8000` | Keycloak groups `Engineering` or `AI-Research` |
| Label Studio | `http://10.61.40.34:8080` | `annotation.admin@keplerops.lab` / `KeplerV2-Training-LabelStudio` |
| Airflow | `http://10.61.40.35:8080` | `range-admin` / `KeplerV2-Training-Airflow` |
| MLflow | `http://10.61.40.36:5000` | Product API/UI; access control belongs at the parent ingress |
| Hayhooks | `http://10.61.40.37:1416/docs` | Product API documentation |
| MinIO API / console | `http://10.61.50.60:9000` / `:9001` | `kepler-minio` / `KeplerV2-Training-Minio-Object-Store` |
| lakeFS | `http://10.61.50.61:8000` | `KeplerLakeFSAccess` / `KeplerV2-Training-LakeFS-Object-Key` |
| Qdrant | `http://10.61.50.62:6333/dashboard` | Network-scoped product UI/API |
| Tika | `http://10.61.50.63:9998/tika` | Product API; the `full` image includes OCR dependencies |
| GROBID | `http://10.61.50.64:8070` | Product API/UI |

The Harbor deployment is the minimal official service split: portal, core,
jobservice, registry, registry controller, Harbor PostgreSQL, Harbor Redis, and
the Harbor Nginx edge. Registry content, metadata, cache, keys, and job logs use
separate named volumes. It deliberately omits optional Trivy, Notary, and chart
museum services.

MinIO initializes private `artifacts`, `datasets`, `labelstudio`, `lakefs`, and
`mlflow` buckets. lakeFS initializes the `orion` repository on
`s3://lakefs/orion`. MLflow proxies artifacts into `s3://mlflow`; Airflow uses
the shared campaign RabbitMQ vhost for Celery and the shared PostgreSQL service
for metadata. Harbor keeps its vendor-supported private PostgreSQL and Redis
instances isolated on `kep-v2-harbor`.

## DVC workspace

DVC is a tool profile, with persistent workspace state and a default lakeFS S3
remote. For example:

```bash
docker compose \
  --env-file engineering/component-lock.additions.env \
  --env-file component-lock.env \
  -f compose.foundation.yaml \
  -f compose.engineering.yaml \
  run --rm dvc dvc status
```

JupyterHub uses DockerSpawner and requires the host Docker socket. Notebook
containers join `kep-v2-data`, use per-user named volumes, and receive only the
clean object, lakeFS, MLflow, and Qdrant endpoints. The parent identity seed must
create the `keplerops` realm, the `jupyterhub` OIDC client, and the two allowed
groups before interactive notebook login.
