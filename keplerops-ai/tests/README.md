# KeplerOps live rehearsal

`run-golden-rehearsal.sh` is the explicit, credentialed rehearsal entrypoint
for the non-degraded `gcp_full` model of record. It composes the canonical
build lifecycle and performs participant actions only through the external
Kasm HTTPS browser terminal. IAP, Terraform, and GCP APIs remain operator-only
provisioning, health, reset, observation, and teardown channels.

The runner requires the same GCP arguments as `build/launch.sh`. It also needs
Chrome, `certutil`, `uv`, and normal Google credentials with permission to
administer tenant resources in the supplied existing project. The participant source CIDR
must be explicitly restricted; world-open ingress is rejected.

```sh
tests/run-golden-rehearsal.sh \
  --project-id prod-ksqdkj \
  --range-instance kep-356-a1 \
  --participant operator \
  --participant-source-cidr 203.0.113.10/32 \
  --retain-until-phase-e
```

`--retain-until-phase-e` runs launch, health, participant actions, and reset but
does not invoke cleanup, even on failure or interruption. The local report keeps
teardown `BLOCKED` until Phase E destroys and verifies only the namespaced tenant.

Generated state and the local JSON report stay owner-only below
`build/.operator/<range>-<participant>/`, which is gitignored. The runner never
creates the committed report itself. After a real run, an operator reviews the
local value-sparse report and commits a rendered snapshot under `docs/`; raw
browser state, cloud identifiers, credentials, tokens, receipts, model data,
and command output must not be committed.

Module 01 implementation adds a second retained-range runner for module-01 reliability. It
enters only through the same Kasm participant surface, performs `kep-m01-a`
through `kep-m01-c` once in each of ten full reset generations, then runs 30
trials apiece for `kep-m01-d` through `kep-m01-f`. Deterministic paths require
10/10; model-sensitive paths require at least 27/30 each. The local report keeps
only counts and 95% Wilson intervals. Campaign retry hardening makes the campaign resilient
to operator-session interruptions: an atomic owner-only checkpoint retains only
completed semantic counts, is bound to the exact participant, range deployment,
and proof source, fails closed on any mismatch, and is removed after the final
report is written.

```sh
python3 tests/module_01_reliability.py \
  --project-id prod-ksqdkj \
  --range-instance kep-356-b1 \
  --participant operator \
  --participant-source-cidr 203.0.113.10/32 \
  --use-existing-range \
  --retain-until-phase-e
```

Module 01 expansion adds the focused Module 01 expansion runner. It enters through Kasm,
satisfies only the two declared receipt prerequisites, rejects one shortcut for
each of `kep-m01-g` through `kep-m01-j`, executes each new real-software path
once, and verifies four receipts. It then performs one canonical reset and
replays the package path with a fresh prerequisite and receipt. This is the
pre-playtest one-pass bar; it does not repeat the original six-item reliability
campaign.

```sh
uv run --no-project --with 'raes==2.0.0' --with 'pyyaml>=6,<7' \
  --with 'playwright>=1.55,<2' python tests/module_01_expansion_rehearsal.py \
  --project-id prod-ksqdkj \
  --range-instance kep-356-b1 \
  --participant operator \
  --participant-source-cidr 203.0.113.10/32 \
  --use-existing-range \
  --retain-until-phase-e
```

The sanitized passing result and reset-schema repair are recorded in
[`../docs/module-01-proof-report.md`](../docs/module-01-proof-report.md).

Module 02 implementation adds the corresponding module-02 reliability runner. It proves the
deterministic paired boundary over ten clean reset generations, then measures
the encoding, semantic, repeatability, transfer, and ensemble paths over 30
participant-surface trials each. The model-sensitive paths require at least
27/30 successes; the report stores only counts and Wilson intervals.

```sh
python3 tests/module_02_reliability.py \
  --project-id prod-ksqdkj \
  --range-instance kep-356-b1 \
  --participant operator \
  --participant-source-cidr 203.0.113.10/32 \
  --use-existing-range \
  --retain-until-phase-e
```

The passing manual walkthrough, reliability campaign, integrated rehearsal,
reset, and telemetry evidence is summarized without participant or cloud
identifiers in
[`../docs/module-02-proof-report.md`](../docs/module-02-proof-report.md).

Module 02 expansion adds a focused pre-playtest runner for the three Module 02 Slice A
supply-chain paths. It enters only through Kasm, executes one signed Airflow
dependency consumption, one real WorkHub-to-MLflow model dependency change,
and one contained Chromium web-delivery effect, verifies all three receipts,
and exercises one representative shortcut rejection per path. It then resets
only the six-node supply dependency closure and replays the deterministic web
path once. It does not rerun the original Module 02 reliability campaign.

```sh
uv run --no-project --with 'raes==2.0.0' --with 'pyyaml>=6,<7' \
  --with 'playwright>=1.55,<2' python tests/module_02_supply_rehearsal.py \
  --project-id prod-ksqdkj \
  --range-instance kep-455-r1 \
  --participant operator \
  --participant-source-cidr 203.0.113.10/32 \
  --use-existing-range \
  --retain-until-phase-e
```

The same issue's Slice B runner covers only `kep-m02-h` and `kep-m02-m`.
It publishes the participant wheel through real Gitea PyPI, proves one pinned
pip resolution and one same-digest analysis/worker delta, checks digest and
unknown-dependency negatives, verifies both receipts, and performs one
four-owner scoped reset plus replay. It does not call the reliability runner.

```sh
uv run --no-project --with 'raes==2.0.0' --with 'pyyaml>=6,<7' \
  --with 'playwright>=1.55,<2' python tests/module_02_package_rehearsal.py \
  --project-id prod-ksqdkj \
  --range-instance kep-455-r1 \
  --participant operator \
  --participant-source-cidr 203.0.113.10/32 \
  --use-existing-range \
  --retain-until-phase-e
```

The final Module 02 expansion runner covers only `kep-m02-l`. It rejects a fabricated
campaign, then creates real Qwen text and an OpenVINO FLUX image, delivers the
exact MIME message through Stalwart, observes the recipient-model disclosure,
checks the fresh Keycloak role, and verifies the receipt. It resets only the
six state owners and replays the path once; the stateless text-generation node
is not restarted and no historical reliability campaign is repeated.

```sh
uv run --no-project --with 'raes==2.0.0' --with 'pyyaml>=6,<7' \
  --with 'playwright>=1.55,<2' python tests/module_02_spearphish_rehearsal.py \
  --project-id prod-ksqdkj \
  --range-instance kep-455-r1 \
  --participant operator \
  --participant-source-cidr 203.0.113.10/32 \
  --use-existing-range \
  --retain-until-phase-e
```

Expansion rehearsal adds focused full-ATLAS expansion proof runners for the Module 03
through Module 10 expansion rows. The issue-62 template proof covers 132
participant-surface challenges and excludes only the two unimplemented hardware
rows: `kep-m06-m` and `kep-m08-i`. Modules 03 through 09 accept
`--prepared-module-reset` only after the module dependency closure has already
passed the SDL-rendered reset and range health gate. Canonical range reset is
destructive to retained range host state and now requires the explicit
`--allow-canonical-reset` flag. Use
`--exclude-challenge kep-m06-m` with the Module 06 runner and
`--exclude-challenge kep-m08-i` with the Module 08 runner only for this
participant-only issue-62 scope; without that exclusion, Module 08 deliberately
blocks if the retained range cannot provide the live browser camera/video-frame
evidence for `kep-m08-i`.

```sh
module=03
uv run --no-project --with 'raes==2.0.0' --with 'pyyaml>=6,<7' \
  --with 'playwright>=1.55,<2' python "tests/module_${module}_full_atlas_rehearsal.py" \
  --project-id prod-ksqdkj \
  --range-instance kep-455-r1 \
  --participant operator \
  --participant-source-cidr 203.0.113.10/32 \
  --use-existing-range \
  --retain-until-phase-e \
  --prepared-module-reset
```

Module 10 consumes prepared prerequisite evidence from the earlier module
passes and refuses to reset that state:

```sh
uv run --no-project --with 'raes==2.0.0' --with 'pyyaml>=6,<7' \
  --with 'playwright>=1.55,<2' python tests/module_10_full_atlas_rehearsal.py \
  --project-id prod-ksqdkj \
  --range-instance kep-455-r1 \
  --participant operator \
  --participant-source-cidr 203.0.113.10/32 \
  --use-existing-range \
  --retain-until-phase-e \
  --prepared-prerequisites
```

Module 03 implementation adds the pre-playtest module-03 runner. Its default path performs one
canonical range reset and health check before exercising all six context
poisoning receipts once through Kasm. When the dataset store and inference
gateway have already passed their SDL-rendered module reset and the full range
health check, `--prepared-module-reset` avoids a second all-service reset and
records `module-services-prepared` in the owner-only report.

```sh
python3 tests/module_03_rehearsal.py \
  --project-id prod-ksqdkj \
  --range-instance kep-356-b1 \
  --participant operator \
  --participant-source-cidr 203.0.113.10/32 \
  --use-existing-range \
  --retain-until-phase-e \
  --prepared-module-reset
```

The sanitized durable result from the passing live run is
[`../docs/module-03-proof-report.md`](../docs/module-03-proof-report.md).

The retained-range Module 03 reliability runner starts with one canonical
reset, measures `kep-m03-a` and `kep-m03-b` across ten clean module-state
samples, and then measures `kep-m03-c` through `kep-m03-f` over 30 live-model
trials each. Deterministic paths require 10/10 and model-sensitive paths require
at least 27/30. Between samples it quiesces, resets, and verifies only the
dataset-store/inference-gateway dependency closure that owns and recreates the
context baseline; unrelated services are not restarted. Its atomic owner-only
checkpoint and aggregate report are bound to the exact participant, range
deployment, runtime, rehearsal, and lifecycle sources.

```sh
python3 tests/module_03_reliability.py \
  --project-id prod-ksqdkj \
  --range-instance kep-356-b1 \
  --participant operator \
  --participant-source-cidr 203.0.113.10/32 \
  --use-existing-range \
  --retain-until-phase-e \
  --allow-canonical-reset
```

Module 04 implementation adds the pre-playtest module-04 runner. It performs one participant-
surface pass across the two live vLLM disclosure paths and three real
classifier membership paths, verifies all five receipts, and exercises
representative shortcut negatives. The `--prepared-module-reset` option is
valid only after the changed gateway, policy, proof, and dataset services have
passed their SDL-rendered reset and the full retained-range health check.

```sh
python3 tests/module_04_rehearsal.py \
  --project-id prod-ksqdkj \
  --range-instance kep-356-b1 \
  --participant operator \
  --participant-source-cidr 203.0.113.10/32 \
  --use-existing-range \
  --retain-until-phase-e \
  --prepared-module-reset
```

The sanitized durable result from the passing live run is
[`../docs/module-04-proof-report.md`](../docs/module-04-proof-report.md).

The module-04 reliability runner samples the three deterministic classifier
paths across ten clean module states and runs 30 participant-surface trials for
each live-model disclosure. Deterministic paths require 10/10 and model-
sensitive paths require at least 27/30. It reuses the verified dataset-store
and inference-gateway dependency closure between samples, retains an atomic
owner-only checkpoint, and writes only aggregate counts and Wilson intervals.
It neither requests receipts nor retains prompts, completions, labels, or
model data. Use `--prepared-module-reset` only when a canonical clean reset has
already passed and the runner should begin with a verified scoped reset.

```sh
python3 tests/module_04_reliability.py \
  --project-id prod-ksqdkj \
  --range-instance kep-356-b1 \
  --participant operator \
  --participant-source-cidr 203.0.113.10/32 \
  --use-existing-range \
  --retain-until-phase-e \
  --prepared-module-reset
```

Module 05 implementation adds the pre-playtest module-05 runner. It uses only the Kasm
participant surface to make the live model plant durable memory, proves later
retrieval across clean-session and thread boundaries, causes and verifies a
real supervised worker restart, then uses restart-surviving state to execute a
contained OPA-backed tool effect. It verifies all five receipts and exercises
representative direct-state, copied-prompt, pre-plant, pre-restart, and forged-
restart negatives.

```sh
python3 tests/module_05_rehearsal.py \
  --project-id prod-ksqdkj \
  --range-instance kep-356-b1 \
  --participant operator \
  --participant-source-cidr 203.0.113.10/32 \
  --use-existing-range \
  --retain-until-phase-e \
  --prepared-module-reset
```

`--prepared-module-reset` is valid only after the changed portal, gateway,
policy, dataset, and proof services have passed their SDL-rendered reset and
the full retained-range health check.

The sanitized durable result from the passing live run is
[`../docs/module-05-proof-report.md`](../docs/module-05-proof-report.md).

The module-05 reliability runner performs 30 participant-surface trials for
each model-sensitive path. A through C pair every counted activation with a
fresh live-model-authored durable plant. D and E run after a genuine supervised
worker restart, with E requiring the real OPA-authorized contained effect on
every successful trial. Each challenge requires at least 27/30. The runner
uses the verified dataset-store/inference-gateway state closure before and
after the campaign, writes only aggregate counts and Wilson intervals, and
finishes with a full retained-range health check. It does not request receipts
or retain prompts, completions, memory, markers, or tool payloads.

```sh
python3 tests/module_05_reliability.py \
  --project-id prod-ksqdkj \
  --range-instance kep-356-b1 \
  --participant operator \
  --participant-source-cidr 203.0.113.10/32 \
  --use-existing-range \
  --retain-until-phase-e \
  --prepared-module-reset
```

Module 06 implementation adds the pre-playtest module-06 runner. It stores real participant
artifacts, exercises manual and repeated boundary crossing, a server-budgeted
black-box search, disclosed-surrogate transfer, hidden semantic repeatability,
and the strict generative/classifier transfer gate. The server owns controls,
query budgets, revision schedules, semantic checks, and verdicts. The runner
verifies all six receipts and representative caller-asserted-verdict negatives
in five bounded Kasm terminal phases.

```sh
python3 tests/module_06_rehearsal.py \
  --project-id prod-ksqdkj \
  --range-instance kep-356-b1 \
  --participant operator \
  --participant-source-cidr 203.0.113.10/32 \
  --use-existing-range \
  --retain-until-phase-e \
  --prepared-module-reset
```

The module-06 reliability runner exercises all six real-model paths 30 times
each. It uses five clean six-trial batches so the server-owned black-box and
surrogate query budgets remain authoritative, checkpoints only aggregate
counts between batches, performs only the dataset-store/inference-gateway
scoped reset, and finishes with a full retained-range health check. It does not
request receipts or retain candidates, prompts, completions, probe bodies,
model decisions, artifact identifiers, or proof content.

```sh
python3 tests/module_06_reliability.py \
  --project-id prod-ksqdkj \
  --range-instance kep-356-b1 \
  --participant operator \
  --participant-source-cidr 203.0.113.10/32 \
  --use-existing-range \
  --retain-until-phase-e \
  --prepared-module-reset
```

The prepared reset option is valid only after the changed portal, gateway,
policy, dataset, and proof services pass their SDL-rendered reset and the full
retained-range health check.

The sanitized durable result from the passing live run is
[`../docs/module-06-proof-report.md`](../docs/module-06-proof-report.md).

Module 07 implementation adds the pre-playtest module-07 runner. It creates real versioned
training datasets, triggers participant-reachable Airflow jobs, trains the
pinned scikit-learn adapter, records MLflow/MinIO lineage, evaluates target,
clean, low-rate, hidden-trigger, and post-sanitization behavior, and verifies
all six independent receipts. Five bounded Kasm phases include representative
caller-digest, caller-metric, class-confusion, and pre-evidence negatives.

```sh
python3 tests/module_07_rehearsal.py \
  --project-id prod-ksqdkj \
  --range-instance kep-356-b1 \
  --participant operator \
  --participant-source-cidr 203.0.113.10/32 \
  --use-existing-range \
  --retain-until-phase-e \
  --prepared-module-reset
```

The prepared reset option is valid only after the dataset, Airflow, MLflow,
MinIO, gateway, policy, portal, and proof service state has been reset for the
new generation and the full retained-range health check passes.

The sanitized durable result from the passing live run is
[`../docs/module-07-proof-report.md`](../docs/module-07-proof-report.md).

Module 07 implementation's participant qualification completed seven clean samples for all
six deterministic paths. The resumable runner stores aggregate counts only,
does not request receipts, and uses a scoped closure containing the dataset,
Airflow, MLflow, MinIO, policy, portal, proof, gateway, and `model-host-01`.
The model host is required because clearing the artifact store also removes the
immutable teacher object that this SDL-declared owner must restore and verify.

```sh
python3 tests/module_07_reliability.py \
  --project-id prod-ksqdkj \
  --range-instance kep-356-b1 \
  --participant operator \
  --participant-source-cidr 203.0.113.10/32 \
  --use-existing-range \
  --retain-until-phase-e \
  --prepared-module-reset
```

Module 08 implementation adds the pre-playtest module-08 runner. It collects item-scoped
corpora from the live range-local teacher under server-enforced budgets,
triggers participant-reachable Airflow jobs, trains real
TF-IDF/logistic-regression proxies, records MLflow/MinIO lineage, evaluates
diagnostic and private live-teacher fidelity, and verifies all six independent
receipts. Five bounded Kasm phases include caller-label, caller-metric,
duplicate-query, private-probe, cross-item, and pre-evidence controls.

```sh
python3 tests/module_08_rehearsal.py \
  --project-id prod-ksqdkj \
  --range-instance kep-356-b1 \
  --participant operator \
  --participant-source-cidr 203.0.113.10/32 \
  --use-existing-range \
  --retain-until-phase-e \
  --prepared-module-reset
```

The prepared reset option is valid only after the dataset, Airflow, MLflow,
MinIO, gateway, policy, portal, and proof service state has been reset for the
new generation and the full retained-range health check passes.

The sanitized durable result from the passing live run is
[`../docs/module-08-proof-report.md`](../docs/module-08-proof-report.md).

Module 09 implementation adds the pre-playtest module-09 runner. It registers the exact
participant-trained Module 07 artifact as a real MLflow model, executes
disclosed and hidden behavior checks, verifies signed Keycloak approval
identities through the intentionally confused OPA rule, changes the production
alias, reloads the exact artifact, and verifies all seven receipts. The clean
passing run is recorded in
[`../docs/module-09-proof-report.md`](../docs/module-09-proof-report.md).

```sh
python3 tests/module_09_rehearsal.py \
  --project-id prod-ksqdkj \
  --range-instance kep-356-b1 \
  --participant operator \
  --participant-source-cidr 203.0.113.10/32 \
  --use-existing-range \
  --retain-until-phase-e \
  --prepared-module-reset
```

Module 10 implementation adds the module-10 runner. It deliberately uses
one prepared generation containing the participant-created Module 05, 06, 08,
and 09 prerequisite state. From Kasm it executes the exact promoted classifier,
creates the OPA-brokered contained effect, obtains scoped access to the full
3.42 GB teacher artifact, performs the internal MinIO-to-MinIO transfer, asks
the gateway to recompute the destination SHA-256, and verifies all seven
receipts. Run the prior module runners in dependency order with their prepared
reset option, then run:

```sh
python3 tests/module_10_rehearsal.py \
  --project-id prod-ksqdkj \
  --range-instance kep-356-b1 \
  --participant operator \
  --participant-source-cidr 203.0.113.10/32 \
  --use-existing-range \
  --retain-until-phase-e \
  --prepared-prerequisites
```

The passing bounded retained-range result is recorded in
[`../docs/module-10-proof-report.md`](../docs/module-10-proof-report.md). The
runner never resets away prepared prerequisites, and the result does not claim
the manual walkthrough or a reliability campaign.

The static suite runs without cloud credentials:

```sh
python3 -m unittest discover -s keplerops-ai/tests -p 'test_*.py'
```
