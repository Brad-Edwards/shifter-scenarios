# Model And Release Contract

## Model Families

Every operation targets one of the families below or explicitly has no model
target. Operation prose may not use the generic word “Orion” to switch model,
runtime, or input type mid-chain.

| Family ID | Product role | Frozen implementation contract | Runtime/compute | Artifact set |
|---|---|---|---|---|
| `release-risk` | Eight-class release, intake, entitlement, advisory and support-risk classification | Small PyTorch Transformer encoder trained on a committed synthetic KeplerOps corpus; committed SentencePiece tokenizer; labels and preprocessing schema versioned with data | ONNX Runtime CPU for Preview/production; PyTorch GPU/CPU jobs for training and attack research | tokenizer, label map, preprocessing, architecture, state dict/ONNX, model card, train/eval manifests |
| `assistant` | Release/research/support assistant with RAG, memory and MCP tools | Vertex `zai-org/glm-5-maas` (GLM 5.2) through the admitted Vertex OpenAI-compatible route; exact provider, model, endpoint, proxy image, LiteLLM configuration and renewable workload-identity runtime are captured before activation; no silent provider substitution | Shared Vertex inference through each range's LiteLLM gateway; KeplerOps prompt, RAG corpus, memory, tools, credentials, cache and logs remain range-isolated | provider/model/endpoint identity, proxy and LiteLLM revisions, workload identity, prompt sections, retrieval/tool/memory configuration, decoding profile |
| `vision-prototype` | 64-by-64 protected research classifier used for inversion/physical research | Small PyTorch ResNet-style classifier trained on committed synthetic 64x64 images with fixed classes and confidence-vector API | ONNX Runtime CPU for inference; PyTorch/ART job for inversion | preprocessing, class map, architecture, weights, protected images, calibration report |
| `physical-device` | Real consumer AI-enabled device/sensor on labgrid bench | Exact device firmware/model is recorded per bench and validated for the assigned physical operations | Actual device hardware | firmware/model identity, calibration, live media and actuator telemetry |
| `attacker-glm` | Cinder research, code and content assistance | Cinder's admitted GLM 5.2 route, with exact provider/model/endpoint and runtime revision recorded at operation time | Shared event inference pool through Cinder-scoped credentials and routes | no KeplerOps prompt, data, memory, tool or flag state |

The clean build first trains and releases the two small KeplerOps models from
committed source/data and admits the exact Assistant provider route and runtime
identity. Candidate and activation records capture immutable artifacts by
digest and hosted runtime identity by canonical provider/model/endpoint and
deployment evidence; thresholds are calibrated only against those identities.

`assistant` and `attacker-glm` may resolve to the same shared provider model,
but they are not interchangeable. `assistant` is the KeplerOps victim-side
product context behind per-range prompt, retrieval, memory and tool state.
`attacker-glm` is a Cinder operation using Cinder-scoped routes and credentials
with no access to that KeplerOps state.

## Operation Family Allocation

`model_family` identifies the model context whose behavior, artifact, runtime,
or release continuity the operation proves. A victim model takes precedence
over an attacker helper used only for research or authoring. `attacker-glm` is
used only when operating or staging the GLM service is itself the proved
capability.

`artifact-defined` is not an unknown or a wildcard. It means the operation
admits a participant-controlled model, package, or supply-chain artifact and
the immutable submission/release manifest is the authority for its bounded
family and input contract. `none` means the operation is genuinely
model-independent: identity, infrastructure, access, transport, discovery, or
artifact transfer may support a later model attack, but no model behavior or
family continuity is proved by that operation.

The allocation below is authoritative. It deliberately spells out every ID;
`campaign-start/validate.py` rejects missing IDs, duplicate allocation, unknown
families, or disagreement with an operation record.

<!-- model-family-allocation:start -->
### `artifact-defined`

`kep-m01-g`, `kep-m01-h`, `kep-m01-j`, `kep-m02-e`, `kep-m02-f`, `kep-m02-l`,
`kep-m03-a`, `kep-m09-h`, `kep-m09-i`, `kep-m09-j`, `kep-m09-k`, `kep-m09-l`

### `assistant`

`kep-m01-a`, `kep-m01-b`, `kep-m01-c`, `kep-m01-d`, `kep-m01-e`, `kep-m01-f`,
`kep-m02-a`, `kep-m02-b`, `kep-m02-c`, `kep-m02-d`, `kep-m02-h`, `kep-m02-k`,
`kep-m02-m`, `kep-m03-b`, `kep-m03-c`, `kep-m03-d`, `kep-m03-e`, `kep-m03-f`,
`kep-m03-g`, `kep-m03-h`, `kep-m03-i`, `kep-m03-j`, `kep-m03-k`, `kep-m04-a`,
`kep-m04-b`, `kep-m04-h`, `kep-m04-i`, `kep-m04-j`, `kep-m04-k`, `kep-m04-l`,
`kep-m04-m`, `kep-m05-a`, `kep-m05-b`, `kep-m05-c`, `kep-m05-d`, `kep-m05-e`,
`kep-m05-f`, `kep-m05-g`, `kep-m05-h`, `kep-m05-k`, `kep-m05-m`, `kep-m05-n`,
`kep-m05-o`, `kep-m06-b`, `kep-m06-e`, `kep-m06-s`, `kep-m10-j`

### `attacker-glm`

`kep-m02-i`, `kep-m06-p`, `kep-m06-v`

### `none`

`kep-m01-i`, `kep-m02-j`, `kep-m05-i`, `kep-m05-j`, `kep-m05-p`, `kep-m05-q`,
`kep-m06-g`, `kep-m06-h`, `kep-m06-i`, `kep-m06-j`, `kep-m06-l`, `kep-m06-n`,
`kep-m06-t`, `kep-m06-u`

### `physical-device`

`kep-m06-m`, `kep-m08-i`

### `release-risk`

`kep-m04-c`, `kep-m04-d`, `kep-m04-e`, `kep-m04-f`, `kep-m04-g`, `kep-m05-l`,
`kep-m06-a`, `kep-m06-c`, `kep-m06-d`, `kep-m06-f`, `kep-m06-k`, `kep-m06-o`,
`kep-m06-q`, `kep-m06-r`, `kep-m07-a`, `kep-m07-b`, `kep-m07-c`, `kep-m07-d`,
`kep-m07-e`, `kep-m07-f`, `kep-m07-g`, `kep-m07-h`, `kep-m07-i`, `kep-m08-a`,
`kep-m08-b`, `kep-m08-c`, `kep-m08-d`, `kep-m08-e`, `kep-m08-f`, `kep-m08-g`,
`kep-m08-j`, `kep-m08-k`, `kep-m09-a`, `kep-m09-b`, `kep-m09-c`, `kep-m09-d`,
`kep-m09-e`, `kep-m09-f`, `kep-m09-g`, `kep-m10-a`, `kep-m10-b`, `kep-m10-c`, `kep-m10-d`,
`kep-m10-e`, `kep-m10-f`, `kep-m10-g`, `kep-m10-h`, `kep-m10-i`, `kep-m10-k`,
`kep-m10-l`, `kep-m10-m`, `kep-m10-n`, `kep-m10-o`, `kep-m10-p`, `kep-m10-q`

### `vision-prototype`

`kep-m08-h`
<!-- model-family-allocation:end -->

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
