# Cinder Typhoon operation portfolio

Status: operation concepts and acceptance criteria, not implemented challenges.
Companion to the [architecture](challenge-architecture-v1.md). Each numbered item
below is an operation allocation containing several substantive scored outcomes.
The challenge budget belongs to the whole family, not equally to every item.
The **67 campaign operations plus four training boxes** form the initial
71-operation worksheet.

Names describe author intent. Participant-facing briefs should explain the
mission without revealing the intended weakness.

## KeplerOps: 32 operations, 104 challenge slots

| Family | Operation allocations | Capability or evidence carried forward |
| --- | --- | --- |
| K1: Borrowed desk; 12 slots | **1. Session scope:** establish what the compromised developer can access and prove a first limited service interaction. **2. Development history:** recover useful access from a past development action and distinguish it from revoked residue. **3. Working context:** use local project/browser state to reach an internal service. **4. Current incident:** reconstruct which package and execution context created the foothold. | Verified identities, an accurate view of the workstation, internal application/repository leads. |
| K2: Whose identity?; 12 slots | **1. Identity mismatch:** exploit differing application and enterprise views of the same principal. **2. Support delegation:** acquire a bounded support capability. **3. Customer relationships:** correlate a real customer entitlement with its integration profile. **4. Service lifecycle:** exploit a service account's ownership or rotation workflow to gain a distinct capability. | Support context, ARWC's customer relationship, usable enterprise identities. |
| K3: Dependency conveyor; 14 slots | **1. Package ancestry:** reconstruct installed-versus-declared dependency lineage. **2. Registry boundaries:** turn limited publisher access into influence over a relevant package. **3. Build inputs:** exploit a dependency-resolution or cache trust mistake in a controlled consumer. **4. Shared component:** demonstrate an effect across a second internal consumer with a different trust assumption. | Repository/registry influence and a verified route into build inputs. |
| K4: Build service; 16 slots | **1. Review context:** cross the separation between a contributor's changes and privileged build execution. **2. Artifact origin:** distinguish and exploit how build outputs inherit authority. **3. Cache isolation:** cross a build-context boundary without assuming all runners share privileges. **4. Workload identity:** obtain a scoped, usable build-service identity. **5. Runner isolation:** an expert branch requiring a separate flaw in the job/worker boundary. | Controlled builds and scoped identities; deeper runner access is optional. |
| K5: Cloud delegation; 14 slots | **1. Role composition:** determine and exercise the usable permission path from a workload identity. **2. Object authority:** exploit metadata/content access differences to recover a deployment configuration. **3. Job authority:** turn a narrow automation capability into a distinct service action. **4. Federation composition:** an expert chain across claims, delegation, and resource policy. | Release-side technical authority, customer deployment context, optional stronger cloud access. |
| K6: Assistant authority; 12 slots | **1. Tool scope:** obtain evidence of the assistant's actual delegated rights through its business workflow. **2. Retrieval trust:** influence an answer or action through lower-trust retrieved content, then verify the effect. **3. Deputy action:** cross from a support request into an unauthorized scoped tool action. **4. Workflow authority:** exploit the handoff between assistant output and a release/support approval record. | A narrowly scoped but real workflow capability required for release promotion. |
| K7: Release engineering; 14 slots | **1. Accepted candidate:** construct an altered candidate that still performs its ordinary function. **2. Promotion binding:** cross the intended separation between a build candidate and a promoted release. **3. Consumer identity:** reconcile which bytes, identity, and configuration the deployment mechanism will consume. **4. Provenance disagreement:** an elite alternate chain against stricter promotion checks. | A release that is accepted, remains functional, and has the intended supplier-side effect. |
| K8: Customer bridge; 10 slots | **1. Tenant binding:** exercise the correct customer entitlement and deployment relationship. **2. Customer consumption:** induce actual ARWC consumption and verify a limited corporate foothold. **3. Constrained delivery:** an elite alternate operation under stricter delivery and service-continuity constraints. | ARWC corporate access with observable limits; no inherited OT authority. |

The mandatory route need not solve every operation in a family. For example,
the build runner's deeper isolation flaw does not gate workload identity, and
the stricter provenance variant does not gate the ordinary accepted release.
They must nevertheless be distinct technical work with valuable outcomes.

The research focus on supply chains does not justify making every operation
another exposed token. Credentials may start an operation; scope and subsequent
trust boundaries should determine what remains to be done.

## ARWC: 35 operations, 120 challenge slots

| Family | Operation allocations | Capability or evidence carried forward |
| --- | --- | --- |
| W1: Supplier footprint; 10 slots | **1. Integration context:** establish the corporate foothold's effective rights. **2. Local extension:** cross a separate application/workload boundary from that foothold. **3. Corporate leads:** recover and use access to an internal operational service. | Restricted corporate presence and identity/data leads. |
| W2: Corporate identity; 14 slots | **1. Application principal:** turn application control into a scoped enterprise identity. **2. Delegation path:** cross a distinct service-to-service delegation boundary. **3. Maintenance role:** acquire the identity needed to exercise a maintenance workflow. **4. Restricted administration:** an expert branch with stronger privileges but an additional independent barrier. | Usable corporate authority, with explicit separation from controller authority. |
| W3: Data operations; 12 slots | **1. Asset reconciliation:** join inconsistent corporate identifiers to the correct operational assets. **2. Maintenance records:** recover and verify the relevant contractor, work order, and entitlement. **3. Water ledger:** derive the reservoir's allocation and replacement-cost implications from protected data. **4. Data-service boundary:** exploit a separate data-processing trust boundary to obtain deeper operational evidence. | Correct maintenance context, asset relationships, and the business meaning of reserve loss. |
| W4: Maintenance trust; 14 slots | **1. Work-order authority:** turn identity and the correct records into a scoped maintenance session. **2. Contractor boundary:** cross an independently enforced vendor/customer access boundary. **3. Session binding:** overcome a flaw in how maintenance scope binds to the relevant asset. **4. Maintenance broker:** an expert alternate route with a different trust assumption. | A usable path to a restricted operational service, not general access to every OT asset. |
| W5: OT vantage; 10 slots | **1. Reach and read:** establish communication and prove the actual limits of the vantage. **2. Historical context:** acquire a useful historical/diagnostic data source under its own permissions. **3. Operational boundary:** cross the next service boundary to reach engineering and process evidence. | Read/diagnostic capability and leads for two parallel investigations. |
| W6: Process truth; 14 slots | **1. Asset meaning:** map engineering identifiers to physical functions. **2. Conflicting telemetry:** resolve units, update delays, and displayed-versus-actual state from evidence. **3. Operating modes:** infer the preconditions for the intended reservoir operation. **4. Partial observability:** an elite variant requiring a validated process model from incomplete but sufficient observations. | A correct, testable process model; the proposed effect must match the narrative. |
| W7: Engineering workbench; 14 slots | **1. Project recovery:** gain access to the correct engineering project and establish its version. **2. Client behavior:** analyze an interface/client sufficiently to build a working read/diagnostic tool. **3. Engineering authority:** cross the separate boundary to an engineering function. **4. Stateful protocol flaw:** an elite implementation/analysis operation against a credible adapter or session mechanism. | Working engineering tools and a distinct control-related capability. |
| W8: Controller authority; 12 slots | **1. Scope and mode:** establish control authority for the correct asset and operating mode. **2. Session continuity:** make the capability usable across the relevant controller/session transition. **3. Restricted controller:** an elite alternate control path under stronger constraints. | Reliable authority to perform the intended operation, still requiring correct process knowledge. |
| W9: Coordinated release; 10 slots | **1. Authority composition:** combine the relevant capabilities without assuming one controller's rights cover every dependency. **2. Process sequence:** construct and validate the intended operation against observable process conditions. **3. Changed conditions:** an elite branch requiring adaptation to a different supported starting state. | A repeatable operation that can be evaluated against the real process model. |
| W10: Open gates; 10 slots | **1. Campaign execution:** open the correct gates and demonstrate the reserve-loss effect. **2. Reliable operation:** an optional variant requiring recovery from a specified session/mode transition while preserving the intended effect. **3. Alternate operating case:** an optional elite variant with a different control constraint and corresponding evidence. | Earned narrative completion, plus further technically distinct work for fast finishers. |

Variants count only when they change the reasoning or technique. New random
identifiers, different water-level constants, or replaying the same script do
not justify extra challenges. W9 changed conditions and W10's alternate case
must be differentiated in their briefs, or merged and the freed slots reassigned.

## Reference-route budget

This table makes the proposed route allocation inspectable. It is not a list
of challenge IDs and must not be described as a verified shortest path.

| Family | Route milestones | Remaining family slots |
| --- | ---: | ---: |
| K1 | 4 | 8 |
| K2 | 3 | 9 |
| K3 | 3 | 11 |
| K4 | 4 | 12 |
| K5 | 4 | 10 |
| K6 | 4 | 8 |
| K7 | 4 | 10 |
| K8 | 4 | 6 |
| **KeplerOps** | **30** | **74** |
| W1 | 3 | 7 |
| W2 | 4 | 10 |
| W3 | 3 | 9 |
| W4 | 4 | 10 |
| W5 | 3 | 7 |
| W6 | 4 | 10 |
| W7 | 4 | 10 |
| W8 | 4 | 8 |
| W9 | 4 | 6 |
| W10 | 5 | 5 |
| **ARWC** | **38** | **82** |

Reference milestones are scored outcomes along an operation, not artificial
permission locks. Possessing and exercising the required capability unlocks
progress even when a player discovered an unanticipated valid route. Optional
operations may reveal useful shortcuts, but must not make a necessary dependency
invisible in the authoring graph.

## What could justify the upper tiers

These exemplars specify the intended source of difficulty, the agent's role,
and a falsifiable success test. They are **candidates for prototyping**, not
claims that the words “provenance,” “AI,” or “OT” establish elite difficulty.
Fresh testing with strong operators and current agents can downgrade any of them.

The upper portfolio must include different kinds of difficult work: original
code-level vulnerability discovery and exploitation, trust/workflow composition,
and process inference with stateful execution. Making every elite task another
identity-policy puzzle would test too narrow a skill set. At least one prototype
must establish the code-exploitation ceiling before the overall allocation is
accepted.

### E1: The signed release that is not the deployed release

**Placement:** K7, optional elite depth; a less demanding promotion chain remains
on the campaign route.

KeplerOps has separate build, attestation, promotion, and customer-consumption
steps. A deliberately engineered disagreement in identity binding or artifact
interpretation creates an opportunity even though signatures verify correctly.
The player receives discoverable source/configuration and realistic workflow
traces after earning the relevant access.

The difficult work is constructing and testing a model of which authority binds
to which artifact at each step, finding the mismatch, and exploiting it without
breaking the required application behavior. The agent can inspect code, compare
execution paths, generate candidate artifacts, and automate trials.

**Proof:** the independently observed customer consumes the altered candidate
through the ordinary workflow and passes the defined functional checks.
An accepted upload, forged screen, broken package, or signature alone fails.
If one obvious path traversal achieves the entire outcome in minutes, this is
not an elite operation and must be relabeled or redesigned.

### E2: Three bounded identities, one unintended authority

**Placement:** K5 expert work, with an optional stronger composition in K8.

The visible identities each have narrow permissions. An engineered interaction
between workload claims, delegation, and application-side authorization allows
an unintended scoped effect; no single policy grants universal administrative
access. Policy and application evidence become available through earned access.

The player must identify a usable chain and distinguish credentials that are
valid from credentials accepted for the required audience, resource, and action.
The agent can enumerate candidate paths and build tests; superficial permission
matching should produce plausible but diagnosable failures.

**Proof:** the intended service action occurs under the derived authority in
the correct tenant. Merely acquiring a token or invoking an unrelated resource
fails. Current agents may make this much easier than expected; it is expert only
if fresh tests support that label.

### E3: A useful assistant becomes a confused deputy

**Placement:** K6, with a reliable advanced core and optional expert depth.

The internal assistant retrieves support material and acts through tools with
separate authorization scopes. The player can influence a lower-trust artifact
but cannot directly invoke the privileged action. The intended weakness lies
in how one component promotes content or identity into authority across a handoff.

The player must map the workflow, locate a viable influence surface, and cause
an actual unauthorized business action while the ordinary workflow remains
functional. The player's agent can inspect artifacts, design trials, and compare
traces. This is more than convincing a chatbot to print a phrase.

**Proof:** a scoped release/support record changes through the victim workflow;
the independent service observes the effect. A persuasive answer without a tool
effect fails. Fix the victim model/version where possible, retain relevant
observable traces, and test repeated fresh sessions. If success remains primarily
stochastic persuasion, remove it as a mandatory gate and redesign the weakness
in the surrounding tool/authorization handling.

### E4: Enterprise control is not maintenance control

**Placement:** W2–W4, rising from advanced to expert.

The supplier foothold, enterprise applications, directory services, contractor
relationship, and maintenance workflow disagree about parts of a principal's
identity or scope. The player must combine several partial capabilities and the
correct asset relationship to establish a usable maintenance session.

The agent can analyze directories, application code, records, and credentials.
The player-agent combination must select a chain that survives each boundary.
Distinct stages deserve partial credit because each creates an independently
usable capability; repeating the same credential discovery does not.

**Proof:** a session reaches the defined operational service with the intended
scope, while wrong assets and unrelated identities remain rejected. Domain
administrator access alone is neither a hidden shortcut nor a completion proof.

### E5: A client implementation hides a stateful protocol flaw

**Placement:** W7/W8, optional elite operation or a validated expert alternate
route into controller authority.

Players earn an engineering client or adapter implementation, a small legitimate
trace, and a way to observe errors. A deliberately engineered vulnerability lies
in session/mode transition handling or authority binding, not a guessed command
name or weak encoding. The process interface should have coherent state rules.

For the original code-exploitation candidate, use a credible native adapter
with an engineered, state-dependent memory-lifetime defect. The player must
discover the defect and develop a usable exploit under the prototype's actual
mitigations and session constraints. The exact defect and mitigations are
prototype decisions; the intended work is more demanding than recognizing a
published CVE or changing a serialized role field. Source visibility is allowed
and should not invalidate the intended difficulty.

The work includes reverse engineering, forming a state model, locating the
weakness, and constructing a client or exploit that works after a fresh session.
Agents can decompile, infer layouts, write harnesses, and run experiments.

**Proof:** the required control capability works under fresh session conditions
and within the specified scope. A crash, a replayed diagnostic reply, or a client
that succeeds only in the author's already-prepared session fails. Tooling and
captures are provided in a way that makes discovery possible; “obscure OT” is
not the source of difficulty.

This is an optional elite route. It should neither make every participant learn
native exploitation to reach the story nor become an empty label attached to
a simpler required protocol task. If the tested exploit is too large for a
single event operation, narrow its scope while preserving the substantive
discovery and reliability work.

### E6: The screen is correct, the interpretation is wrong

**Placement:** W6, expert core with an optional elite partial-observability case.

Engineering records, historical observations, and live displays provide enough
information to identify the actual controlled process. Some evidence differs
because of real semantics: update intervals, operating modes, identifiers, or
units. These differences have explainable causes, not arbitrary red herrings.

The player-agent combination must test competing interpretations and produce a
model that predicts a permitted observation or bounded experiment. The agent
helps parse records and fit hypotheses; guessing a tag name does not complete
the operation.

**Proof:** the model correctly predicts the specified independent observations
under the supported starting cases. The elite variant must remove an observation
in a way that requires an additional inference, not merely more waiting. A
water/OT reviewer must first establish that the exercise's process makes sense.

### E7: Compose an operation that actually works

**Placement:** W9/W10, including the required elite finale.

The player arrives with earned maintenance/controller authority, a process model,
and engineering tooling. These do not automatically form a reliable operation.
The finale requires composing them across the relevant identities, operating
modes, and process conditions, then verifying the consequence.

The agent can generate and run the client, inspect telemetry, and revise a
failed attempt. The remaining difficulty must be in the composition and
diagnosis of state-dependent behavior, rather than manually typing a long list
of known commands. No wall-clock appointment or random service failure is used
to make the task hard.

**Proof:** the simulated gates and reserve state independently satisfy the
defined objective. Replaying a final flag or changing only a display fails.
Use a fresh supported state for reliability testing; do not require extra runs
of every player unless reliability is explicitly a separate scored operation.

If the earned capabilities make this final composition trivial, downgrade it
and create real additional technical work. A long preceding route cannot
justify advertising the final action as elite.

## Authoring contract for every operation

Before receiving final challenge slots, an operation needs:

- Its mission purpose, starting access, discoverable evidence, and exact output.
- The independently meaningful achievements being scored, with marginal work
  after each predecessor stated explicitly.
- Required and optional dependencies, and the behavior of alternate valid routes.
- The intended technical weakness, complete author solve, and a clean reset.
- Independent positive and negative success checks, including partial effects.
- An account of what the current provided agent handles readily and what remains
  difficult; record strong BYO results as well.
- A hint ladder, plausible failure feedback, and the expected recovery path.
- Fresh participant timings and the resulting difficulty assignment.

The next authoring pass should merge duplicate concepts before expanding any
family simply to meet its allocation. If a family cannot support the proposed
count without padding, move capacity to a distinct operation elsewhere and
recheck dependencies and total workload.
