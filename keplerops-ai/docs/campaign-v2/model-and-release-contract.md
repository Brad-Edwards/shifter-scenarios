# Model And Release Contract

## Model Families

Every operation targets one of the families below or explicitly has no model
target. Operation prose may not use the generic word “Orion” to switch model,
runtime, or input type mid-chain.

| Family ID | Product role | Frozen implementation contract | Runtime/compute | Artifact set |
|---|---|---|---|---|
| `release-risk` | Eight-class release, intake, entitlement, advisory and support-risk classification | Small PyTorch Transformer encoder trained on a committed synthetic KeplerOps corpus; committed SentencePiece tokenizer; labels and preprocessing schema versioned with data | ONNX Runtime CPU for Preview/production; PyTorch GPU/CPU jobs for training and attack research | tokenizer, label map, preprocessing, architecture, state dict/ONNX, model card, train/eval manifests |
| `assistant` | Release/research/support assistant with RAG, memory and MCP tools | Qwen2.5-7B-Instruct (Apache-2.0) or a mechanically compatible admitted open-weight revision pinned by exact model-card and weight digest before build; no silent provider substitution | vLLM through per-range LiteLLM; shared immutable inference allowed under the isolation contract | weight/tokenizer revision, prompt sections, retrieval/tool/memory configuration, decoding profile |
| `vision-prototype` | 64-by-64 protected research classifier used for inversion/physical research | Small PyTorch ResNet-style classifier trained on committed synthetic 64x64 images with fixed classes and confidence-vector API | ONNX Runtime CPU for inference; PyTorch/ART job for inversion | preprocessing, class map, architecture, weights, protected images, calibration report |
| `physical-device` | Real consumer AI-enabled device/sensor on labgrid bench | Exact device firmware/model is recorded per bench and validated for the assigned physical operations | Actual device hardware | firmware/model identity, calibration, live media and actuator telemetry |
| `attacker-glm` | Cinder research, code and content assistance | Event GLM 5.2 endpoint, exact provider/model revision recorded at candidate time | Shared event inference pool | no KeplerOps prompt, data, memory, tool or flag state |

The clean build first trains and releases the two small KeplerOps models from
committed source/data and loads the admitted Assistant revision. The candidate
records exact digests; thresholds are calibrated only against those digests.

## Operation Family Allocation

- **Release Risk:** `kep-m04-f`, `kep-m06-a`, `kep-m06-c`, `kep-m06-d`,
  `kep-m06-e`, `kep-m06-f`, `kep-m07-a` through `kep-m07-h`, `kep-m08-a`
  through `kep-m08-g`, `kep-m09-b` through `kep-m09-g`, `kep-m10-a`,
  `kep-m10-b`, `kep-m10-d` through `kep-m10-i`, `kep-m10-k`, `kep-m10-l`,
  `kep-m10-n`, `kep-m10-o`, and `kep-m10-p`.
- **Assistant:** `kep-m01-a` through `kep-m01-f`, `kep-m02-a` through
  `kep-m02-d`, `kep-m03-d`, `kep-m03-e`, `kep-m03-j`, `kep-m03-k`,
  `kep-m03-g`, `kep-m03-h`, `kep-m03-i`, `kep-m04-a`, `kep-m04-b`,
  `kep-m04-h` through `kep-m04-m`, `kep-m05-a` through `kep-m05-q`,
  `kep-m06-b`, `kep-m06-s`, `kep-m10-e`, `kep-m10-j`, `kep-m10-m`, and
  `kep-m10-q`.
- **Vision Prototype:** `kep-m08-h`.
- **Physical Device:** `kep-m08-i`, `kep-m06-m`, and physical validation in
  `kep-m06-r` where the selected white-box candidate targets that device.
- **Artifact/supply-chain operations with the exact family declared by their
  participant artifact:** `kep-m01-g`, `kep-m01-h`, `kep-m02-e`, `kep-m02-f`,
  `kep-m03-a` through `kep-m03-c`, `kep-m03-f`, `kep-m07-i`, and `kep-m09-h`
  through `kep-m09-l`. The operation record and release manifest state whether
  that artifact carries Release Risk, Assistant, or a bounded review fixture.
- **No victim model target:** reconnaissance, general Cinder infrastructure,
  identity, service mapping, ordinary access, exact-byte collection and
  transfer operations not listed above. Those records still name any model
  artifact they observe.

Implementation adds a machine-readable `model_family` field to every operation
record and mechanically checks that each ID belongs to exactly one allocation.

## Release State Schema

Every Release Risk candidate and production revision has one immutable lineage
record with:

| Stage | Required identity |
|---|---|
| Source | Forgejo repository, commit and tree digests |
| Data | lakeFS/DVC repository, commit, manifest, split and label-schema digests |
| Training | Airflow DAG/run, code image, parameters, seed, runtime and hardware class |
| Model | MLflow run/version plus native weights, ONNX, tokenizer and model-card digests |
| Serving image | Harbor repository and immutable image/config/SBOM digests |
| Evaluation | visible/hidden suite revisions, input-set digests, metrics, controls and signed report |
| Approval | actor, policy revision, immutable subject fields and decision ID |
| Signature | signer identity, exact model/image digests, in-toto statement and transparency inclusion |
| Deployment | Forgejo GitOps commit, Argo application/revision and OPA admission decision |
| Runtime | KServe revision, pod image, loaded model/tokenizer/config digests and health/control traces |

`release_id` is the SHA-256 of the canonical schema above. Mutable names,
aliases, tags and compatibility labels are recorded as observations but never
replace immutable identity. The intentional campaign weaknesses in
`kep-m09-c`, `kep-m09-d` and `kep-m09-e` each violate one documented join while
leaving the immutable forensic record available.

## Distillation Contract

`kep-m08-a` through `kep-m08-f` is one real extraction chain against
`release-risk`:

1. participant-selected inputs query the live teacher API and store returned
   class probabilities/labels with request IDs;
2. the participant versions a balanced corpus and clean local validation set;
3. a real first student trains from those teacher labels and is loaded in a new
   process;
4. published error slices drive required active-learning query selection and a
   second real training run;
5. a disjoint server-held set measures aggregate, private-class and worst-slice
   fidelity for the exact second-student digest; and
6. a Cinder egress-denied job loads the complete exported student package and
   reproduces teacher capability on fresh participant-supplied cases.

The first student is intentionally calibrated to pass the broad baseline but
leave recoverable slice errors. This prevents model lottery while keeping the
second round meaningful. Query records, corpus, training code, weights and
offline execution are participant-owned; a prebuilt student or uploaded metrics
cannot pass.

## Release Continuity Gates

- Every operation report names `model_family`, input schema, model/runtime
  digest, preprocessing digest and compute profile.
- A Release Risk artifact cannot be evaluated or deployed as Assistant, and a
  prompt/agent operation cannot claim a classifier artifact as its victim.
- Production impact operations name the exact release ID and causal model
  decision. Generic business API abuse without the model contribution fails.
- Shared inference may serve Assistant weights, but range-owned prompt,
  retrieval, memory and tools remain per range.
- Availability and cost operations consume only a per-range runtime quota, not
  the shared attacker/victim pool.
- Candidate QA reconstructs the entire source-to-runtime record and checks every
  digest independently before behavior tests begin.
