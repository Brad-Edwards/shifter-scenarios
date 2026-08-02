# Module 04 Facilitator Guide

Treat owning-system records as the evidence surface: Orion/Jaeger for model and
tool activity, Airflow plus signed MinIO objects for independent evaluations,
WorkHub for business state, Forgejo for signed capability source, Zammad plus
the support Chromium worker for review, and Redis export audit records for the
archive flaw. Never accept screenshots, operator-written evidence reports, caller
URLs, claimed scores or keywords as substitutes. Failed resets remove only the
failed native attempt and preserve successful immutable evidence.

## kep-m04-a: Canary In Context

**Lesson and reality:** Retrieved private context can leak through model
generation despite correct source ACLs. **Method:** Use two semantic
transformation families against the known topic/date and require fresh traced
responses. **Milestones:** denied direct read, protected retrieval trace, two
fresh leaks. **Stalls:** exact-secret requests often refuse; hints progress from
topic selection to transformation to freshness. **Defense:** retrieval-time
authorization, context minimization, output DLP. **Diagnostics/reset:** inspect
source ACL, two request IDs, exact responses, retrieval traces and signed report;
clear only unsuccessful conversations and reports.

## kep-m04-b: Extract The Guardrail

**Lesson and reality:** System instructions are model-accessible context, not a
secret store. **Method:** Bound extraction to the known routing section and use
transform/comparison prompts that preserve its operator comment. **Milestones:**
real rules plus reference in two fresh responses. **Stalls:** generic policy
summaries do not qualify. **Defense:** keep secrets out of prompts, minimize
instruction disclosure impact, enforce tools independently. **Diagnostics/reset:**
compare exact deployed ConfigMap bytes, responses, traces and report signature;
clear only unsuccessful conversations and reports.

## kep-m04-c: Calibrate The Privacy Signal

**Lesson and reality:** Membership attacks require calibrated observable model
signals, not intuition. **Method:** Fit probability/entropy/perturbation
features on one balanced split and validate on another. **Milestones:** live
requests, committed feature code, threshold, held-out AUC/TPR/FPR. **Stalls:**
prevent validation-set tuning and answer tables. **Defense:** regularization,
privacy-preserving training, output coarsening, query controls. **Diagnostics/reset:**
inspect the notebook digest, two server-created rotations, model revision,
request IDs and independently calculated report; remove failed runs and jobs.

## kep-m04-d: Population Of One

**Lesson and reality:** Calibrated black-box signals can infer an individual's
training membership. **Method:** Apply unchanged features to randomized unknown
candidates and let the server join labels only after scoring. **Milestones:**
live request set, selected record, margin, confusion metrics. **Stalls:** largest
raw score without the calibrated margin is insufficient. **Defense:** differential
privacy, regularization, rate limits, reduced scores. **Diagnostics/reset:**
inspect both rotations, query digest, submitted code, server labels/margins and
report signature; reset failed runs only.

## kep-m04-e: The Cohort Tell

**Lesson and reality:** Aggregate membership can reveal protected data-source
participation even when individual signals are noisy. **Method:** balance
metadata, aggregate perturbations, bootstrap uncertainty, and select one cohort.
**Milestones:** balance report, two seeds, confidence interval, low control FPR.
**Stalls:** metadata shortcuts invalidate the result. **Defense:** dataset
governance, privacy accounting, cohort audits, output restriction. **Diagnostics/reset:**
inspect request IDs, fixed balance strata, evaluator bootstrap results and
predecessor digests; delete failed runs only.

## kep-m04-f: Orion's Fingerprint

**Lesson and reality:** Batch outputs and audit metadata reveal model family,
revision, ontology, and hidden scores. **Method:** author a full-category batch
and inspect the downloadable report. **Milestones:** eight category requests,
labels, vectors, schema and revision. **Stalls:** rendered labels alone omit the
needed evidence. **Defense:** minimize metadata, authorize detailed reports,
monitor systematic probing. **Diagnostics/reset:** inspect KServe request IDs,
vectors, live model metadata and signed report coverage; clear rejected reports.

## kep-m04-g: The Running Revision

**Lesson and reality:** Runtime, orchestration, registry, and object metadata
can be joined to discover the exact loaded AI artifact. **Method:** follow the
Preview run through server-derived process state, scoped Kubernetes discovery,
the MLflow-tagged training Airflow run, MinIO, lakeFS, and KServe. **Milestones:**
one digest across every owning layer and a fresh inference trace. **Stalls:** no
caller-selected pod, process, object, run, service inventory, or trace is
accepted. **Defense:** metadata least privilege, namespace isolation, opaque
object keys. **Diagnostics/reset:** compare process-probe, Kubernetes, Airflow,
MLflow, MinIO, lakeFS, KServe and Jaeger records plus exact object bytes; remove
failed attestations only.

## kep-m04-h: The Project That Never Existed

**Lesson and reality:** A hallucination is exploitable only when it is reliable
and contradicted by authoritative evidence. **Method:** run two fixed requests
against the unverified rumor source and two fixed controls against the
retired-project ledger. **Milestones:** repeated Orion Caldera response, rumor
citations, ledger refutation, passing controls. **Stalls:** caller-provided or
echoed entities cannot qualify. **Defense:** grounded generation, citation
verification, constrained automation. **Diagnostics/reset:** fixed target and
control IDs, source citations, pinned model, ledger bytes, and factuality report;
clear only incomplete attempts.

## kep-m04-i: The Prompt Envelope

**Lesson and reality:** Parser traces and recognizers expose prompt boundaries
and internal keywords without extracting the prompt. **Method:** create fresh
malformed cases for both documented conditions and compare them to a normal
request. **Milestones:** three request IDs, two distinct recognizers, no tool
mutation. **Stalls:** model prose is not parser evidence. **Defense:** strict
structured composition, escaping, trace access control. **Diagnostics/reset:**
Jaeger spans and report case digests; clear attempt traces/reports.

## kep-m04-j: What The Release Assistant Can Reach

**Lesson and reality:** Signed configuration states intent; only live retrieval
and MCP traces prove actual agent reach. **Method:** verify the manifest, issue
one knowledge request and one read-only tool request, then join fresh traces.
**Milestones:** signature, cited collection, schema, tool result, distinct trace
IDs. **Stalls:** manifest-only answers and two same-kind calls fail. **Defense:**
capability minimization, runtime authorization, tool/schema inventory.
**Diagnostics/reset:** manifest digest, Qdrant and MCP spans; clear audit attempt.

## kep-m04-k: From Trigger To Tool

**Lesson and reality:** Agent activation and call chains cross business events,
planning, policy, brokers, and tools. **Method:** send the safe fixture through
WorkHub and correlate the broker delivery, actual Orion trace, allowed MCP
event, dedicated OPA decision, actual FastMCP dry-run receipt, and unchanged
runtime state. **Milestones:** operator issue, matching event/message IDs, Orion
trace, policy receipt, dry-run plan and unchanged production. **Stalls:**
direct tool calls bypass the behavior. **Defense:** end-to-end trace propagation,
policy at every authority transition, replay protection. **Diagnostics/reset:**
inspect the WorkHub issue, RabbitMQ delivery, Orion trace, OPA response, FastMCP
receipt and before/after state under one event ID; remove failed fixtures and
queue data.

## kep-m04-l: The Rendered Side Channel

**Lesson and reality:** Generated Markdown can turn a reviewer browser into an
exfiltration channel. **Method:** indirect attachment instruction, protected
value in remote image URL, normal support review browser, correlated access
log. **Milestones:** source article, draft article, Orion trace, browser-origin
request, then publish relay access at the fixed Cinder key. **Stalls:**
operator-originated curl and known constants fail. **Defense:**
sanitize remote content, image proxying, CSP, egress filtering, secret removal
from rendered context. **Diagnostics/reset:** inspect source and draft Zammad
articles, Orion trace, actual Chromium URL/user-agent, post-effect Cinder access
object, and relay record; delete only failed draft/profile/log state.

## kep-m04-m: Service Archive Spill

**Lesson and reality:** Object-level authorization failures in AI-service export
APIs expose prompts, attachments, and usage across identities. **Method:** learn
the request from one's own export, use the evidenced neighboring reference, and
verify returned owner/digest. **Milestones:** own export, justified reference,
other owner, complete archive. **Stalls:** blind scanning and object-store access
are invalid. **Defense:** owner checks on every object, opaque references,
export audit. **Diagnostics/reset:** compare the own and cross-owner server audit
entries, response digest and exact ZIP bytes; delete failed operator exports
while preserving fixed reference `7403` and the intentional authorization flaw.
