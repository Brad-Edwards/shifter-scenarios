# Scoring And Hint Design

## Objectives

Scoring should communicate effort and risk without distorting the campaign.
Participants should be able to choose branches, understand meaningful progress,
and recover from uncertainty without being told to invoke hidden challenge
machinery.

## Difficulty And Base Points

| Difficulty | Base Points | Expected Participant Work |
|---|---:|---|
| Accessible | 100 | One primary system or technique, direct discovery path, clear feedback, and no unexplained specialist prerequisite. |
| Intermediate | 200 | Two or more connected observations or tools, modest artifact construction, or a non-obvious but well-clued trust failure. |
| Advanced | 350 | Multi-system state, substantial analysis or artifact creation, careful preservation of bytes or lineage, or a technically demanding attack method. |
| Expert | 500 | Campaign convergence, independent exploit development, model training or extraction, difficult multi-stage reasoning, or exact cross-system artifact continuity. |

Difficulty is assigned from the participant work, not implementation
complexity. A technically elaborate backend does not justify more points when
the player only clicks one button.

## Scoring Rules

- Each of the 134 operations has one fixed base score.
- Required campaign-spine operations are visible from the start of their act.
- Branch operations unlock when the participant has the access or artifact
  needed to attempt them.
- Completion is idempotent and cannot award points twice.
- A parent ATLAS row and its subtechnique do not receive separate scores when
  one participant operation naturally performs both.
- No points are awarded for opening a page, reading static text, entering a
  challenge ID, or requesting a proof value.
- Compound operations earn points only after all material participant actions
  and effects have occurred.
- Optional expert operations may be worth more but cannot be required to reach
  basic campaign orientation or understand how to begin.

## Participant Descriptions

Each Shifter description is concise and mission-facing. It states:

1. the operational objective;
2. the target or business context the participant already knows;
3. the success condition in terms of observable company or attacker state; and
4. any explicit safety or scope constraint.

Descriptions do not reveal:

- exploit strings or exact prompts;
- hidden endpoint paths;
- database keys or proof fields;
- challenge IDs as application commands;
- credentials that must be earned;
- internal implementation names a real attacker could not know; or
- ATLAS labels as instructions.

## Progressive Hints

Every operation has three hints with distinct purposes.

### Hint 1: Orientation

Points the participant toward the correct company fact, owner, system, or
artifact. It answers "where should I investigate?" without identifying the
weakness.

### Hint 2: Mechanism

Names the security boundary or technical relationship to examine. It answers
"what behavior should I test?" without providing the final payload or command.

### Hint 3: Execution

Provides enough concrete syntax, workflow order, or artifact constraints for a
participant who understands the mechanism to execute it. It may include an
example using non-solution values but does not become a copy-paste flag request.

## Hint Penalties

The initial event uses no score penalty for hints. The objective is effective
playtesting and AI-security learning, not discouraging participants from using
the material required to understand an unfamiliar enterprise. Hint telemetry
may be recorded to identify unclear challenges, but it does not alter score.

## Completion Feedback

The participant retrieves a conventional `FLAG{<16-hex>}` value from the
in-world artifact, record, response, or changed state reached by the operation
and submits it to Shifter. Shifter confirms completion and score.

Flag locations follow the Polaris pattern: they are ordinary range content
embedded behind the access or effect the participant must achieve. Gitea,
Airflow, MLflow, MinIO, mail, model responses, generated reports, and other
enterprise tools remain normal applications. There is no proof broker or
additional participant proof utility.

When an operation is incomplete, company applications return authentic system
feedback and the flag-bearing state is not reachable or has not yet been
created. Shifter may clarify the participant-facing success condition but must
not expose the flag location beyond the progressive hints.
