# Participant Operation Contract

## Purpose

Every challenge is a step in Cinder Typhoon's operation against KeplerOps AI
Systems. It must work as an authentic adversary task before it is treated as a
scored challenge or mapped to ATLAS.

The challenge count and existing identifiers are catalog constraints, not
design inputs. A challenge may be renamed, remapped, recomposed, or rebuilt.
Several ATLAS rows may belong to one challenge when one realistic operation
materially performs them together. One row may require multiple participant
steps when the real technique cannot be honestly reduced to one action.

## Required Participant Record

Before implementation, every challenge must define all of the following.

| Field | Required Design Answer |
|---|---|
| Mission context | Why Cinder Typhoon performs this action now and how it advances the theft of KeplerOps AI capability. |
| Starting knowledge | Exactly what the participant has learned or earned before starting. No undisclosed magic values. |
| Discovery path | Where a participant can naturally find the target, clue, credential, artifact, weakness, or next action. |
| Participant surface | The browser, terminal, mail client, repository, notebook, API client, enterprise application, or other normal surface used. |
| Participant action | The concrete actions a human performs. Provisioning, orchestration, and hidden test calls cannot substitute for them. |
| Real mechanism | The actual software, protocol, model, data flow, vulnerability, or insecure design that makes the action work. |
| Observable result | What the participant sees in-world when the action succeeds or fails. |
| Operational consequence | What identity, access, data, control, artifact, or effect is gained and why it matters to the campaign. |
| ATLAS behavior | The exact official row behavior performed, including any qualifying AI-specific mechanism. |
| Training value | What security property, attack method, or defensive failure the participant learns by completing the operation. |
| Ambiguity controls | The clues, feedback, constraints, and hints that prevent blind guessing without giving away the solution. |
| Evidence | Server-observed facts sufficient to distinguish the real participant action from a shortcut or assertion. |
| Flag placement | The exact in-world artifact, record, response, or changed state that contains the flag and why the participant cannot reach it without completing the operation. |
| Reset | How mutable state returns to a valid start state without invalidating other campaign progress. |
| QA procedure | Command-by-command or click-by-click participant steps and exact expected observations. |
| Facilitation notes | The explanation, teaching points, likely mistakes, and diagnostic checks needed by an instructor. |

## Participant Equivalence

A challenge passes only when a human can complete it from the assigned Kali
workstation using the same access, information, credentials, and tools provided
to event participants.

The happy path may use:

- Chromium and normal web applications;
- terminal tools installed on Kali;
- participant-visible APIs documented or discoverable in-world;
- attacker-controlled mail and files;
- range-provided open models and Internet-accessible research resources;
- credentials, sessions, and access material earned through prior operations;
- real enterprise tools such as Git, issue trackers, notebooks, Airflow,
  MLflow, object storage, directories, and mail; and
- participant-created prompts, messages, datasets, packages, models, and other
  artifacts.

The happy path may not use:

- cloud consoles, host SSH, Docker, database consoles, service-account tokens,
  or generated deployment outputs;
- challenge IDs as commands or application concepts;
- buttons whose only function is to execute or prove a challenge;
- direct proof, receipt, evidence, flag, or oracle endpoints exposed as company
  functionality;
- precomputed attacker artifacts represented as participant-created work;
- API calls that perform an entire multi-system operation instead of the
  participant performing its meaningful steps; or
- credentials disclosed by mission text when the operation is supposed to earn
  them.

## Reality And Taste

KeplerOps applications must behave like applications a frontier AI company
would actually operate. A participant should infer the security problem from
normal company state, not from a challenge card explaining the exploit.

Examples:

- A phishing operation requires the participant to research a target, create a
  lure, send real email, conduct the social-engineering exchange, and retrieve
  the result. An endpoint that performs all five steps is invalid.
- A distillation attack requires teacher queries, a participant-owned labeled
  corpus, a real training job, a student artifact, and fidelity evaluation. A
  query counter plus a prebuilt surrogate is invalid.
- A RAG poisoning operation requires modifying content through a plausible
  ingestion path and observing a fresh retrieval or agent decision that uses
  the poisoned content. Submitting a challenge ID to a generic attempt endpoint
  is invalid.
- A model supply-chain compromise requires real artifact bytes, provenance,
  publication, resolution, loading, and changed behavior. Selecting a supplied
  candidate from a challenge menu is invalid.
- Model theft requires acquiring the actual protected artifact or reconstructing
  capability through a real extraction method. Returning a receipt that says
  theft occurred is invalid.

## ATLAS Mapping Gate

For each claimed row, reviewers must answer:

1. What exact participant behavior satisfies the official description?
2. What AI-specific aspect distinguishes it from ordinary enterprise ATT&CK,
   where ATLAS requires one?
3. What observable and server-owned facts prove that behavior occurred?
4. Which plausible shortcuts must fail?
5. Would an independent AI-security practitioner agree with the mapping after
   seeing only the participant actions and effects?

Any uncertain answer blocks the mapping. The operation must be redesigned or
the row assigned elsewhere.

## CTF Flag Convention

Every scored operation has one conventional static CTF flag in the range. The
participant retrieves it from the company or attacker state reached by doing
the operation and submits it to Shifter. There is no proof broker, proof API,
collection command, or separate proof protocol.

Flags follow the Polaris placement pattern:

- reconnaissance flags are embedded in the public record, metadata, source,
  DNS response, repository, or other material the participant discovers;
- access flags are stored in the protected mailbox, file, directory record,
  application page, configuration, or artifact reached with that access;
- model-behavior flags appear in the qualifying model response or resulting
  artifact only when the participant causes the required behavior;
- pipeline flags are written into the normal run output, report, registry
  record, model card, or artifact produced by the qualifying job;
- release and impact flags appear in the normal changed state or response of the
  affected system; and
- compound-operation flags are placed at the final consequence, after every
  required participant step has contributed to that state.

A canonical flag-placement ledger records a stable flag ID, static synthetic
value, host or service, exact path or state location, campaign operation, and
build source. The Shifter challenge loader projects the same static value as the
accepted answer. Build validation proves that every canonical value is present
at its declared location and absent from participant start material.

Flags use the established `FLAG{<16-hex>}` format. Static synthetic flags are
committed scenario content. They need not differ by participant because every
participant receives an isolated range and independent score state.

The flag is the permitted CTF abstraction. It should fit naturally into the
artifact or result, but it does not need an elaborate business explanation.
KeplerOps applications still do not display points, hints, challenge IDs, or a
challenge board.

## Challenge Quality Gate

A challenge is ready to build only when all statements are true:

- The action is credible for Cinder Typhoon and advances the campaign.
- The participant can discover how to begin from existing information.
- The participant performs the security-relevant work themselves.
- The target and effect are real within the range.
- Success produces a clear in-world observation and a meaningful campaign
  consequence.
- Failure produces feedback that supports investigation rather than guessing.
- The challenge teaches the intended technique without requiring unexplained
  syntax, magic prompts, or hidden implementation knowledge.
- The ATLAS mapping survives direct comparison with the official description.
- A non-specialist QA tester can follow the participant-equivalent walkthrough.
- An instructor can explain why the attack worked and how it should be
  prevented.
