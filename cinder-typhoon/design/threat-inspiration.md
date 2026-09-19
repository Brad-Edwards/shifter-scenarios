# Threat behavior and scenario inspiration

Research date: September 18, 2026. These references shape the fictional campaign's
behavior and causal sequence. The [CTF catalog](reference-catalog.md) separately
supports challenge mechanisms and proposed difficulty. Neither an ATT&CK entry
nor a real APT name establishes a hard challenge.

## The MITRE repository

The relevant repository is the **MITRE Center for Threat-Informed Defense
Adversary Emulation Library**. It contains intelligence summaries, operational
flows, and emulation plans rather than just a flat technique list.
[Official repository](https://github.com/center-for-threat-informed-defense/adversary_emulation_library).

Use selected sequences and their intermediate purposes. Cinder Typhoon is a
fictional composite, not a claim to recreate one actor or a particular water
intrusion. The story begins with an assumed developer compromise, so a source
plan's phishing opening need not become a new compulsory initial-access exam.

| Source | What the published sequence contributes | Proposed campaign use | Deliberate adaptation |
| --- | --- | --- | --- |
| [menuPass operations flow](https://raw.githubusercontent.com/center-for-threat-informed-defense/adversary_emulation_library/master/menu_pass/Operations_Flow.md) | Discover shared provider infrastructure; abuse trusted access into a customer; continue discovery, credential access, movement, collection, and staging. | K25–K27 make the supplier/customer relationship operational. W01/W02/W03 reveal what the resulting customer foothold can actually reach. | The source concerns an MSP. KeplerOps is a software supplier, so actual connector/package consumption supplies the bridge. Customer entry has limited corporate scope. |
| [APT29 plan overview](https://raw.githubusercontent.com/center-for-threat-informed-defense/adversary_emulation_library/master/apt29/README.md) | Different operational tempos and a distinction between initial collection and later persistent access. | K15 produces a bounded collection payoff; K16 tests an established capability across a simulated shift change. | Optional episodes can have different rhythms without real-time waiting or mandatory stealth scoring. No need to reproduce the entire domain-compromise plan. |
| [OilRig emulation overview](https://raw.githubusercontent.com/center-for-threat-informed-defense/adversary_emulation_library/master/oilrig/README.md) | Enterprise movement has an intelligence purpose: reach a data service holding critical-infrastructure information. | W06/W07/W11/W12 turn corporate access into meaningful operational records and engineering clues. | Collection supports an intruder's next decision. It is not an unrelated forensic exam or a demand to deploy the source actor's malware. |

These are behavioral inspirations. The detailed plans can inform realistic
artifacts and limited scope for each stage, but their infrastructure layouts
are not adopted. Importing an entire emulation plan would prejudge topology and
add actions whose gameplay value has not been established.

Draft 3 makes the intermediate purposes more concrete. K29 pursues durable
supplier delivery after a disclosed release change; K30/K31 recover specific
customer and commissioning intelligence. W33 uses that kind of knowledge to
plan a bounded economic effect, and W34 distinguishes a manipulated planning
view from independent process truth. These are fictional adaptations, not
claims that the cited actors performed these exact operations. Their technical
precedents and new constraints are in the
[campaign contracts](campaign-operations.md) and [source catalog](reference-catalog.md).

The catalog includes Sandworm, but there is no need to import destructive
campaign outcomes to give the OT section credibility. The supplied financial
loss and water-restriction story controls the selection.

## ATT&CK Enterprise

Select a small set of behaviors with visible effects, then check their mapping.
Do not award flags for naming technique IDs or attempt full matrix coverage.

| Verified reference | Appropriate use in this design |
| --- | --- |
| [T1195.001: Compromise Software Dependencies and Development Tools](https://attack.mitre.org/techniques/T1195/001/) | The established opening compromise and K05/K06/K26 dependency-consumption route. The technical achievement is the consumer's changed execution. |
| [T1199: Trusted Relationship](https://attack.mitre.org/techniques/T1199/) | Supplier support and distribution privileges become the customer bridge in K27. The relationship is necessary context; possessing a customer name alone is not an exploit. |
| [T1078.004: Cloud Accounts](https://attack.mitre.org/techniques/T1078/004/) | K13/K14 distinguish a found workload identity from a usable role with actual resource scope. |
| [T1530: Data from Cloud Storage](https://attack.mitre.org/techniques/T1530/) | K13/K15 give object and export access a bounded collection result. |

These mappings identify relevant actions, not complete coverage of every
operation. One challenge can cross several techniques; one technique can support
several difficulty levels. Final mapping follows the implemented behavior.

## ATT&CK for ICS

**ATT&CK for ICS** is the relevant MITRE framework for the OT portion.
[Official ICS matrix](https://attack.mitre.org/matrices/ics/).

| Verified reference | Proposed challenge use |
| --- | --- |
| [T0861: Point & Tag Identification](https://attack.mitre.org/techniques/T0861/) | W18 identifies the intended equipment through engineering information and observations. |
| [T0801: Monitor Process State](https://attack.mitre.org/techniques/T0801/) | W17/W25 distinguish live conditions and operating state from a copied report. |
| [T0845: Program Upload](https://attack.mitre.org/techniques/T0845/) | A possible W21 implementation retrieves the running control project for comparison. Use this mapping only if the player actually retrieves it from the control system, not merely from a corporate archive. |
| [T0836: Modify Parameter](https://attack.mitre.org/techniques/T0836/) | A possible W25/W30 implementation changes an operating parameter under earned control. It is not automatically the right tag for a program exploit. |
| [T1692.001: Unauthorized Message: Command Message](https://attack.mitre.org/techniques/T1692/001/) | W30's unauthorized control action. This is the current reference checked for this draft; avoid copying an older command-message ID without checking the framework version. |
| [T0831: Manipulation of Control](https://attack.mitre.org/techniques/T0831/) | The reservoir effect is a changed physical process in the simulator. It requires independent state evidence. |

The distinction between monitoring, authority, command acceptance, and actual
actuation is fertile challenge material. It allows approachable observations,
medium process interpretation, hard control acquisition, and optional deep
engineering research in the same organization.

## ATLAS

Use [MITRE's official ATLAS data](https://github.com/mitre-atlas/atlas-data),
checked against the
[September 2026 dataset](https://raw.githubusercontent.com/mitre-atlas/atlas-data/main/dist/v6/ATLAS-2026.09.yaml).
Relevant entries include AML.T0051 (LLM Prompt Injection), its indirect subtype
AML.T0051.001, AML.T0056 (Extract LLM System Prompt), and AML.T0057 (LLM Data
Leakage). These are candidate mappings, not instructions to implement every
variation.

| Operation | Player task and tier ceiling | Compute and adjudication |
| --- | --- | --- |
| K21: Policy in the margins | Easy/medium configuration/context disclosure; a system-prompt-related discovery must reveal something useful to the support investigation. | Small configuration and conversation artifacts; at most the final extraction requires an inference call. No secret-provider keys in the target. |
| K22: Helpful attachment | Easy/medium indirect instruction in a retrieved support attachment, leading to a bounded unauthorized tool action. | Tiny fixed corpus; one short model interaction and, if required, one follow-up. Grade the actual tool effect, not whether the answer contains a preferred phrase. |
| K23: Missing tenant filter | Easy/medium failure to enforce retrieval isolation. | Deterministic document/API behavior. Apply ATLAS leakage mapping only when the implemented AI data path supports it; otherwise classify as ordinary application authorization. |
| K24: Complete and run | Easy/medium context selection and unsafe execution by the completion application, directly inspired by Chrono Mind. | Small frozen model and short completion. The weakness is application trust, not defeating a sophisticated model. |
| W10: Another district's answer | Easy/medium district-scoped planning-data disclosure through the assistant's retrieval interface. | Small fixed records and deterministic retrieval; no training or expensive search. It supplies information, never control authority. |

These five operations account for fifteen proposed flags, some independent of
model inference. None is on either mandatory supplier route or required for the
reservoir ending. Exclude training-data poisoning that needs retraining,
large-scale model extraction, gradient optimization, GPU races, and open-ended
jailbreak search. A toy prompt puzzle without a business effect does not earn
a place merely because ATLAS names a related technique.

For prototyping, budget no more than two short model calls per trial in the
three operations that actually need generation. A candidate ceiling of twenty
trials per operation gives 120 calls per player and 36,000 calls for 300 players.
At a ceiling of 3,072 input and 384 output tokens per call, that is approximately
110.6 million input and 13.8 million output tokens. These are **worst-case
planning limits, not a cost quote or proof of cheap hosting**. Include retries,
staff activity, and burst headroom separately in the build budget. Pick the
smallest model that reliably supports the intended behavior and measure it.

Validate a much smaller typical solve budget. Display any trial budget and give
useful hints before players spend it on unproductive variation. A quota should
not become the challenge. If a model cannot support the operation reliably and
affordably, replace the generative part with a disclosed deterministic
application task and recalibrate it; do not secretly substitute a keyword
matcher while describing it as a genuine LLM vulnerability.

The participant's provided agent has a separate budget. Restricting that agent
to make the vulnerable assistant cheap would undermine the event's intended
uplift. Keep both budgets visible to the organizers and load-test them separately.
