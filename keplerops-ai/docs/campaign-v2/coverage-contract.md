# ATLAS Coverage Contract

## Source Of Truth

Coverage uses the official MITRE ATLAS collection version `2026.06`, modified
2026-05-27. The source contains:

- 16 tactics;
- 173 exact technique rows;
- 23 rows that have one or more subtechniques; and
- 150 leaf rows.

The design audit source is the official
[`mitre-atlas/atlas-data`](https://github.com/mitre-atlas/atlas-data)
distribution for that release. The audited YAML SHA-256 is
`b771de8b1489564b2838a709c7429849a9575dbd94073928817fe1a21661e70a`.
The build repository must retain a version-pinned copy or fetch-and-digest step
before the final coverage validator is implemented; a moving `main` download
is not an acceptable audit input.

The sole event exclusion is `AML.T0010.000 Hardware`. It is one of the 150 leaf
rows. The resulting event requirement is therefore:

- 16 of 16 tactics;
- 172 of 173 exact technique rows; and
- 149 of 150 leaf rows.

The design must preserve the source version and a digest of the source used for
the final audit. Technique names and relationships are never reconstructed from
memory.

## Exact Row Rule

Every one of the 172 required rows must be assigned explicitly to at least one
participant operation. Parent coverage is not inferred from a child row.

For example, an operation mapped to `AML.T0052.001 Deepfake-Assisted Phishing`
does not automatically satisfy `AML.T0052 Phishing`. The operation may claim
both only when the participant behavior materially satisfies both official
descriptions and the design records a rationale for each row.

Similarly, merely naming or observing a technique does not perform it. A
participant who finds a poisoned model has not necessarily performed `Publish
Poisoned Models`; a participant who downloads a supplied student has not
performed `Train Proxy via Replication`.

## Coverage Evidence Per Row

The operation map must record the following for every claimed row:

1. official row ID and name;
2. official tactic relationship or relationships;
3. the exact participant action that performs the behavior;
4. the AI component, artifact, or system involved;
5. the in-world consequence;
6. the server-observed facts that distinguish the action from a shortcut;
7. the reason this operation is an accurate rather than thematic mapping; and
8. negative cases that must not earn the row.

Rows may be covered by one compound operation when the real attack naturally
performs them together. The participant must still perform every material part.

## Exclusion

`AML.T0010.000 Hardware` is excluded because the event cannot credibly require
participants to compromise physical AI hardware while retaining the required
repeatability, safety, and remote participant access. Simulated firmware,
invented accelerator controls, labels, or a software-only stand-in do not count
as hardware supply-chain compromise and will not be used to claim the row.

Physical environment access (`AML.T0041`) remains required. It must be realized
through an authentic sensor or physical-environment interface that participants
can access remotely and affect through the normal system path; it cannot be
conflated with the excluded hardware supply-chain row.

## Audit Gates

### Design Audit

- Exactly 134 scored operations exist.
- Every operation belongs to the Cinder Typhoon campaign journey.
- Every operation has an explicit ATLAS rationale or is intentionally a
  prerequisite operation whose training value justifies a scored slot.
- All 172 required exact rows appear at least once.
- No excluded row is claimed.
- Duplicate mappings are justified by distinct tactic use or learning value.

### Implementation Audit

- Every mapped participant action is possible through the participant surface.
- Every mapped effect is produced by the declared real mechanism.
- Every server-observed predicate corresponds to participant-produced state.
- Representative shortcut and assertion-only paths fail.
- All required OSS components are installed, licensed, and available without a
  participant commercial account.

### Participant Audit

- A human can discover, execute, and observe each happy path.
- Progressive hints resolve ambiguity without exposing implementation details.
- The complete intrusion preserves prerequisites and artifacts across acts.
- The finale requires the actual outputs of the earlier campaign.
