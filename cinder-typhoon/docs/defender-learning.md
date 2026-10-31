# Cinder Typhoon: Defender-Learning Facilitator Guide

Operator-only. Not shipped to participants during live play.

This guide maps each major attack operation in Cinder Typhoon to its defensive
lesson, the evidence the operation produces, and a practical control or
engineering recommendation for the defender debrief.

The guide does not cover detection and response as scored challenges. It is
post-exercise material for a facilitator-led defender debrief.

---

## How to use this guide

The debrief distinguishes three categories of attacker action:

- **What the AI agent accelerated**: discovery and enumeration that the agent
  did faster than an unassisted human would.
- **What still required human judgment**: understanding a domain, designing a
  payload, recognizing that a control is meaningful.
- **What a defender's design decision would change**: the single engineering
  change that would break the chain at that point.

Do not claim that any one lab technique generalizes to every real product or
threat actor. The scenario is fictional and bounded.

---

## Training phase — T01–T04

### T01: Supplier onboarding and credential exposure

**Attacker actions:**
- Reads an unauthenticated handover document
- Discovers an unlisted dispatch route from client-side code
- Recovers a stored courier token from the workstation
- Submits a non-standard input to trigger a diagnostic code path

**Agent acceleration:** The agent found the unlisted route and the stored
credential in seconds. A human analyst would need several minutes of
browser-developer-tool and file-system exploration.

**Human judgment required:** Recognizing that the helper's non-standard input
triggered a privileged code path required reading the dispatch documentation.

**Defender lesson:** Credentials stored in clear text on a shared workstation
are equivalent to credentials stored nowhere. The helper's input-type switch
should be guarded by the same authorization check as its sensitive output.

**Evidenced by:** The handover document access log; the courier token issue
event; the diagnostic output recorded in the helper's audit stream.

**Practical control:** Require short-lived credentials with a use-specific
audience. An unscoped long-lived token stored on a workstation is a standing
access grant for anyone who reaches the machine.

---

### T02: Identity desk traversal and session recovery

**Attacker actions:**
- Reads a rehearsal account from the identity desk directory
- Discovers a hidden directory entry not shown in the UI
- Completes an account recovery using identity evidence rather than a password
- Lists the recovered account's task assignment

**Agent acceleration:** The agent enumerated the directory API endpoint and
compared it with the UI in one step.

**Human judgment required:** Recognizing that the recovery flow accepted the
recovered identity evidence as a second factor required reading the recovery
documentation.

**Defender lesson:** Directory APIs that return more data than the UI displays
expose accounts that administrators believe are hidden. API and UI authorization
must be enforced at the same level.

**Evidenced by:** The directory API query log; the recovery event; the assignment
read event.

**Practical control:** Enforce the same visibility rules at the API layer that
the UI applies. Privilege-reduced accounts should not appear in public directory
responses at any access level.

---

### T03: Repository history and build artifact recovery

**Attacker actions:**
- Recovers a deleted fixture from git history
- Reads a verbose CI error log to recover a build credential
- Inspects a supplied package archive without installing it
- Publishes a modified package that adds diagnostic output

**Agent acceleration:** The agent read the CI log and identified the credential
in the error output without human direction.

**Human judgment required:** The participant had to decide that the verbose log
was worth reading and to correlate the recovered credential with the rehearsal
endpoint.

**Defender lesson:** CI error logs are a common credential leak vector. A failed
build that includes authentication tokens in its stderr is equivalent to a
credential disclosed in plaintext.

**Evidenced by:** The git log access; the CI log read event; the rehearsal
package publication; the rehearsal run receipt.

**Practical control:** Build environments should never write authentication
material to stdout or stderr. Use secret scanning on CI log capture as a
compensating control, not as the primary protection.

---

### T04: Sensor data interpretation and bounded release

**Attacker actions:**
- Reads a tank observation and identifies the authoritative measurement field
- Decodes a binary controller status capture using the published field map
- Issues a bounded water release command using the session credential
- Identifies a discrepancy between a report and the independent instrument record

**Agent acceleration:** The agent decoded the binary capture quickly using the
published spec. Manual decoding would have taken significantly longer.

**Human judgment required:** The participant had to recognize that the report
and the instrument record disagreed and to determine which source to trust.

**Defender lesson:** Operator reports that do not include an audit trail to
the independent sensor record can be falsified. A reporting system that copies
from an intermediate database rather than querying the instrument directly
creates a falsification opportunity.

**Evidenced by:** The control command receipt; the independent instrument read;
the report discrepancy.

**Practical control:** Authoritative physical readings should be signed or
hashed at the instrument. A report that cannot produce a chain of custody from
the measurement to the printed value should not be used as the sole basis for
a safety or financial decision.

---

## KeplerOps phase — K01–K31

### K01–K03: Developer workstation foothold and source access

**Attacker actions:**
- Recovers stored git credentials from the workstation browser and credential store
- Reads a retained support conversation ticket from browser history and cookies
- Imports a CI review to discover an operator workspace path
- Submits a non-standard report type to the CI helper to disclose an internal API

**Agent acceleration:** Credential and cookie recovery from browser SQLite databases
is near-instant with agent assistance.

**Human judgment required:** Correlating the support ticket number with the
browser history and recognizing that the CI helper accepted report types beyond
the documented one required reading the documentation.

**Defender lesson:** A developer's browser session is a credential. Session
cookies stored in a profile on a shared workstation give access to every
service the developer was logged into. CI helpers that silently accept
undocumented input types are hidden attack surfaces.

**Evidenced by:** The git handover read; the support session event; the CI
review import event; the helper output.

---

### K04: Native indexer controlled overflow

**Attacker actions:**
- Analyzes an offline reproducer binary to determine the allocation boundary
  and trigger sentinel
- Submits a controlled body that overflows the allocation by exactly 16 bytes
- Reads the runtime descriptor that is only disclosed after a successful mutation
- Executes the completion routine to recover the protected dossier

**Agent acceleration:** Binary analysis of the reproducer accelerated the
allocation and sentinel discovery.

**Human judgment required:** Understanding that the routine would disclose a
dossier only in the post-mutation state required reading the descriptor fields.

**Defender lesson:** A native parser that allows caller-controlled allocation
with adjacency to a sentinel field is a controlled information disclosure.
The boundary between a normal allocation and an adjacent object should be
enforced by the runtime, not by the caller.

**Evidenced by:** The indexer state mutation event; the descriptor read; the
completion routine execution; the dossier recovery.

---

### K11: Policy compiler bytecode analysis

**Attacker actions:**
- Clones a retained policy compiler repository
- Recovers the instruction set by reading the embedded program from the binary
- Models the instruction set using the retained link map and opcode model API
- Submits an input that the compiler accepts as valid and recovers the corpus digest

**Agent acceleration:** The agent navigated the repository structure and
assembled the program model faster than manual analysis.

**Human judgment required:** Recognizing that the opcode model endpoint was
available and that the corpus check required a specific corpus identifier from
the README required reading the documentation.

**Defender lesson:** A retained legacy binary with a documented instruction set
and a service endpoint that validates inputs against that instruction set is an
oracle for accepted inputs. Organizations that retain legacy compiler toolchains
for compatibility should audit what the compiler accepts and whether the
acceptance criteria are discoverable.

**Evidenced by:** The program model submission; the corpus result digest.

---

### K18: Staff federation and identity provider modification

**Attacker actions:**
- Reads a restricted staff note via a server-side request forgery through the
  note-preview service identity
- Patches the identity registration using the preview service identity
- Mints a federated assertion that matches the modified registration
- Reads a protected customer record using the federated session

**Agent acceleration:** The agent identified the SSRF path and the note-preview
identity in the service directory quickly.

**Human judgment required:** Understanding that patching the registration would
cause the identity service to accept a new issuer required reading the registration
fields and the assertion endpoint documentation.

**Defender lesson:** A service that makes outbound requests using its own identity
can be used as a SSRF proxy if the destination is caller-controlled. The note-preview
service should not make identity-service requests on behalf of a developer credential.

**Evidenced by:** The registration read; the registration patch; the fixture assertion
mint; the protected customer record read.

---

### K26–K29: Release channel authority and connector delivery

**Attacker actions:**
- Earns a scoped channel token through the package approval flow
- Polls, activates, and rehearses rollback on the customer connector channel
- Compiles and signs a connector package using keys from the signer history
- Delivers a diagnostic package to the customer's ARWC runtime

**Agent acceleration:** Building and signing the package was significantly faster
with agent assistance.

**Human judgment required:** Understanding the key rollover mechanism and the
approval authority relationship required reading the signer history and the
approval documentation.

**Defender lesson:** A signed package that passes the approval flow but is not
the package the approver reviewed is a supply-chain integrity failure. Approval
should bind to a package digest, not just a version string. A channel token
that grants broad delivery authority should be scoped to the specific delivery
operation, tenant, and version.

**Evidenced by:** The approval receipt; the channel token; the activation receipt;
the diagnostic delivery receipt.

---

## ARWC phase — W01–W35

### W01–W06: Corporate access and identity escalation

**Attacker actions:**
- Reads the customer handover document earned from the KeplerOps connector delivery
- Recovers a planner session by exploiting retained browser state
- Accesses the corporate identity desk to enumerate provisioning packages
- Uses a temporary credential that was issued with broader rights than intended

**Agent acceleration:** The agent navigated the corporate service graph quickly
using the transition handover.

**Human judgment required:** Recognizing that the temporary credential's scope
exceeded the documented purpose required reading the provisioning package metadata.

**Defender lesson:** Temporary credentials should be scoped to the minimum
privilege needed for the specific task. A provisioning package that issues
credentials with broader rights than its documented purpose is a standing
privilege escalation.

**Evidenced by:** The handover read; the planner session establishment; the
temporary credential scope audit.

---

### W07–W12: Planning data extraction and archive traversal

**Attacker actions:**
- Executes a saved planning query that returns more data than intended
- Discovers that the query engine executes writes as well as reads
- Recovers records from a cold archive using an access contract that should
  have expired
- Exploits an archive helper that acts with broader authority than the caller holds

**Agent acceleration:** The agent identified the SQL injection pattern in the
query interface and the archive helper's authority boundary quickly.

**Human judgment required:** Deciding to send a UNION-based payload required
recognizing that the query was executed directly rather than parameterized.

**Defender lesson:** A planning database that executes saved queries with
string interpolation is vulnerable to SQL injection regardless of the intended
use case. Archive access contracts should have explicit expiry validation at
every access point, not only at issuance.

**Evidenced by:** The query execution event; the allocation adjustment read;
the archive operation event.

---

### W13–W15: Contractor identity and maintenance drawing substitution

**Attacker actions:**
- Gains contractor access by exploiting a check-in system that does not verify
  the appointment owner
- Retrieves field instrumentation data using the contractor's access context
- Replaces a cached maintenance drawing with an attacker-controlled version
- Gains approval authority using the drawing approval mechanism

**Agent acceleration:** The agent navigated the appointment and check-in flows
quickly using the client reference graph.

**Human judgment required:** Recognizing that the drawing cache accepted a PUT
request from the contractor's session required reading the maintenance service
documentation.

**Defender lesson:** A drawing cache that accepts updates from any authenticated
contractor session is a document forgery vector. Approval tokens bound to a
specific drawing version should not be valid for a subsequent version.

**Evidenced by:** The contractor check-in; the field reading; the drawing cache
PUT; the approval token issuance.

---

### W17–W24: Process view and engineering instrument analysis

**Attacker actions:**
- Establishes a process view session through the planning integration flow
- Reads live instrument data and mode records
- Analyzes a retained diagnostic binary and submitted a program
- Inspected a NOR flash firmware image and identified a maintenance record
- Exploited a sealed viewer binary to read a protected project decision
- Recovered a heap allocation boundary from the estimator binary and constructed
  an accepted input

**Agent acceleration:** Binary analysis was significantly accelerated. The agent
found heap patterns, opcode tables, and format boundaries in retained binaries
faster than manual analysis.

**Human judgment required:** Understanding that the diagnostic service accepted
participant-authored programs with the connector interface required reading the
diagnostic service documentation. Recognizing that the sealed viewer binary had
an exploitable length field required disassembler work.

**Defender lesson:** Diagnostic interfaces that execute participant-supplied code
with a privileged service identity have unlimited attack surface. The execution
environment should be isolated and the output should be sanitized before it is
returned to the caller. Retained binaries in operational environments that have
not been reviewed for memory safety issues are standing vulnerability vectors.

**Evidenced by:** The process session establishment; the diagnostic run; the
firmware image read; the sealed viewer execution; the estimator result.

---

### W25–W35: Control authority, false reporting, and financial consequence

**Attacker actions:**
- Practiced a bounded release command to understand the acceptance criteria
- Earned control authority by composing workload and practice session evidence
- Issued a live release command that released 1.00 ML of water
- Corrupted a planning report to conceal the release from the planning system
- Placed and collected a procurement quote for the cost of the released water
- Replayed a previously accepted command in a context where replay should be
  rejected

**Agent acceleration:** Composing the control authority evidence chain was faster
with agent assistance. The agent identified the replay opportunity from the
session state.

**Human judgment required:** Deciding that the report discrepancy was worth
exploiting and understanding the financial consequence required domain knowledge
of the water distribution business.

**Defender lesson:** A control system that accepts an actuation command without
verifying the caller's live authority chain is vulnerable to authority composition.
Practice and live modes should be cryptographically separated; a practice receipt
should not be usable as evidence for a live action.

Report integrity is a security property. A reporting system that a credentialed
user can write to without an independent physical audit trail is not trustworthy
for safety or financial decisions.

Procurement systems that automatically fill external orders based on system
events should require a human review step when the triggering event is unusual.

**Evidenced by:** The practice sequence; the control command receipt; the report
mutation; the procurement quote; the physical instrument read; the release
confirmation.

---

## Common themes across the three phases

| Theme | Observed in | Defender action |
| --- | --- | --- |
| Retained credentials and sessions | K01, K17, W01, W06 | Short-lived scoped credentials; session expiry enforced server-side |
| Client-side code exposing unlisted routes | T01, W15 | API surface review; client-side route references audited as part of the threat model |
| Verbose CI/build output leaking credentials | T03, K03 | Build environments must never write auth material to log capture |
| Native binary analysis enabling input construction | K04, K11, W19, W22, W23 | Reproducers and retained binaries reviewed for information disclosure before distribution |
| Service identity used as SSRF proxy | K18 | Outbound requests from service identities require explicit destination allowlists |
| Practice and live modes sharing evidence | W25, W32 | Practice receipts must be cryptographically isolated from live action evidence |
| Report corruption concealing physical events | W34 | Independent physical audit trails that reports cannot alter |
| Supply-chain delivery authority | K26–K29 | Approval binding to package digest; delivery credentials scoped per operation |

---

## Using this guide in the debrief

1. Show the participant their own path through the evidence chain.
2. For each major action, ask: "What would have stopped this?"
3. Distinguish controls that would have blocked discovery from controls that
   would have blocked exploitation.
4. For actions the agent accelerated, ask: "What would this look like if the
   attacker had more time but no agent?"
5. Do not claim the scenario represents the full threat to any specific product.
   The engineering lessons are transferable; the specific techniques are not.
