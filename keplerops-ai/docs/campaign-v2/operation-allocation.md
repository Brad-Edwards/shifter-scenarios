# Campaign Operation Allocation

## Purpose

This document allocates all 134 existing scoring identifiers to the replacement
campaign before detailed operation design. The identifiers are stable catalog
slots only. Their old module names, titles, order, mappings, and implementations
do not constrain the new operation assigned to them.

Participants see campaign acts and operation titles in Shifter. They do not need
to understand the `kep-mNN-x` identifier structure.

## Campaign Graph

The campaign has one mandatory outside-in spine and three internal branches:

```text
Act 1 Target KeplerOps
  -> Act 2 Build Cinder Typhoon Capabilities
  -> Act 3 Gain The First Foothold
  -> Act 4 Discover Orion From The Inside
       |-> Act 5 Compromise Agent Operations -----|
       |-> Act 6 Compromise Model Integrity ------|-> Act 8 Compromise The Orion Release
       |-> Act 7 Steal And Reproduce Orion -------|          -> Act 9 Operate Against Production
```

The branches can be investigated in parallel after internal discovery. The
complete happy path performs every operation. Release compromise requires
specific access and artifacts from all three branches, and the production
finale requires the exact candidate and stolen capability created earlier.

## Allocation Summary

| Act | Purpose | Slots |
|---|---|---:|
| 1 | Target KeplerOps | 4 |
| 2 | Build Cinder Typhoon Capabilities | 13 |
| 3 | Gain The First Foothold | 8 |
| 4 | Discover Orion From The Inside | 17 |
| 5 | Compromise Agent Operations | 22 |
| 6 | Compromise Model Integrity | 30 |
| 7 | Steal And Reproduce Orion | 16 |
| 8 | Compromise The Orion Release | 7 |
| 9 | Operate Against Production | 17 |
| | **Total** | **134** |

## Act 1: Target KeplerOps

Allocated slots:

- `kep-m06-g`
- `kep-m06-h`
- `kep-m06-i`
- `kep-m06-j`

These operations cover public research, vulnerability and repository research,
victim websites/domains and personnel, and active scanning. Each fact collected
must be reused by a later capability, foothold, or discovery operation.

## Act 2: Build Cinder Typhoon Capabilities

Allocated slots:

- `kep-m06-k`
- `kep-m06-l`
- `kep-m08-i`
- `kep-m06-m`
- `kep-m06-n`
- `kep-m06-o`
- `kep-m06-p`
- `kep-m06-q`
- `kep-m06-r`
- `kep-m06-s`
- `kep-m06-t`
- `kep-m06-u`
- `kep-m06-v`

These operations produce real attacker-owned accounts, infrastructure, tools,
models, datasets, prompts, retrieval content, adversarial inputs, deepfakes,
and executable artifacts. Exact bytes created here must be consumed later.

## Act 3: Gain The First Foothold

Allocated slots:

- `kep-m01-i`
- `kep-m01-j`
- `kep-m02-h`
- `kep-m02-i`
- `kep-m02-j`
- `kep-m02-k`
- `kep-m02-l`
- `kep-m02-m`

These operations implement real external delivery and initial-access paths:
malicious links and agent clickbait, public prompt infiltration, software/data/
model supply-chain entry, public application exploitation and drive-by effects,
participant-sent AI-assisted phishing with deepfake material, and sandbox-aware
delivery. At least one primary route earns the first scoped KeplerOps identity;
the other routes create access and artifacts used later rather than dead-end
flags.

## Act 4: Discover Orion From The Inside

Allocated slots:

- `kep-m03-g`
- `kep-m03-h`
- `kep-m03-i`
- `kep-m04-f`
- `kep-m04-g`
- `kep-m04-h`
- `kep-m04-i`
- `kep-m04-j`
- `kep-m04-k`
- `kep-m05-f`
- `kep-m05-g`
- `kep-m05-h`
- `kep-m05-i`
- `kep-m05-j`
- `kep-m05-k`
- `kep-m05-l`
- `kep-m08-k`

These operations discover RAG targets and stores, model family and behavior,
AI artifacts and processes, LLM and agent configuration, credentials and
authentication material, model-enabled products, and the sensor/physical
environment interface. They establish the real access required by the three
branches.

## Act 5: Compromise Agent Operations

Allocated slots:

- `kep-m01-a`
- `kep-m01-b`
- `kep-m01-c`
- `kep-m01-d`
- `kep-m01-e`
- `kep-m01-f`
- `kep-m01-g`
- `kep-m01-h`
- `kep-m03-d`
- `kep-m03-e`
- `kep-m03-j`
- `kep-m03-k`
- `kep-m05-a`
- `kep-m05-b`
- `kep-m05-c`
- `kep-m05-d`
- `kep-m05-e`
- `kep-m05-m`
- `kep-m05-n`
- `kep-m05-p`
- `kep-m05-q`

These operations progress from direct and indirect prompt compromise through
tool use, delegated authority, unsafe artifacts, retrieval and tool-data trust,
self-replication, delayed execution, memory/thread/configuration persistence,
rogue-agent deployment, command channels, exfiltration, and a release-relevant
agent effect.

## Act 6: Compromise Model Integrity

Allocated slots:

- `kep-m02-a`
- `kep-m02-b`
- `kep-m02-c`
- `kep-m02-d`
- `kep-m03-b`
- `kep-m03-a`
- `kep-m03-c`
- `kep-m03-f`
- `kep-m06-a`
- `kep-m06-b`
- `kep-m05-o`
- `kep-m06-c`
- `kep-m06-d`
- `kep-m06-e`
- `kep-m06-f`
- `kep-m07-a`
- `kep-m07-b`
- `kep-m07-c`
- `kep-m07-d`
- `kep-m07-e`
- `kep-m07-f`
- `kep-m07-g`
- `kep-m07-h`
- `kep-m07-i`
- `kep-m02-e`
- `kep-m02-f`
- `kep-m09-h`
- `kep-m09-i`
- `kep-m09-j`
- `kep-m09-k`
- `kep-m09-l`

These operations cover evasion, adversarial-data creation and verification,
RAG and trusted-output manipulation, training/data/model poisoning, model
architecture and embedded-code manipulation, malicious publication, registry
reputation, rug pulls, agent-tool supply chain, and model corruption. Every
operation must produce or modify real artifacts through normal OSS systems.

## Act 7: Steal And Reproduce Orion

Allocated slots:

- `kep-m04-a`
- `kep-m04-b`
- `kep-m04-c`
- `kep-m04-d`
- `kep-m04-e`
- `kep-m04-l`
- `kep-m04-m`
- `kep-m08-a`
- `kep-m08-b`
- `kep-m08-c`
- `kep-m08-d`
- `kep-m08-e`
- `kep-m08-f`
- `kep-m08-g`
- `kep-m08-h`
- `kep-m08-j`

These operations cover prompt and data leakage, membership inference, response
rendering and service-data exfiltration, teacher-query collection, genuine
teacher/student distillation, hidden fidelity testing, proxy creation from
gathered artifacts, inversion, full model access, and collection of exact
protected Orion artifacts.

## Act 8: Compromise The Orion Release

Allocated slots:

- `kep-m09-b`
- `kep-m09-a`
- `kep-m09-c`
- `kep-m09-d`
- `kep-m09-e`
- `kep-m09-f`
- `kep-m09-g`

These operations join the exact participant-created candidate, evaluation
state, lineage, model card, approval, signature, policy, registry alias, and
deployment decision. The final operation promotes the exact compromised bytes,
not a supplied stand-in.

## Act 9: Operate Against Production

Allocated slots:

- `kep-m10-a`
- `kep-m10-b`
- `kep-m10-c`
- `kep-m10-d`
- `kep-m10-e`
- `kep-m10-f`
- `kep-m10-g`
- `kep-m10-h`
- `kep-m10-i`
- `kep-m10-j`
- `kep-m10-k`
- `kep-m10-l`
- `kep-m10-m`
- `kep-m10-n`
- `kep-m10-o`
- `kep-m10-p`
- `kep-m10-q`

These operations verify the production revision, activate fresh compromised
behavior, demonstrate safe machine compromise, steal the original Orion
artifact, exfiltrate exact bytes, exercise denial/cost/chaff paths, demonstrate
reversible external harms, and cause real dataset and agent-tool-mediated data
destruction in contained targets. The finale requires both reproduced and
stolen Orion capability plus the production effect.

## Detailed Design Gate

An allocated slot is not approved merely because it appears above. Its detailed
record must satisfy the participant operation contract, independently validate
every ATLAS mapping, identify its flag placement, and name the real OSS
mechanism. Invalid old mappings may move between slots as the detailed review
reconciles the complete 172-row coverage set.
