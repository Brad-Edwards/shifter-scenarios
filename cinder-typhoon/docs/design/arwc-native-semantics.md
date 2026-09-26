# ARWC native RAE semantics

This note freezes the SDL vocabulary for the Alterra Regional Water Company
tranche. It records how the design is represented in the pinned RAE 5.0.0
model; it does not introduce a project dialect or a realization plugin.

## Conclusion

No upstream RAE expressivity gap is required by the ARWC design. The scenario
can describe the complete hand-build contract with native nodes, runtime
inventories, applications and routes, identity and authorization records,
content, relationships, action contracts, evidence, propositions, assertions,
objectives, workflows, events, and injects.

RAE's legacy `vulnerabilities` compatibility syntax is not used. A weakness is
instead the ordinary software, configuration, permission, record, binary, or
protocol state that makes the authored behavior occur. Private relationship
properties are not used as an alternate type system.

## Representation rules

| Required fact | Native representation |
| --- | --- |
| System and network presence | Node infrastructure plus `runtime.network.endpoints` |
| Listening process | Node service plus `runtime.service_listeners` |
| HTTP or protocol interaction | `runtime.applications` and typed routes, parameters, authentication, sessions, responses, and disclosures |
| Files, images, programs, records, and service-loader contracts | `content` at an inventoried filesystem path, with runtime software and storage declarations where applicable |
| Local execution identity | `runtime.local_identity`, processes, service-manager state, and software components |
| Application permissions and tenancy | `runtime.app_authorizations` principals, roles, grants, mappings, and tenants |
| Directory, certificate, delegated, or service identity | `runtime.identity_authorities` services, subjects, policies, and identity relationships |
| Databases and durable service state | Native database or datastore services, access relationships, volumes, and filesystem inventory |
| Scheduled or isolated execution | Native scheduled jobs, orchestration authorities, spawn templates, children, and lifecycle policy |
| Ordinary business connectivity | Unadorned `connects_to` relationships, or a more specific native proxy, data, identity, or service relationship when it really applies |
| Prerequisite logic and action applicability | Workflows and action-contract preconditions |
| Exact action and state transition | Action-contract procedure, arguments, effects, failures, interactions, and temporal terms, backed by exact owned service content |
| Completion | Independently owned evidence, an observed-state proposition, assertion, and objective |
| Story consequence after an observed result | Native event and inject declarations; they present or retain the already caused effect and never manufacture its proof |

## Modular boundary

- The five ARWC world modules own systems and native runtime state:
  `a-corporate`, `a-maintenance`, `a-dmz`, `a-engineering`, and `a-control`.
- One content module per owning system holds its deterministic private
  service-loader contracts. Those contracts are data consumed by the hand
  build, not executable SDL semantics.
- Operation modules own only their W-card workflows, action contracts,
  evidence, and objective logic. They refer to native systems and exact
  content; they do not allocate work through `challenge_surface` edges.
- `arwc-integrations.yaml` contains only ordinary relationships useful to a
  reader of the composed architecture. Identity, authorization, route, and
  data rules remain with their owning systems rather than being encoded on
  those edges.
- The process-model contract is authoritative for quantities, units, and
  state separation. Cards may refer to it but may not copy or silently vary
  its values.

## Forbidden residual semantics

ARWC modules must not require a consumer to interpret `cinder_kind`,
`flow_kind`, `context_kind`, `modes`, `guard`, or another private relationship
property. The old `flows-a-*` modules, ARWC entries in the shared contexts and
relays modules, generated `challenge_surface` relationships, and generic
`starting-records` content are removed when the native modules are generated.

An open RAE value such as `other` remains valid only inside the native field
that owns that vocabulary. It may not be paired with hidden project logic.

## Content and evidence boundary

The private service-loader contract for a card freezes exact initial records,
surface bindings, defect or constrained algorithm, accepted and denied
requests, resulting mutation or disclosure, persistence, and evidence. It
does not seed the successful result. Stable artifacts have a canonical
generation-input digest; runtime records name their owner, mode, durability,
and sensitivity without pretending to have a pre-build binary digest.

An objective observes evidence written by the responsible service after the
action. Objective evaluation cannot issue a session, mutate a business record,
move a simulated actuator, or make a downstream system accept a result.

## Recovery and adjudication

Normal participant-created state persists across retries and day-two resume.
Infrastructure recovery and result submission are external operations and are
not scenario mechanics. The private W33 and W34 rehearsal checkpoints are
ordinary in-world services because their isolation is part of those exercises;
they do not reset W30 or any previously earned state.

## Gap rule

If hand-building later reveals a required fact that cannot be expressed by
the surfaces above, authoring stops and the gap is raised upstream. A custom
semantic decoder is not an acceptable workaround. No such gap is known at the
hand-build-readiness boundary.
