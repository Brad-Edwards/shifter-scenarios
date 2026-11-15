# FieldLink platform access

Use the normal application or protocol for each service. Your workstation has
native Kubernetes, PostgreSQL and S3 clients, with personal configuration in
your home directory.

| Service | Address | Access |
| --- | --- | --- |
| Kubernetes | `https://cloud-api.keplerops.test:6443` | `kubectl`; the current context selects the FieldLink namespace. |
| PostgreSQL | `data.keplerops.test:5432` | `psql service=fieldlink`; company records are read-only and your workspace schema is writable. |
| Object storage | `https://objects.keplerops.test` | `aws --endpoint-url https://objects.keplerops.test s3 ls s3://fieldlink-exports`; the normal AWS profile supplies your scoped credentials and certificate trust. |
| Assistant | `https://assistant.keplerops.test` | Your ordinary staff account; FieldLink Operations contains company documents and shared work. |
| Model server | `https://llm.keplerops.test` | Native Ollama API, using the local FieldLink Qwen model. |

Kubernetes access applies to the FieldLink namespace. It does not grant cluster
administration or permission to run workloads with host privileges. Standard
Kubernetes API errors and job logs show the result of ordinary operations.
The approved `rancher/k3s:v1.37.2-k3s1` client image is available on the node
for ordinary jobs without an external image pull.

The assistant uses the local model and local document retrieval. Its FieldLink
support tool reads current report metadata or the state of an existing job. It
does not create or deliver customer work, and it does not manage help-desk
accounts or sessions.
