# Challenge Design Research

## Purpose

This document translates established CTF design guidance, AI red-team practice,
and empirical AI-security competitions into binding design rules for the
KeplerOps AI Systems campaign. It is not a bibliography attached after the
fact. Every operation must survive the review gates derived here.

The central design problem is not making an operation technically possible. It
is making the intended security lesson discoverable, authentic, and satisfying
without reducing it to a recipe. Difficulty must come from the security work,
not from guessing what the author had in mind.

## Research Base

### General CTF design

- Chung and Cohen's CTF design paper warns that artificial constraints,
  convolution, ambiguity, luck, hidden file locations, and unexplained
  transformations frustrate participants without adding learning value. It
  argues that a good challenge leads a participant through its solution process
  with digital breadcrumbs and gives positive feedback when the participant is
  on the right track.
  [Toward Better CTFs](https://www.usenix.org/system/files/conference/3gse14/3gse14-chung.pdf)
- CTFd's published challenge levels distinguish difficulty by required
  knowledge, number of mechanisms, amount of custom tooling, and realism. They
  do not define harder challenges as less legible versions of easier ones.
  [CTFd challenge levels](https://docs.ctfd.io/events/challenge-levels/)
- CTFd supports explicit prerequisites and a recommended next challenge. The
  campaign should use those affordances to expose a meaningful path without
  duplicating challenge records.
  [CTFd requirements](https://docs.ctfd.io/docs/challenges/requirements/)
  [CTFd challenge creation](https://docs.ctfd.io/tutorials/challenges/creating-challenges/)
- CTFd supports progressive hints. Hints in this event are free because their
  purpose is to preserve learning and momentum, not to create a second scoring
  game.
  [CTFd hints](https://docs.ctfd.io/docs/challenges/hints/)

### AI-security exercise design

- OWASP frames GenAI red teaming as a risk-based, system-level activity across
  model evaluation, implementation, infrastructure, and runtime behavior. The
  campaign therefore exercises deployed AI systems and their surrounding
  enterprise, not a board of disconnected chatbot riddles.
  [OWASP GenAI Red Teaming Guide](https://genai.owasp.org/resource/genai-red-teaming-guide/)
- NIST's adversarial ML taxonomy separates attack goals, lifecycle stages,
  attacker knowledge, and attacker capabilities. Each operation must state
  these conditions so that a claimed technique is more than a label.
  [NIST AI 100-2e2025](https://doi.org/10.6028/NIST.AI.100-2e2025)
- MITRE ATLAS supplies the required behavior vocabulary and case studies. ATLAS
  is a coverage constraint, not a challenge generator: a row is claimed only
  where the participant performs the corresponding behavior against a real
  component in the campaign.
  [MITRE ATLAS](https://atlas.mitre.org/)
- PyRIT separates an attack objective from the prompts used to pursue it and
  scores an observed result against an explicit success criterion. This is the
  correct model for prompt-oriented operations: many semantically valid prompts
  may achieve one objective.
  [PyRIT datasets and objectives](https://microsoft.github.io/PyRIT/latest/code/datasets/dataset/)
  [PyRIT scoring](https://microsoft.github.io/PyRIT/latest/code/scoring/scoring/)
- PyRIT's cross-domain prompt-injection workflow models instructions planted in
  a real side channel and later consumed by a legitimate system. This supports
  challenge designs based on mail, documents, tickets, repositories, and
  retrieved content instead of direct access to a purpose-built injection box.
  [PyRIT workflows](https://microsoft.github.io/PyRIT/latest/code/executor/workflow/)
- NVIDIA garak separates probes, target generators, detectors, and evaluation.
  It also performs repeated generations and reports failure rates. Operations
  involving stochastic model behavior need bounded retries and robust outcome
  detection rather than a single lucky generation.
  [NVIDIA garak](https://github.com/NVIDIA/garak)
- The UK AI Security Institute's Inspect framework composes datasets, agents,
  tools, and scorers and retains inspectable logs. This reinforces the need for
  reproducible inputs, explicit tools, objective scoring, and QA-visible
  transcripts.
  [Inspect AI](https://www.aisi.gov.uk/blog/open-sourcing-our-testing-framework-inspect)

### Lessons from AI-security competitions

- HackAPrompt accepted free-form human attacks and collected a wide variety of
  successful strategies. Its results show why a prompt-injection operation
  should recognize a security effect, not compare participant prose to one
  canonical attack string.
  [HackAPrompt](https://paper.hackaprompt.com/)
- Tensor Trust produced large sets of human-generated prompt extraction and
  hijacking attacks through an open-ended game. It demonstrates that a clear
  objective and a stable success condition can support diverse solutions.
  [Tensor Trust](https://tensortrust.ai/paper/)
- AI Village's event retrospective distinguishes low-value easy volume from
  genuinely difficult work and records the operational importance of local
  contest surfaces with resilient remote model calls.
  [AI Village Generative Red Team recap](https://aivillage.org/blog/generative-recap/)
- A public competition against deployed agents used realistic scenarios and
  measured concrete policy violations such as unauthorized data access and
  actions. The useful unit of success was a system consequence, not merely
  adversarial text.
  [Agent Red Teaming competition paper](https://arxiv.org/abs/2507.20526)
- Cybench decomposes professional CTF tasks into subtasks for analysis while
  preserving the complete task. We use the same distinction: internal QA may
  enumerate milestones, but participant-facing content exposes only the
  evidence and hints appropriate to the selected difficulty.
  [Cybench](https://arxiv.org/abs/2408.08926)
- pwn.college's five-year experience found that large, loosely connected tasks
  without intermediate feedback frustrate newcomers. Its education-first
  design uses tightly scoped progression, monitors where learners drop off,
  and decomposes or adds scaffolding when confusion recurs.
  [Five Years of pwn.college](https://adamdoupe.com/publications/pwn-college-five-years-sigcse2026.pdf)
- A study of beginner CTF problem solving used a structurally similar tutorial,
  complete tool orientation, progressive milestone-aligned hints, and fresh
  pilot participants. This supports teaching the campaign's interaction grammar
  before assessing security synthesis and calibrating with people near the
  target audience.
  [Just Google It](https://www.usenix.org/system/files/usenixsecurity25-mattei.pdf)

### Verified implementation precedents

- Large-scale research finds that membership inference against broad LLM
  pretraining often performs near chance and can appear successful because of
  distribution shift. The campaign therefore does not pretend that arbitrary
  black-box chat access reliably reveals pretraining membership. `kep-m04-c`
  through `kep-m04-e` use a genuine deliberately overfit fine-tuned classifier,
  balanced member/non-member controls, held-out labels, perturbation-based
  signals, false-positive constraints, and rotated identifiers.
  [Do Membership Inference Attacks Work on Large Language Models?](https://arxiv.org/abs/2402.07841)
- SPV-MIA demonstrates a practical fine-tuned-LLM membership method based on
  self-calibration and probability variation under neighboring prompts. It is
  the methodological starting point for the participant notebook, but the
  operation accepts independently implemented methods that meet the published
  metrics.
  [Practical Membership Inference Attacks against Fine-tuned Large Language Models via Self-prompt Calibration](https://papers.nips.cc/paper_files/paper/2024/hash/f36ad694188bb4c4bbbd61e2038e069e-Abstract-Conference.html)
- Model Leeching demonstrates task-specific LLM extraction by collecting target
  outputs and training a smaller model, with separate train/evaluation splits.
  This supports the real teacher-query corpus, participant training, and
  disjoint fidelity evaluation in `kep-m08-a` through `kep-m08-f`; it does not
  justify a counter plus prebuilt surrogate.
  [Model Leeching](https://ceur-ws.org/Vol-3652/paper7.pdf)
- Official rCTF guidance states the core anti-guess principle directly: when
  progress depends on guessing author intent or arbitrary inputs, the challenge
  is unclear rather than difficult. This reinforces the operation-level
  breadcrumb, feedback, progressive-hint, and fresh-review gates.
  [Running a successful CTF](https://rctf.osec.io/meta/running-a-successful-ctf/)
- Samba documents provisioning an actual Active Directory forest with AD DNS,
  LDAP, Kerberos, domain members, and multiple DCs for redundancy. The clean
  enterprise uses two Samba AD DCs rather than treating a Keycloak realm or
  flat LDAP directory as an enterprise domain.
  [Samba Active Directory Domain Controller](https://wiki.samba.org/index.php/Setting_up_Samba_as_an_Active_Directory_Domain_Controller)
- Keycloak documents LDAP/Active Directory federation, Kerberos, OIDC/SAML,
  groups, roles, sessions, organizations, service accounts, and token audience
  controls. Those native mechanisms implement employee SSO, external partner
  separation, and scoped web/service access.
  [Keycloak Server Administration Guide](https://www.keycloak.org/docs/latest/server_admin/)
- k3s retains real Kubernetes server, agent, datastore, control-plane and
  workload semantics in a compact distribution. It is the minimum acceptable
  production substrate for operations that require Kubernetes discovery,
  KServe, GitOps, registry policy, pods, or runtime identity.
  [k3s architecture](https://docs.k3s.io/architecture)
- Argo CD's declarative application model supports a genuine source-to-desired-
  state-to-cluster reconciliation chain. Release operations must alter signed
  Git state and observe Argo reconciliation; changing a pod or alias through a
  challenge endpoint is invalid.
  [Argo CD declarative setup](https://argo-cd.readthedocs.io/en/stable/operator-manual/declarative-setup/)

- Langflow's official advisory for `CVE-2026-33017` documents unauthenticated
  code execution through attacker-controlled flow data passed to `exec()` by
  the public temporary-flow build endpoint. Versions through 1.8.2 are affected
  and 1.9.0 is patched. This is a defensible public-application foothold for
  `kep-m01-i`; it is not stretched into a defense-evasion claim.
  [Langflow GHSA-vwmf-pq79-vjvx](https://github.com/langflow-ai/langflow/security/advisories/GHSA-vwmf-pq79-vjvx)
- PickleScan's official advisory documents an incomplete unsafe-global policy
  before 0.0.22. A malicious pickle can use an allowed-looking callable to
  evade scanning and execute during deserialization. `kep-m02-e` pins the real
  vulnerable release and must also prove the normal importer executed the same
  bytes.
  [PickleScan GHSA-655q-fx9r-782v](https://github.com/mmaitre314/picklescan/security/advisories/GHSA-655q-fx9r-782v)
- The reviewed `mcp-package-docs` advisory for `CVE-2025-54073` includes a
  realistic indirect-prompt path: malicious package documentation causes an
  agent to invoke the documentation tool again with command-injection content.
  The reproduced vulnerable upstream is 0.1.26 and the local 0.1.27 source is
  the patched negative control. This replaces the
  invented review-companion exploit in `kep-m02-k`.
  [mcp-package-docs GHSA-vf9j-h32g-2764](https://github.com/advisories/GHSA-vf9j-h32g-2764)
- MLflow's reviewed `CVE-2024-0520` advisory covers releases before 2.9.0 and
  documents an attacker-controlled HTTP dataset filename that permits arbitrary
  file write and resulting code execution. `kep-m05-l` pins MLflow 2.8.1 and
  uses the real dataset-loading path to write an import hook in the disposable
  worker, then starts a normal child job and reads that process's own service
  credential. This provides an exact, reproducible replacement for the earlier
  unspecified worker exploit.
  [MLflow GHSA-5q6c-ffvg-xcm9](https://github.com/advisories/GHSA-5q6c-ffvg-xcm9)
- MCP's official security guidance treats local servers and stdio proxies as
  host-compromise boundaries: local servers run with client privileges, and a
  compromised proxy that can spawn stdio servers can provide arbitrary host
  command execution. `kep-m05-o` must materialize and expose those real trust
  relationships rather than inventing a challenge-only escape.
  [MCP security best practices](https://modelcontextprotocol.io/docs/2025-11-25/tutorials/security/security_best_practices)
- labgrid provides an OSS remote-hardware client/exporter/coordinator model,
  mutually exclusive reservable hardware places, and integrations for video,
  audio, measurement, USB, power, and other physical resources. This supplies a
  real implementation pattern for a pooled physical lane: a participant claims
  actual consumer display, camera, and lighting hardware, places their exact
  pattern on the display, changes live physical conditions, and obtains a fresh
  camera capture. LAVA is an alternative scheduler, but labgrid is the simpler
  fit for interactive control.
  [labgrid documentation](https://labgrid.readthedocs.io/en/v25.0/index.html)
  [labgrid remote resources](https://labgrid.readthedocs.io/en/stable/overview.html)

## Binding Design Principles

### 1. Security objective before puzzle mechanism

Every operation begins with a concrete attacker objective in the KeplerOps
enterprise. The technique, software, data, and flag placement follow from that
objective. An ATLAS row never supplies the story by itself.

### 2. One deterministic starting clue

The participant must have at least one justified first move based on information
already obtained in-world. A hostname, person, artifact, service, observed
behavior, or prior operation provides the lead. "Try things until something
works" is not a lead.

### 3. Breadcrumbs, not recipes

The environment responds to useful investigation:

- a discovered endpoint exposes a schema or error that narrows the next move;
- a repository reveals the component or data flow that explains behavior;
- a failed authorization attempt distinguishes authentication from policy;
- a model response or application audit trail confirms a changed condition;
- a recovered artifact names or links the next target.

Breadcrumbs are in-world evidence. The challenge description does not narrate
the exploit sequence.

### 4. Multiple valid strategies where the real system permits them

Prompt, agent, evasion, and poisoning operations are judged by their effect.
They must not require an exact phrase, ordering, encoding, or tool unless that
constraint is intrinsic to the technique being taught. The QA plan records at
least two materially different successful approaches for open-ended operations.

### 5. Observable baseline, action, and consequence

Before acting, the participant can observe the relevant normal behavior. After
acting, the participant can observe a durable or repeatable change. A model
saying "success" is not evidence unless the operation's objective is itself an
output behavior. Tool use, data access, workflow state, model metrics, release
state, or a recovered artifact must demonstrate the consequence.

### 6. Robust stochastic behavior

An operation cannot hinge on one sampled response. Where model behavior is
probabilistic, the design supplies:

- fixed model and decoding configuration for the event;
- a success detector based on the objective;
- a documented bounded number of attempts;
- a success threshold or one-of-many valid result set;
- deterministic reset of conversation and application state;
- a non-model fallback only for infrastructure failure, never to fake success.

### 7. Difficulty comes from meaningful work

- **Accessible**: one new concept, obvious surface, strong breadcrumbs, no
  custom code required.
- **Intermediate**: one primary mechanism with discovery or adaptation; basic
  scripting or documentation research may be useful.
- **Advanced**: multiple real mechanisms or trust boundaries; participants must
  analyze evidence and adapt tooling.
- **Expert**: long-horizon synthesis, weak-but-fair signals, or substantial
  custom analysis against authentic behavior. It is not merely an operation
  with fewer instructions.

No difficulty level may be created through arbitrary encoding, obscure trivia,
huge search spaces, rate-limit waiting, repeated manual work, or concealed
paths.

### 8. Onboarding teaches the interaction grammar

The first operations teach participants how this particular campaign works:
discover a lead, interact through the normal enterprise surface, observe a real
effect, recognize an embedded flag, submit it, and use the recovered information
to continue. Onboarding flags are earned, but the path is deliberately legible.

### 9. Flags are evidence found through the action

Flags live in normal in-world artifacts or changed state that the participant
can reach only after performing the operation. They do not appear because a
challenge-specific service decided a magic interaction was correct. Flag text
is recognizable and does not itself require interpretation.

### 10. Every operation advances the campaign

The participant gains at least one reusable asset: access, knowledge, tooling,
data, a credential, a foothold, a poisoned object, a model artifact, or an
operational effect. Reuse may be optional for branch operations, but no
operation exists solely to satisfy a matrix cell.

## Automatic Redesign Triggers

An operation fails review and returns to design if any answer is **yes**:

1. Could two reasonable participants read the available evidence and choose
   unrelated next actions with no way to distinguish them?
2. Does success depend on wording known only to the author?
3. Can a participant perform the intended technique but miss the flag because
   of an unrelated hidden path or format?
4. Is a reported success unsupported by an observable system or model effect?
5. Does the operation call a challenge-only endpoint or button that a real
   enterprise would not have?
6. Does it ask the participant to pretend they sent mail, changed data, trained
   a model, poisoned a pipeline, or affected production?
7. Can random model variation turn the same valid method into an unbounded
   failure?
8. Is difficulty primarily search-space size, waiting, repetition, trivia, or
   tool friction?
9. Does a hidden prerequisite come from the author's implementation knowledge
   rather than participant-observable evidence?
10. Does the operation duplicate an earlier lesson without adding a new
    decision, context, consequence, or technique?
11. Is the challenge title or description giving away the exploit while the
    environment gives too little evidence to discover it?
12. Would a non-expert QA tester be unable to distinguish a content defect from
    an infrastructure defect using the operation's QA procedure?

## Iterative Review Protocol

### Round 1: authoring review

For every operation, trace the complete participant path from currently known
evidence to flag. Record each inference and identify what in-world fact supports
it. Any unsupported inference is either supplied by a breadcrumb or removed.

### Round 2: adversarial anti-guess review

An independent reviewer receives only the participant-visible start state,
description, and hints. The reviewer attempts to identify:

- plausible dead ends;
- author-only assumptions;
- exact-string dependencies;
- false-positive and false-negative success states;
- alternate valid techniques the implementation would reject;
- places where a participant can break later operations while solving this one.

The reviewer is expected to reject operations. A rejection requires redesign,
not merely a more explicit final hint, unless the defect is genuinely missing
orientation.

### Round 3: calibration and pacing review

A second independent review considers the campaign rather than isolated
operations:

- whether a new participant earns a meaningful success early;
- whether each difficulty label matches participant effort;
- whether accessible and intermediate paths remain available throughout;
- whether advanced and expert operations test synthesis instead of obscurity;
- whether repeated interaction patterns become tedious;
- whether model-facing, application, infrastructure, data, and supply-chain
  work remain varied;
- whether prerequisite depth creates avoidable blockers;
- whether point distribution rewards progress and major consequences.

### Round 4: participant-equivalent validation plan

Before implementation is accepted, a fresh tester performs the documented path
from the participant workstation without management-plane assistance. For every
operation, QA records:

- elapsed time and hint use;
- first attempted action and why;
- dead ends encountered;
- successful method;
- observed baseline and consequence;
- flag discovery and submission;
- reset behavior;
- any mismatch between intended and perceived difficulty.

## Design Artifacts Required Before Implementation

The campaign is not ready to build until it has:

1. A detailed contract for all 134 operations.
2. An explicit map from all 172 required exact ATLAS rows to participant
   behaviors, excluding only `AML.T0010.000 Hardware`.
3. A difficulty and points distribution reviewed at act and campaign level.
4. An in-world flag placement ledger.
5. A prerequisite graph with at least one accessible continuation at each act.
6. A complete enterprise architecture derived from the operations.
7. Reset, QA, and facilitator procedures for every operation.
8. Recorded adversarial and calibration review findings and dispositions.
