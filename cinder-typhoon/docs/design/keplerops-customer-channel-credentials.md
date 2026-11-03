# KeplerOps customer-channel credentials

This design replaces the broad customer-channel bearer with approval-issued,
operation-scoped credentials for K26. A participant must first publish and sign
the selected FieldKest connector release. The accepted release approval returns
the only participant-visible copies of the short-lived bearers.

The machine-readable contract is
[`keplerops-customer-channel-credentials.json`](keplerops-customer-channel-credentials.json).
Runtime and acceptance tests must agree with that contract.

## Trust boundaries and data flow

```text
participant                 KeplerOps trusted state                 Alterra
    |                                |                                  |
    | signed release approval        |                                  |
    +------------------------------->| k-registry                       |
    |                                | issue four scoped bearers         |
    |<-------------------------------+ store protected credential set    |
    |                                                                   |
    | one bearer + bound request     a-connector relay                  |
    +------------------------------->| verify range/tenant/channel/      |
    |                                | operation/version/expiry          |
    |                                +---- existing range-paired mTLS -->|
    |<------------------------------------------------ destination result|
```

The registry and relay share only the protected registry publication volume
and the existing per-range runtime credential mount. The relay derives the
expected range-binding digest locally; the raw per-range secret is never
written into the credential record or response. The relay's existing client
certificate and request signature remain the separate supplier identity seen
by Alterra.

## Credential set

A successful signed approval creates one
`fieldkest.customer-channel-credentials/v1` document. It records a random
credential-set ID, the per-range binding digest, tenant, channel, approved
version, issue and expiry times, and four independently random grants:

- `poll` can retrieve only the approved package candidate.
- `activate` can activate only that approved version.
- `receipt` can read only that version's activation receipt.
- `rollback` can rehearse only the retained `7.4.2` future-state slot.

The response returns the credential set through the earned approval workflow.
The release record and audit retain non-secret approval and credential metadata,
not bearer values.

## Failure and security behaviour

The relay validates the credential before contacting Alterra. It returns the
same authorization denial for a missing or malformed record, a foreign range,
an expired set, a wrong operation, or a wrong tenant/channel/version binding.
This avoids turning authorization failures into a credential oracle. Denied
requests cannot create a candidate, activation, receipt, rollback, or audit at
the destination.

The credential lifetime is one hour. A new signed approval replaces the prior
set, so an older set is no longer accepted even if its timestamp has not yet
expired. Range reset removes the publication volume and therefore removes every
issued customer-channel bearer.

Automated acceptance proves these bindings and the known K26 path. It does not
prove that a fresh participant will discover the workflow or that the route has
the intended difficulty; those remain blind-playtest requirements.
