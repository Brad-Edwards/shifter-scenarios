# Oracle receipt contract

The range-local proof service is the sole receipt issuer. Each flag placement
names one oracle evidence contract. After that evidence is current,
participant-attributed, bound to the flag's outcome, and clear of all blocking
negative gates, the service emits a compact `PENR1` receipt containing exactly:

`version`, `flag_id`, `outcome`, `evidence`, `range_instance`, `participant`,
`reset_generation`, `verdict`, `issued_at`, and `expires_at`.

The service signs the canonical compact JSON body with the event receipt key.
The CTFd plugin verifies that signature and compares every contract and
namespace field with the challenge and current account binding. It accepts only
`verdict: passed` during the signed validity interval. Reset rotates or replaces
the issuer key and advances the binding's `reset_generation`; either action
invalidates receipts from the previous participant start state.

The exact `flag_id`, outcome, evidence, participant, range instance, and reset
generation are all verified. The ten module-01 flags are therefore independently
receiptable: satisfying the broad `agent-control` outcome cannot release a
sibling flag without that sibling's item-specific evidence.

The signing key, account bindings, generated receipts, and raw proof are runtime
state. They must use protected files or structured service responses and must
never enter pack YAML, process arguments, logs, images, metadata, Terraform
outputs, or participant-visible content other than the gated receipt returned
to its bound participant.
