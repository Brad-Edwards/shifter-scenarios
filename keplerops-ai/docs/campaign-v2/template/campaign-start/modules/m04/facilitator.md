# Module 04 Facilitator Guide

## kep-m04-a: Canary In Context

**Lesson and reality:** Retrieved private context can leak through model
generation despite correct source ACLs. **Method:** Use two semantic
transformation families against the known topic/date and require fresh traced
responses. **Milestones:** denied direct read, protected retrieval trace, two
fresh leaks. **Stalls:** exact-secret requests often refuse; hints progress from
topic selection to transformation to freshness. **Defense:** retrieval-time
authorization, context minimization, output DLP. **Diagnostics/reset:** inspect
source ACL, request IDs, retrieval source and response bytes; clear thread only.

## kep-m04-b: Extract The Guardrail

**Lesson and reality:** System instructions are model-accessible context, not a
secret store. **Method:** Bound extraction to the known routing section and use
transform/comparison prompts that preserve its operator comment. **Milestones:**
real rules plus reference in two fresh responses. **Stalls:** generic policy
summaries do not qualify. **Defense:** keep secrets out of prompts, minimize
instruction disclosure impact, enforce tools independently. **Diagnostics/reset:**
compare prompt revision, response and trace; clear conversations only.

## kep-m04-c: Calibrate The Privacy Signal

**Lesson and reality:** Membership attacks require calibrated observable model
signals, not intuition. **Method:** Fit probability/entropy/perturbation
features on one balanced split and validate on another. **Milestones:** live
requests, committed feature code, threshold, held-out AUC/TPR/FPR. **Stalls:**
prevent validation-set tuning and answer tables. **Defense:** regularization,
privacy-preserving training, output coarsening, query controls. **Diagnostics/reset:**
notebook digest, model revision, request IDs, independent report; remove failed run.

## kep-m04-d: Population Of One

**Lesson and reality:** Calibrated black-box signals can infer an individual's
training membership. **Method:** Apply unchanged features to randomized unknown
candidates and let the server join labels only after scoring. **Milestones:**
live request set, selected record, margin, confusion metrics. **Stalls:** largest
raw score without the calibrated margin is insufficient. **Defense:** differential
privacy, regularization, rate limits, reduced scores. **Diagnostics/reset:**
rotation seed, query digest, submitted code and signature; reset this run only.

## kep-m04-e: The Cohort Tell

**Lesson and reality:** Aggregate membership can reveal protected data-source
participation even when individual signals are noisy. **Method:** balance
metadata, aggregate perturbations, bootstrap uncertainty, and select one cohort.
**Milestones:** balance report, two seeds, confidence interval, low control FPR.
**Stalls:** metadata shortcuts invalidate the result. **Defense:** dataset
governance, privacy accounting, cohort audits, output restriction. **Diagnostics/reset:**
query IDs, balance strata, bootstrap reports; delete current run only.

## kep-m04-f: Orion's Fingerprint

**Lesson and reality:** Batch outputs and audit metadata reveal model family,
revision, ontology, and hidden scores. **Method:** author a full-category batch
and inspect the downloadable report. **Milestones:** eight category requests,
labels, vectors, schema and revision. **Stalls:** rendered labels alone omit the
needed evidence. **Defense:** minimize metadata, authorize detailed reports,
monitor systematic probing. **Diagnostics/reset:** Preview request IDs and
report coverage; clear rejected batches/traces.

## kep-m04-g: The Running Revision

**Lesson and reality:** Runtime, orchestration, registry, and object metadata
can be joined to discover the exact loaded AI artifact. **Method:** follow the
Preview run through process state, scoped Kubernetes discovery, Airflow,
MLflow, MinIO, and KServe. **Milestones:** one digest across every layer.
**Stalls:** no-list object access requires deriving the key; broad cluster
access is invalid. **Defense:** metadata least privilege, namespace isolation,
opaque object keys. **Diagnostics/reset:** compare each native record; recreate
project pod/session, never production runtime.

## kep-m04-h: The Project That Never Existed

**Lesson and reality:** A hallucination is exploitable only when it is reliable
and contradicted by authoritative evidence. **Method:** use two phrasings and
grounded controls around the retired-project ledger. **Milestones:** repeated
entity, failed citation, ledger refutation, passing controls. **Stalls:** one
surprising response is not enough. **Defense:** grounded generation, citation
verification, constrained automation. **Diagnostics/reset:** pinned model and
decoding, request set, factuality report; clear attempt/thread.

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
WorkHub and trace every correlated hop to a dry-run effect. **Milestones:**
event, planner, OPA, RabbitMQ, MCP IDs and unchanged production. **Stalls:**
direct tool calls bypass the behavior. **Defense:** end-to-end trace propagation,
policy at every authority transition, replay protection. **Diagnostics/reset:**
inspect each native system by root trace; remove fixture execution/memory.

## kep-m04-l: The Rendered Side Channel

**Lesson and reality:** Generated Markdown can turn a reviewer browser into an
exfiltration channel. **Method:** indirect attachment instruction, protected
value in remote image URL, normal support review browser, correlated access
log. **Milestones:** draft ID, Orion trace, notification job, browser-origin
request. **Stalls:** participant curl and known constants fail. **Defense:**
sanitize remote content, image proxying, CSP, egress filtering, secret removal
from rendered context. **Diagnostics/reset:** Chromium network log and source
address; clear draft/profile/log attempt.

## kep-m04-m: Service Archive Spill

**Lesson and reality:** Object-level authorization failures in AI-service export
APIs expose prompts, attachments, and usage across identities. **Method:** learn
the request from one's own export, use the evidenced neighboring reference, and
verify returned owner/digest. **Milestones:** own export, justified reference,
other owner, complete archive. **Stalls:** blind scanning and object-store access
are invalid. **Defense:** owner checks on every object, opaque references,
export audit. **Diagnostics/reset:** service access log and archive ownership;
delete participant exports and restore bounded ACL state.
