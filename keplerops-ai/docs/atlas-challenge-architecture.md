# KeplerOps Full-ATLAS Challenge Architecture

Operator and implementer view for ATLAS expansion design. The machine authority is
`content.core.atlas-challenge-design` and
`content.core.atlas-technique-catalog` in the canonical modular ACES SDL. This
document renders that design for review; implementation slices must update the
SDL first and reconcile this rendering in the same slice.

## Portfolio Decision

KeplerOps now has 134 realized challenge contracts and one design awaiting
realization, for a complete library of 135 challenges. The participant proof campaigns
participant-prove all 134 playable contracts through the retained GCP range and
Kasm participant surface. The original expansion architecture remains 75
contracts: 74 are participant-proven, and `kep-m02-g` remains planned while the
physical accelerator attestation contract is under consideration.
The design covers all 173 exact
MITRE ATLAS 2026.06 technique rows and all 150 leaves. It does not turn the
framework into 173 flags:

- 34 exact rows are proven by the original 60 challenges;
- 129 additional exact rows are participant-proven by the 74 realized expansion
  challenges;
- nine remaining parent rows are assigned to existing receipts whose current
  participant actions already prove the parent semantics; and
- one exact leaf row, `AML.T0010.000` Hardware, remains planned behind
  `kep-m02-g`.

The average new challenge covers 1.73 previously missing rows. A challenge
normally covers at most three rows when one participant action and one proof
obligation genuinely prove them together. The only four-row exception is
`kep-m06-g`: one search-and-reproduction workflow covers the Search Open
Technical Databases parent and its journal, preprint, and blog source variants.

The complete library contains 3,045 incremental target minutes and 16,750
points. It is not an expected full clear. Event-bundle selection selects dependency-closed
eight-hour bundles from this library for novice, intermediate, advanced,
mixed, and agent-heavy cohorts. Challenge selection and research-capture mode
remain independent, so the event can downselect content without redesigning
coverage or losing the option for full-content capture.

The exact seed or exclusion lists are SDL-owned. Event-bundle selection projects these
five designs into selectable CTFd and event manifests and validates dependency
closure:

| Bundle | Audience | Challenges after closure | Manual-equivalent stock | A / I / Adv / Exp |
|---|---|---:|---:|---|
| `novice-manual` | Novice manual participants | 48 | 678 min | 26 / 22 / 0 / 0 |
| `intermediate-manual` | Intermediate manual participants | 63 | 1,072 min | 26 / 28 / 9 / 0 |
| `advanced-manual` | Advanced manual participants | 50 | 1,206 min | 14 / 18 / 13 / 5 |
| `mixed-cohort` | Shared manual and assisted event | 66 | 1,321 min | 18 / 34 / 12 / 2 |
| `agent-heavy` | Participant-owned offensive agents | 130 | 2,964 min | 34 / 57 / 28 / 11 |

Stock intentionally exceeds 420 active minutes. Participants solve subsets;
the excess absorbs route choice, retries, skill variance, and agent throughput.
The agent-heavy board exposes almost the entire library because participant
agents can operate in parallel, while every included challenge remains
manually solvable.

## Difficulty and Module Shape

| Scope | Accessible | Intermediate | Advanced | Expert | Total | Target minutes |
|---|---:|---:|---:|---:|---:|---:|
| Realized board | 37 | 58 | 28 | 11 | 134 | 3,015 |
| Remaining planned expansion | 0 | 0 | 1 | 0 | 1 | 30 |
| Complete library | 37 | 58 | 29 | 11 | 135 | 3,045 |

Accessible and intermediate work is 70.4% of the complete library. The
expansion preserves immediate AI-security entry points while adding longer
credential, supply-chain, training, extraction, agent, and deployed-impact
paths. Participants can work manually; no challenge requires an assistant or
agent. Participant-owned offensive agents are also first-class, so proof binds
fresh actions to participant, range, challenge, and reset generation rather
than depending on human pacing.

| Module | Realized | Planned | Complete | Planned minutes | Implementation |
|---|---:|---:|---:|---:|---:|
| 01 Agent control | 10 | 0 | 10 | 0 | Module 01 expansion |
| 02 Model evasion and delivery | 12 | 1 | 13 | 30 | Module 02 expansion |
| 03 Retrieval and context | 11 | 0 | 11 | 0 | Module 03 expansion |
| 04 Discovery and model secrets | 13 | 0 | 13 | 0 | Module 04 expansion |
| 05 Agent state, identity, and C2 | 17 | 0 | 17 | 0 | Module 05 expansion |
| 06 Reconnaissance and adversarial workbench | 22 | 0 | 22 | 0 | Module 06 expansion |
| 07 Training and datasets | 9 | 0 | 9 | 0 | Module 07 expansion |
| 08 Model access and extraction | 11 | 0 | 11 | 0 | Module 08 expansion |
| 09 AI supply chain | 12 | 0 | 12 | 0 | Module 09 expansion |
| 10 Deployed impact | 17 | 0 | 17 | 0 | Module 10 expansion |

## Implementation Contract

Each row below has a complete participant action, proof obligation, dependency
list, participant-visible surfaces, required real-software realization, scoring
tier, and timing band in ACES SDL. The implementation slice must realize that
contract rather than redesign it locally. New nodes and software are expected
where the contract requires them. Reuse is preferred when the existing real
service meets the semantics; a stub, fake twin, management-plane action, or
pack-local projection cannot substitute.

Before playtest, acceptance is deliberately focused:

1. one participant-equivalent success for each new challenge;
2. one representative shortcut rejection for each proof class;
3. one scoped reset and replay for the changed module;
4. focused contract, telemetry, and module tests; and
5. CI and Sonar.

Repeated stochastic campaigns run only when an observed defect justifies a
targeted repetition. Playtest and hardening can proceed concurrently.

Operational digest-safe telemetry remains always on. The selectable research
profile from research telemetry is designed to capture prompts, completions, tool messages, terminal and
process activity, scenario HTTP bodies, browser interaction, notebooks,
artifacts, workflow state, receipts, resets, and CTFd events into encrypted
operator-only storage. Every implementation must emit participant, range,
challenge, reset-generation, source, and timestamp joins needed to reconstruct
manual and participant-agent runs. Full KasmVNC frame/pointer replay is not
required for the current event profile; pixel-level UI reconstruction is an
explicit limit documented in `telemetry/data-dictionary.md` and would require a
separate SDL-authored, encrypted, fail-open capture path if later needed.

## Expansion Architecture Inventory

All realized rows in the expansion inventory are now `participant-proven`.
The remaining Module 02 g hardware row remains planned/under consideration.
The table is retained as the stable cross-module design handoff.

### Module 01

| ID | Challenge | Tier | Target | ATLAS rows |
|---|---|---|---:|---|
| `kep-m01-g` | Triggered Artifact | Intermediate | 16 min | `AML.T0011`, `AML.T0011.000`, `AML.T0051.002` |
| `kep-m01-h` | Malicious Package Runner | Intermediate | 18 min | `AML.T0011.001`, `AML.T0050` |
| `kep-m01-i` | Agent Click Trap | Accessible | 10 min | `AML.T0011.003`, `AML.T0100` |
| `kep-m01-j` | Public Prompt Seed | Accessible | 10 min | `AML.T0093` |

### Module 02

| ID | Challenge | Tier | Target | ATLAS rows |
|---|---|---|---:|---|
| `kep-m02-g` | Accelerator Trust Break | Advanced | 30 min | `AML.T0010.000` |
| `kep-m02-h` | Masquerading AI Runtime | Intermediate | 20 min | `AML.T0010.001`, `AML.T0074` |
| `kep-m02-i` | Poisoned Data Dependency | Accessible | 12 min | `AML.T0010.002` |
| `kep-m02-j` | Poisoned Model Dependency | Accessible | 12 min | `AML.T0010.003` |
| `kep-m02-k` | Web Exploit Delivery | Intermediate | 20 min | `AML.T0049`, `AML.T0078` |
| `kep-m02-l` | Synthetic Spearphish | Accessible | 12 min | `AML.T0052`, `AML.T0052.000`, `AML.T0052.001` |
| `kep-m02-m` | Sandbox-Aware Payload | Intermediate | 28 min | `AML.T0097` |

### Module 03

| ID | Challenge | Tier | Target | ATLAS rows |
|---|---|---|---:|---|
| `kep-m03-g` | RAG Target Census | Accessible | 10 min | `AML.T0064`, `AML.T0036` |
| `kep-m03-h` | Local Vector Collection | Intermediate | 18 min | `AML.T0037`, `AML.T0085.000` |
| `kep-m03-i` | Indexed Credential Harvest | Accessible | 16 min | `AML.T0082` |
| `kep-m03-j` | Self-Replicating Prompt | Advanced | 28 min | `AML.T0061` |
| `kep-m03-k` | Delayed Conversation Trigger | Intermediate | 18 min | `AML.T0092`, `AML.T0094` |

### Module 04

| ID | Challenge | Tier | Target | ATLAS rows |
|---|---|---|---:|---|
| `kep-m04-f` | Model Fingerprint | Intermediate | 18 min | `AML.T0013`, `AML.T0014`, `AML.T0063` |
| `kep-m04-g` | Runtime Artifact Census | Accessible | 12 min | `AML.T0007`, `AML.T0075`, `AML.T0089` |
| `kep-m04-h` | Hallucination Cartography | Accessible | 10 min | `AML.T0062` |
| `kep-m04-i` | System Delimiter Probe | Intermediate | 18 min | `AML.T0069.000`, `AML.T0069.001` |
| `kep-m04-j` | Agent Knowledge Map | Accessible | 16 min | `AML.T0084.000`, `AML.T0084.001` |
| `kep-m04-k` | Dormant Wires | Advanced | 28 min | `AML.T0084.002`, `AML.T0084.003` |
| `kep-m04-l` | Rendered Exfil | Intermediate | 18 min | `AML.T0077` |
| `kep-m04-m` | Service Data Export | Intermediate | 20 min | `AML.T0085` |

### Module 05

| ID | Challenge | Tier | Target | ATLAS rows |
|---|---|---|---:|---|
| `kep-m05-f` | Public Agent Blueprint | Accessible | 10 min | `AML.T0002.002` |
| `kep-m05-g` | Configuration Credential Discovery | Intermediate | 18 min | `AML.T0084`, `AML.T0083` |
| `kep-m05-h` | Valid Token Reuse | Intermediate | 18 min | `AML.T0012`, `AML.T0091`, `AML.T0091.000` |
| `kep-m05-i` | Session Cookie Theft | Intermediate | 16 min | `AML.T0091.001`, `AML.T0113` |
| `kep-m05-j` | Unsecured Credential Pickup | Accessible | 10 min | `AML.T0055` |
| `kep-m05-k` | Agent Tool Credential Harvest | Accessible | 18 min | `AML.T0085.001`, `AML.T0098` |
| `kep-m05-l` | Host Credential Exploit | Intermediate | 30 min | `AML.T0106`, `AML.T0090` |
| `kep-m05-m` | Persistent Agent Reconfiguration | Intermediate | 20 min | `AML.T0081` |
| `kep-m05-n` | Deploy Local Rogue Agent | Advanced | 35 min | `AML.T0103`, `AML.T0112.000` |
| `kep-m05-o` | Agent Reverse Channel | Advanced | 35 min | `AML.T0072`, `AML.T0108` |
| `kep-m05-p` | Service API Covert Channel | Intermediate | 20 min | `AML.T0096` |
| `kep-m05-q` | Web Assistant Relay | Advanced | 35 min | `AML.T0114` |

### Module 06

| ID | Challenge | Tier | Target | ATLAS rows |
|---|---|---|---:|---|
| `kep-m06-g` | Open Literature Triangulation | Accessible | 12 min | `AML.T0000`, `AML.T0000.000`, `AML.T0000.001`, `AML.T0000.002` |
| `kep-m06-h` | Open Vulnerability Research | Accessible | 12 min | `AML.T0001`, `AML.T0004`, `AML.T0095.000` |
| `kep-m06-i` | Victim Web Recon | Accessible | 12 min | `AML.T0003`, `AML.T0095`, `AML.T0087` |
| `kep-m06-j` | Active AI Surface Scan | Accessible | 10 min | `AML.T0006` |
| `kep-m06-k` | Public Artifact Kit | Accessible | 12 min | `AML.T0002`, `AML.T0002.000`, `AML.T0005.002` |
| `kep-m06-l` | Cloud Attack Workbench | Intermediate | 20 min | `AML.T0008`, `AML.T0008.000`, `AML.T0008.004` |
| `kep-m06-m` | Edge Acquisition | Advanced | 35 min | `AML.T0008.001`, `AML.T0008.003` |
| `kep-m06-n` | Domain and Proxy Front | Intermediate | 22 min | `AML.T0008.002`, `AML.T0008.005`, `AML.T0021` |
| `kep-m06-o` | Capability Procurement | Intermediate | 20 min | `AML.T0016`, `AML.T0016.000`, `AML.T0016.001` |
| `kep-m06-p` | Generative Capability Procurement | Accessible | 12 min | `AML.T0016.002` |
| `kep-m06-q` | Custom Attack Builder | Intermediate | 24 min | `AML.T0017`, `AML.T0079` |
| `kep-m06-r` | White-Box Optimizer | Advanced | 35 min | `AML.T0043.000` |
| `kep-m06-s` | Retrieval Trust Forge | Intermediate | 22 min | `AML.T0066`, `AML.T0067`, `AML.T0067.000` |
| `kep-m06-t` | Synthetic Impersonation | Intermediate | 20 min | `AML.T0073`, `AML.T0088` |
| `kep-m06-u` | Generated Host Escape | Expert | 50 min | `AML.T0102`, `AML.T0105` |
| `kep-m06-v` | Security Control Exploit | Intermediate | 35 min | `AML.T0107` |

### Module 07

| ID | Challenge | Tier | Target | ATLAS rows |
|---|---|---|---:|---|
| `kep-m07-g` | Architecture Sabotage | Advanced | 40 min | `AML.T0018`, `AML.T0018.001` |
| `kep-m07-h` | Poisoned Dataset Publication | Intermediate | 24 min | `AML.T0019` |
| `kep-m07-i` | Executable Model Artifact | Expert | 50 min | `AML.T0018.002` |

### Module 08

| ID | Challenge | Tier | Target | ATLAS rows |
|---|---|---|---:|---|
| `kep-m08-g` | Gathered Artifact Proxy | Advanced | 40 min | `AML.T0005.000`, `AML.T0035` |
| `kep-m08-h` | Model Inversion | Advanced | 40 min | `AML.T0024.001` |
| `kep-m08-i` | Physical Sensor Evasion | Intermediate | 20 min | `AML.T0041` |
| `kep-m08-j` | Full Model Access | Expert | 55 min | `AML.T0044` |
| `kep-m08-k` | Product Side Channel | Intermediate | 22 min | `AML.T0047` |

### Module 09

| ID | Challenge | Tier | Target | ATLAS rows |
|---|---|---|---:|---|
| `kep-m09-h` | Registry Reputation Seed | Intermediate | 22 min | `AML.T0010.004`, `AML.T0111` |
| `kep-m09-i` | Poisoned Model Publication | Intermediate | 35 min | `AML.T0058` |
| `kep-m09-j` | Model Rug Pull | Advanced | 40 min | `AML.T0109` |
| `kep-m09-k` | Poisoned Tool Publication | Advanced | 35 min | `AML.T0010.005`, `AML.T0104`, `AML.T0011.002` |
| `kep-m09-l` | Model Corruption | Intermediate | 24 min | `AML.T0076` |

### Module 10

| ID | Challenge | Tier | Target | ATLAS rows |
|---|---|---|---:|---|
| `kep-m10-h` | Service Denial | Intermediate | 22 min | `AML.T0029` |
| `kep-m10-i` | Cost Amplification | Advanced | 35 min | `AML.T0034`, `AML.T0034.000`, `AML.T0034.001` |
| `kep-m10-j` | Agentic Budget Loop | Advanced | 40 min | `AML.T0034.002` |
| `kep-m10-k` | Chaff Flood | Intermediate | 24 min | `AML.T0046` |
| `kep-m10-l` | Financial Harm | Advanced | 35 min | `AML.T0048`, `AML.T0048.000` |
| `kep-m10-m` | Reputational Harm | Advanced | 35 min | `AML.T0048.001` |
| `kep-m10-n` | Societal Harm | Expert | 55 min | `AML.T0048.002` |
| `kep-m10-o` | User Harm | Intermediate | 22 min | `AML.T0048.003` |
| `kep-m10-p` | Dataset Integrity Destruction | Intermediate | 30 min | `AML.T0059` |
| `kep-m10-q` | Agent Tool Data Destruction | Expert | 50 min | `AML.T0101` |

## Existing Receipt Extensions

Nine missing parent rows do not need another participant flag because an
existing action already proves their semantics. They remain `planned` until
the implementation slice adds the exact governed binding and focused
participant proof.

| ATLAS row | Existing challenges | Why no new challenge |
|---|---|---|
| `AML.T0051` | `kep-m01-a`, `kep-m01-e` | Direct and indirect prompt-injection receipts prove the parent. |
| `AML.T0080` | `kep-m03-c`, `kep-m05-a` | Thread and memory receipts prove context poisoning. |
| `AML.T0024` | `kep-m04-c`, `kep-m04-d`, `kep-m04-e` | Fresh inference outputs prove inference-API exfiltration. |
| `AML.T0069` | `kep-m04-b` | Reconstructing hidden instructions proves system-information discovery. |
| `AML.T0069.002` | `kep-m04-b` | The reconstruction contains the live system prompt. |
| `AML.T0043` | `kep-m06-a`, `kep-m06-c`, `kep-m06-e` | Manual, optimized, and generated examples prove adversarial-data crafting. |
| `AML.T0005` | `kep-m08-a` through `kep-m08-d` | Teacher query and student training produce a functioning proxy. |
| `AML.T0040` | `kep-m08-a` | The participant uses the real teacher inference API. |
| `AML.T0112` | `kep-m10-c`, `kep-m10-e` | Executable artifact and deployed effect prove machine compromise. |

## Realization Additions

The design deliberately reuses the current real PostgreSQL/pgvector, Gitea,
Redmine, Keycloak, Envoy, OPA, vLLM, MLflow, MinIO, Airflow, JupyterLab,
OpenTelemetry, Kasm, and GCP surfaces. The implementation slices add only the
capabilities their SDL contracts require, including:

- real range-local package and OCI registries, searchable research content,
  DNS, mail/webmail, contained public sites, and two attested physical edge
  accelerator appliances for the hardware supply-chain path;
- disposable Linux agent, loader, sandbox, and container-escape workers;
- real browser automation, document AI, media generation/classification, and
  webcam/WebRTC vision inference;
- contained C2, synthetic cost, financial, allocation, publication, and user
  outcome services; and
- encrypted full-content research storage and readback from research telemetry.

These are implementation requirements, not a parallel topology. Each node,
service, feature, relationship, identity, content artifact, and route must be
added to the modular ACES SDL before its provider realization is built.
