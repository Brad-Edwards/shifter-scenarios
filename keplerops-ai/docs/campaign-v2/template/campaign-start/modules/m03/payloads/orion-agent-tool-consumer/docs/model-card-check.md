# Model-card compatibility workflow

The WorkHub release assistant first retrieves this procedure through its
allow-listed read-only MCP tool. The Airflow compatibility workflow binds that
request and trace to a server-side dispatch of `model-card-check.yml`. The
Forgejo workflow performs a clean install from `package-lock.json`, starts the installed package's stdio MCP
server, invokes `inspect_model_card`, and retains the agent trace, package
integrity, MCP request ID, and public result as a Forgejo Actions artifact.

The private model-card record is supplied from the release workflow's protected
configuration. Only the public license and schema fields belong in the normal
result. The runner permits the tool's declared Cinder audit callback so release
engineering can diagnose third-party integrations.
