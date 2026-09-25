# SDL and design readiness review — 23 September 2026

This is the 23 September snapshot. For subsequent Training changes and current
validation limits, see the [25 September Training gate](training-readiness.md).
The SDL hash and counts below identify the earlier checked revision, not the
current worktree.

**Not ready for materialization.** The scenario has a checked allocation and
dependency model, substantial workplace assets, and a partially drafted technical
design. It does not yet have a complete native SDL description of playable
behavior. Passing the parser is not the same as finishing that design.

## Approved build-job decision

K09 must provide access that the participant can recognize and continue using.
The revised draft supplies ordinary Build Operations documents, a repeatable
command format, and a harmless status read proved by both the job and the
receiving service. Its tier allocation remains Easy/Easy/Medium/Medium.

The earlier request-only proposal always authenticated as the build worker and
could not use a newly obtained colleague identity. The scenario owner approved
ordinary command execution in an isolated, restricted build job. The updated
design accepts an executable and arguments, supports shells/scripts and installed
native clients, retains private files across runs, and permits explicit use of
separately earned client credentials. It does not pre-seed those identities or
grant CI administration, release approval, customer access, or general network
transit. Code inside the job can read its own worker credentials; those are
therefore scoped per service/run and revoked at exit, with origin and isolation
checks enforced outside participant-writable state.

This closes the execution-boundary decision, not the full identity branch.
K19/K20 still require their concrete enrollment, authentication, delegation,
client-tool, endpoint, and renewal designs. Later acceptance must follow the
real acquisition path and prove use of the resulting principal at the receiving
service. A successful abstract graph replay or a pre-supplied test credential
does not establish that solve. No new RAE semantic is claimed or introduced.

## Work still required

| Area | What is unfinished | Acceptance requirement |
| --- | --- | --- |
| Native SDL | 398 relationships use a local interpretation: 99 flows, 26 contexts, 7 relays, and 266 challenge-surface bindings. RAE accepts their metadata but does not supply the meaning of `cinder_kind`, modes, and workflow guards. | Replace that interpretation with appropriate native declarations and validate them upstream. Do not replace it with another private decoder. Stop for owner review if a necessary upstream semantic is genuinely absent. |
| Usable access | The graph records earned positions but does not establish the actual client, authentication, service operation, denial behavior, or continuity for every position. K09 exposes a concrete example of this gap. | For each of the 26 positions, specify how it is acquired, recognized, exercised, renewed or retained, and reset; distinguish it from the service identity it contacts. |
| Asset ownership | There are 264 challenge starting-record declarations, plus six shared record declarations. These mostly describe required records rather than supplying their contents. Seventeen multi-system cards still lack an explicit partition of their starting records. | Assign each required record to its real owner and audience; distinguish local discovery material, protected source records, job results, and independent proof. Preserve existing asset/challenge relationships. Do not copy a complete starting-material list to every involved service. |
| Technical completeness | All 16 tutorial cards and 34 KeplerOps cards have technical drafts. The other 70 KeplerOps cards and all 120 ARWC cards remain briefs. A shortest main route contains 35 cards, only three technically drafted. | Complete full-scenario interface and authority agreements in stage 1, then full technical designs in the user's tutorial, KeplerOps, and ARWC order. A brief or a five-section draft is not evidence of a working mechanism. |
| Discovery and continuity | A permission alone is not a useful next step. Corporate and OT arrival expose 43 and 56 possible unfinished cards in the abstract model. | Make a few useful leads apparent through obtainable in-world records, while retaining other choices. Verify a fresh reader can find addresses, understand responses, retry, and resume after a break. No solution-hint delivery or fourth-wall copy. |
| Difficulty | Allocations and declared route ceilings are checked; assisted discovery time and difficulty are unmeasured. | Preserve the approved distribution and separate achievements. Later fresh assisted solves must confirm difficulty, including cumulative investigation burden and source-aware transfer. Do not preserve a tier by making documentation obscure. |
| Reservoir behavior | The consequence must follow a real bounded process transition. Quantities, timing, permissible transitions, measurement, and cost still need a complete coherent design. | Obtain the specified water/controls review, define the model and independently observable results, and keep practice, live state, reporting manipulation, and financial effects separate. Completion must observe the result, not create its own evidence. |
| Isolation and recovery | Requirements exist, but live boundaries and reset behavior have not been demonstrated. | Specify ownership and reset for mutable jobs, credentials, records, process state, and retained evidence. Test denials and cross-participant isolation at each golden-range stage. |

The seventeen unpartitioned multi-system cards are K20.3, K26.3, K27.2, K29.3,
W17.4, W18.4, W21.2, W25.4, W29.2, W29.3, W30.1, W30.2, W33.1, W33.2, W33.3,
W33.4, and W34.3. The authored workplace collections are separate from those
required challenge records; large ambient-content counts do not fill missing
challenge mechanisms or ownership decisions.

## Corrections made during this review

- Recovery redeems a one-use transaction into a reusable authenticated session;
  it no longer consumes the session before the tutorial's next task.
- The reservoir completion joins process, independent measurement, and business
  consequence evidence. Its follow-up presentation cannot open the gates or
  manufacture the evidence needed to trigger itself.
- K09 has two authored, worker-owned documents with exact native file content,
  repeatable command execution, and independent destination proof. No completion
  event grants permissions. The approved execution boundary allows native
  clients to use separately earned identities; downstream mechanisms still need
  full design and acceptance tests.
- The experience and calibration plans now require in-world discovery instead
  of published solution hints, difficulty announcements inside the fiction, or
  score-triggered access. Inherited empty hint headings remain empty.
- The production order now follows the user's design-first, progressively
  hand-built golden-range sequence; isolated pre-design prototypes are not a
  substitute.

## Verification and its limits

The design/allocation checks pass. The challenge checker rejects 27 broken
graphs and seven invalid documents. The topology checker replays 1,209 minimal
closures and all 16 main route combinations, and rejects 26 broken topology or
event cases. Seventeen focused K09 tests check authored document bytes and
placement, the command example's syntax and argument expansion, real product
read paths, independent proof ownership, command/isolation requirements,
identity selection, the completed-review input prerequisite, unchanged
allocation, and absence of fourth-wall copy in those documents.
The argument-expansion test substitutes a printing curl stand-in; it makes no
network request and tests no service authentication or isolation.

The complete SDL also passes `raes-env-packs==6.1.0` author validation and
`raes==5.0.0` parsing, composition, semantic validation, instantiation, and
compilation using Python 3.14. The processor emits 3,453 realization requirements;
all 281 observation source bindings and eight workplace content bindings survive
compilation. This rerun used `validate_sdl.py --pack-check`; the full SDL mutation
suite was not rerun. The focused K09, design, challenge, and topology checks above
were rerun separately. `git diff --check` passes.

The final rerun includes the approved command job and completed-review reference
requirement. Its 97 SDL files have aggregate SHA-256
`f82a7aa0b4340eaa84806fa514b3b59f2cc706d41e961b8b4dd6534924934f4b`,
using the path/NUL/bytes/NUL method in the historical
[validation record](../sdl-validation.md). The SDL remained unchanged throughout
that run. No K09 relationship, workflow, assertion, objective inventory, or
difficulty allocation changed; the new requirements use the existing native
action/evidence contracts and literal file-content declarations.

These are static checks. They do not establish that later authentication works,
that the proposed flaws are exploitable, that isolation holds, or that the
experience achieves the intended difficulty. In particular, topology replay
still depends on the private relationship interpretation listed above. The
upstream validator/processor result must be read with that limitation, not used
to waive it. No service has been materialized or playtested for this review.

## Required order

Follow [the design and golden-range gates](calibration.md#1-design-and-golden-range-gates):
full-scenario correction and native SDL validation; full tutorial design;
hand-built tutorial golden range; full KeplerOps design and range extension;
full ARWC design and range extension; full integration testing and playtesting.
Test every stage, with integration tests and initial playtest observations at
the KeplerOps and ARWC extensions. The golden range supplies later bakes.
