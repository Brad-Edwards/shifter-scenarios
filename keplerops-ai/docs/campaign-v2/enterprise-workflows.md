# Enterprise Workflow Contracts

## Purpose

These workflows are the connective tissue of the campaign. The clean path must
work before challenge content is added. Weaknesses alter ordinary state; they
do not replace the workflow with a challenge endpoint.

## 1. Public Research And Client Release

**Clean path:** Forgejo source and CI produce a signed Android client, SBOM,
APK, release notes, model card, paper, preprint, and release manifest. The
public Research and Engineering pages link the normal artifacts.

**Participant path:** Chromium, public search, F-Droid metadata, APK tools, Git,
and SBOM tooling reveal reusable model, dependency, endpoint, people, and
release facts.

**Operations:** `kep-m06-g`, `kep-m06-h`, `kep-m06-i`, `kep-m06-j`,
`kep-m01-i`.

**Baseline proof:** A clean client build matches source, SBOM, APK digest, API
origin, model card, and release manifest.

## 2. Mail, Partner Intake, And Review Rooms

**Clean path:** An external sender reaches Stalwart; Zammad creates a case;
Tika/Tesseract extracts attachments; Airflow indexes permitted content in
Qdrant; Orion triages it; an accepted case causes Keycloak invitation and a
Nextcloud room. Employee recipients read and reply through real mail state.

**Participant path:** Participants compose and send mail, conduct a thread,
attach generated media, upload documents, follow status, authenticate with an
invitation, and use only the resulting room/project rights.

**Introduced weaknesses:** targetable recipient policy, deepfake-assisted trust,
prompt infiltration through uploaded documents, false nested RAG records, and
bounded export authorization failure.

**Operations:** `kep-m02-h` through `kep-m02-j`, `kep-m02-c`, `kep-m02-d`,
`kep-m04-m`, `kep-m10-o`.

**Baseline proof:** A benign message with attachment is delivered, replied to,
triaged, indexed, cited, invited, opened, and audited end to end.

## 3. Visible Artifact And Package Review

**Clean path:** A participant or partner submits a Forgejo URL, package,
container, model, or document. RabbitMQ queues it. The reviewer browser opens
the request, the local coding agent summarizes package documentation, and the
disposable domain-joined workbench installs or loads exact submitted bytes.
Normal results return to WorkHub within the published SLA.

**Participant path:** Participants create useful artifacts, publish them to
ordinary registries, submit credible review context, and observe real victim
browser, agent, package-manager, scanner, loader, and callback behavior.

**Introduced weaknesses:** vulnerable MCP documentation tool, dependency
resolution, unsafe model formats, scanner bypass, sandbox detection, and
fail-open corrupt-artifact review.

**Operations:** `kep-m01-g`, `kep-m01-h`, `kep-m02-k` through `kep-m02-m`,
`kep-m02-e`, `kep-m02-f`, `kep-m09-i`, `kep-m09-k`.

**Baseline proof:** Benign repository, package, model, and document submissions
all complete through the same visible queue; patched negative controls reject
the exploit classes.

## 4. WorkHub Release Assistant

**Clean path:** WorkHub issues and Nextcloud/Forgejo documents enter approved
Qdrant collections. LangGraph builds a prompt, retrieves sources, calls the
pinned Orion Assistant model, and may invoke allow-listed MCP tools through OPA.
Responses, citations, memories, handoffs, tool calls, and workflow IDs are
visible through ordinary application and trace views.

**Participant path:** Participants compare baselines, create or change the
actual messages/documents/tool data/memory/configuration, trigger fresh work,
and inspect downstream business state.

**Introduced weaknesses:** direct, indirect, triggered, and self-replicating
instructions; trusted-output manipulation; poisoned retrieval/tool data;
memory/thread poisoning; history manipulation; tool/config modification; and
delegated-authority abuse.

**Operations:** `kep-m01-a` through `kep-m01-f`, `kep-m02-a`, `kep-m02-b`,
`kep-m03-e`, `kep-m03-j`, `kep-m03-k`, `kep-m05-a` through `kep-m05-e`,
`kep-m05-m`.

**Baseline proof:** A normal release brief retrieves authoritative sources,
cites them, calls only permitted read tools, stores user memory, creates a
handoff, and cannot approve or transfer protected data for the participant.

## 5. Orion Discovery And Credential Paths

**Clean path:** WorkHub, JupyterHub, Airflow, MLflow, MinIO, Kubernetes, agent
traces, and configuration expose different scoped views of one real AI
lifecycle. Identity and object ACLs limit every view.

**Participant path:** Participants correlate ordinary references, retrieve
stale/overexposed artifacts, derive no-list object keys, inspect process and
service state, and use recovered authentication only through normal clients.

**Introduced weaknesses:** stale indexed credentials, rendered agent token,
stolen session cookie, notebook residue, verbose tool credential leakage, and
the pinned MLflow arbitrary-file-write chain.

**Operations:** `kep-m03-g` through `kep-m03-i`, `kep-m04-f` through
`kep-m04-k`, `kep-m05-f` through `kep-m05-l`, `kep-m08-k`.

**Baseline proof:** Clean roles can discover only their named systems and
artifacts; every recovered credential has a valid bounded scope and adjacent
denials.

## 6. Data, Training, And Evaluation

**Clean path:** Label Studio annotation revisions export to a versioned
lakeFS/DVC snapshot in MinIO. Airflow starts a pinned PyTorch/Transformers/PEFT
job. MLflow records source, data, base, prompt, configuration, weights, metrics,
and output digests. Inspect AI/pytest and Great Expectations evaluate exact
artifacts and datasets.

**Participant path:** Participants change real labels/data/config/code, run real
training, load resulting weights, and compare target, control, utility, and
lineage evidence.

**Introduced weaknesses:** contributor label poisoning, trusted-upstream
takeover, holdout corruption, backdoor training, graph modification, and
embedded code.

**Operations:** `kep-m07-a` through `kep-m07-i`, plus `kep-m10-p`.

**Baseline proof:** A clean training run is reproducible from immutable inputs;
the trained artifact loads in a new process; clean evaluation passes; snapshots
restore without deleting audit history.

## 7. Teacher Query, Privacy, Distillation, And Inversion

**Clean path:** Label Studio and Preview expose bounded Orion inferences;
privacy-audit jobs run submitted notebooks against balanced server-held labels;
Cinder's training/evaluation queues load participant artifacts; the vision
research project returns fixed confidence vectors.

**Participant path:** Participants issue real queries, version a corpus, train
student weights, improve weak slices, submit immutable digests, run offline,
train a distinct artifact-derived proxy, infer membership, and reconstruct a
vision prototype.

**Introduced weaknesses:** model/API information exposure and deliberately
overfit or invertible research models calibrated to the published attack
contracts. No labels, student weights, reconstruction, or target answers are
pre-supplied.

**Operations:** `kep-m04-a` through `kep-m04-e`, `kep-m04-l`, `kep-m08-a`
through `kep-m08-h`.

**Baseline proof:** Jobs load participant-submitted code and artifacts, enforce
query/network/data boundaries, report reproducible metrics, and reject copied
labels, prebuilt weights, uploaded logs, or direct source access.

## 8. Original Model Access And Egress

**Clean path:** A signed MLflow/MinIO manifest names every original Orion model
member. Internal validation jobs can read and load it. A separate export job
creates compressed, encrypted, object-locked archives. MinIO replication moves
approved exports to a named destination.

**Participant path:** Participants earn the package ACL, collect every member
inside KeplerOps, validate it under egress denial, stage a real encrypted
archive, replicate actual bytes to Cinder, decrypt them, and run the original in
a separate egress-denied Cinder job.

**Introduced weaknesses:** overprivileged model access and participant-controlled
egress destination after host/service compromise.

**Operations:** `kep-m08-j`, `kep-m10-d`, `kep-m10-f`, `kep-m10-g`.

**Baseline proof:** A manifest cannot substitute for bytes; every member hash,
archive digest, recipient, replication object, decrypted member, and loaded
runtime digest must agree.

## 9. Release And Production

**Clean path:** A candidate passes the visible suite, is registered immutably in
MLflow and Harbor, receives lineage and approval decisions, is signed, enters a
signed GitOps manifest, and is reconciled by Argo CD into the KServe canary.
Runtime inventory binds model and image digests to all inference traces.

**Participant path:** Participants modify their own attack implementation,
register exact bytes, exploit mutable lineage/approval/model-image bindings,
request normal signatures, promote the exact signed candidate, establish a
baseline, and activate the behavior.

**Introduced weaknesses:** three independent underspecified trust joins; the
signer and Argo CD remain genuine and behave normally on the bad policy result.

**Operations:** `kep-m09-b`, `kep-m09-a`, `kep-m09-c` through `kep-m09-g`,
`kep-m10-a` through `kep-m10-c`, `kep-m10-e`.

**Baseline proof:** A clean candidate passes and deploys with one immutable
model/image chain; mismatched digests are denied until the participant creates
the intended compromised policy state.

## 10. Contained Business And Operational Impact

**Clean path:** Orion canary decisions may invoke bounded OPA-governed tools for
feature control, accounting, publication, advisories, support, feedback triage,
and retention. Every action reaches an actual OSS business system and is
reversible through ordinary records.

**Participant path:** Participants create distinct input/data/approval states,
trigger the real workflow, verify actual business effect, and inspect the
causal model-policy-tool-application trace.

**Introduced weaknesses:** learned model behavior for feature/financial impact;
publication approval subject mismatch; cohort-map poisoning; adversarial
support content; chaff; bounded denial/cost; and data-steward instruction abuse.

**Operations:** `kep-m10-h` through `kep-m10-q`.

**Baseline proof:** Clean controls produce correct accounting, publication,
cohort, support, feedback, retention, availability, and budget outcomes. A
model response without the separate business-system effect never qualifies.

## Cross-Workflow Causal Keys

All systems preserve normal identifiers that permit participant correlation:

- mail message/thread and attachment digest;
- ticket, room, document, extraction, chunk, collection and source IDs;
- repository commit, package version and OCI/model digest;
- user, service principal, session, token audience and job ID;
- dataset commit, MLflow run, model version and evaluation report ID;
- approval, OPA decision, signature, transparency and GitOps revision IDs;
- request, trace, span, model, image, tool call and business record IDs; and
- archive, replication, destination, offline-job and attestation IDs.

Flags may be attached to an ordinary record after the real state exists, but
they cannot become a replacement identifier or an out-of-band join service.
