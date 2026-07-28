# KeplerOps isolation and edge software boundaries

This package contains infrastructure capabilities only. It does not contain
challenge actions, success logic, flags, receipts, scoring, or ATLAS promotion.
The ACES SDL remains the only deployment and routing authority.

## Process families

- `policy-lab` is a dedicated Open Policy Agent 1.3.0-static service. It is
  pinned to `sha256:44f0f4b1c09260eaf5e24fc3931fe10f80cffd13054ef3ef62cef775d5cbd272`
  and intentionally preserves the standalone Data API path-injection condition
  described by CVE-2025-46569 / GHSA-6m8w-jc87-6cr7. The official advisory says
  the issue is fixed in OPA 1.4.0. This lab must have its own network and must
  never serve, proxy, or participate in KeplerOps range authorization, which
  remains on the separately pinned OPA 1.7.1 service.
- `loader-control` accepts bounded Python pickle artifacts and loads them only
  in disposable, network-disabled containers on a daemon-labelled dedicated
  worker engine. Python pickle is a real unsafe serialization format; loading
  can execute artifact-supplied code. The controller refuses general Docker
  sockets and engines without `keplerops.engine.role=bounded-workers`.
- `edge-registry` records procurement, inventory reports, claimed capabilities,
  and supplied attestation content. It deliberately reports all enrolled
  hardware as unverified until real vendor or TPM attestation integration and
  the physical appliance are present. It never manufactures an accelerator,
  device identity, verified capability, or physical-presence claim.
- `k6` is a Grafana k6 2.0.0 runner pinned to
  `sha256:a33a0cfdc4d2483d6b7a3a22e726a499ff2831a671a49239104cd34a9937523c`.
  It permits only query-free loopback or `*.keplerops.lab` targets and caps the
  client cohort at 5 iterations/second, 60 seconds, and 10 virtual users.

The dedicated worker engine uses the official rootless Docker 29.6.1 image
pinned to
`sha256:371962f4344295a1eb185f1c9e62064bf4503a7beb8c6e73be3405500041784b`.
Its Dockerfile is in `worker-engine/`. Bootstrap must give it the rootless DIND
runtime requirements documented by Docker (including the privileged outer
container required for rootless DIND), a tmpfs or named volume at
`/run/user/1000`, and no host Docker socket. The daemon advertises
`keplerops.engine.role=bounded-workers` and listens only on
`/run/user/1000/docker.sock`; it exposes no TCP API.

The same dedicated engine can serve the platform-agent bounded workers without
weakening the unsafe loader boundary. Mount the engine's `/run/user/1000`
socket volume read/write at `/run/keplerops-worker` in platform-agent and at
`/run/keplerops-isolation-engine` in loader-control. Each controller sees its
declared socket path, while neither disposable workload receives the socket.
Both controllers currently use the same exact worker image digest,
`python@sha256:5f55cdf0c5d9dc1a415637a5ccc4a9e18663ad203673173b8cda8f8dcacef689`;
the engine must preload it so workers do not need network access. It must not
host general range services or receive the host engine socket.

## External hardware constraint

The software boundary is ready without claiming hardware availability. The
physical accelerator path remains unsatisfied until two real range-owned edge
accelerator appliances are procured, connected, inventoried, and verified by
their actual vendor or TPM attestation mechanism. A software record, uploaded
attestation-shaped JSON, VM device, or configuration toggle cannot satisfy that
constraint.

OPA is Apache-2.0, Docker SDK/Engine are Apache-2.0, Grafana k6 is AGPL-3.0,
FastAPI is MIT, Uvicorn is BSD-3-Clause, and Python is PSF-2.0.
