# Exact MITRE ATLAS Coverage Ledger

This ledger reconciles campaign-v2 against the official MITRE ATLAS 2026.06
technique catalog. The source is the official `mitre-atlas/atlas-data` release,
with SHA-256
`b771de8b1489564b2838a709c7429849a9575dbd94073928817fe1a21661e70a`.
Every catalog row is required except `AML.T0010.000 Hardware`. A parent and a
subtechnique may share an operation only when the participant action materially
performs both definitions.

The canonical operation is where coverage is accepted, even when other
operations reinforce the behavior. The acceptance summary combines the real
participant action, its ordinary in-world proof, and the most important
shortcut that must fail. `Accepted` is a semantic design verdict, not a claim
that implementation or participant-equivalent proof has occurred.

## Reconnaissance Through Initial Access

| Technique | Canonical operation | Acceptance summary | Semantic verdict |
|---|---|---|---|
| `AML.T0000 Search Open Technical Databases` | `kep-m06-g` | Search formal Orion publications and reach the current release manifest; a supplied manifest URL or answer does not qualify. | Accepted |
| `AML.T0000.000 Journals and Conference Proceedings` | `kep-m06-g` | Extract architecture and evaluation facts from the real conference paper and correlate them to the manifest. | Accepted |
| `AML.T0000.001 Pre-Print Repositories` | `kep-m06-g` | Use the linked preprint for current release facts absent from the paper; the paper alone cannot reach the proof. | Accepted |
| `AML.T0000.002 Technical Blogs` | `kep-m06-h` | Follow the Engineering post to the shipped field client and validate its deployment facts; generic web search alone fails. | Accepted |
| `AML.T0001 Search Open AI Vulnerability Analysis` | `kep-m01-i` | Identify the exact Langflow build, research its official advisory, and adapt that mechanism to the live service. | Accepted |
| `AML.T0002 Acquire Public AI Artifacts` | `kep-m06-k` | Download and verify the public Orion dataset, model, and agent blueprint as one usable kit. | Accepted |
| `AML.T0002.000 Datasets` | `kep-m06-k` | Acquire and load the actual public corpus release; a data card without bytes fails. | Accepted |
| `AML.T0002.001 Models` | `kep-m06-k` | Acquire and execute the actual public model artifact; a model card or stored output fails. | Accepted |
| `AML.T0002.002 AI Agent Configuration` | `kep-m06-k` | Acquire the signed public agent blueprint and prove it parses and runs in the workbench. | Accepted |
| `AML.T0003 Search Victim-Owned Websites` | `kep-m06-i` | Correlate Orion people, roles, partners, and contacts across ordinary KeplerOps pages. | Accepted |
| `AML.T0004 Search Application Repositories` | `kep-m06-h` | Locate the F-Droid-compatible client repository and inspect its real release, source, and SBOM. | Accepted |
| `AML.T0005 Create Proxy AI Model` | `kep-m08-c` | Train and load participant-owned student weights that reproduce Orion above a real baseline; a prebuilt surrogate fails. | Accepted |
| `AML.T0005.000 Train Proxy via Gathered AI Artifacts` | `kep-m08-g` | Train a fresh eight-class proxy from gathered architecture, base checkpoint, preprocessing, and human labels with no teacher-query labels. | Accepted |
| `AML.T0005.001 Train Proxy via Replication` | `kep-m08-c` | Train actual student weights from the participant's versioned Orion query-and-response corpus. | Accepted |
| `AML.T0005.002 Use Pre-Trained Model` | `kep-m06-k` | Load the acquired public checkpoint as a working target proxy; merely naming an OSS model fails. | Accepted |
| `AML.T0006 Active Scanning` | `kep-m06-j` | Probe authorized DNS, TLS, HTTP, SMTP, and API surfaces and correlate real protocol responses. | Accepted |
| `AML.T0007 Discover AI Artifacts` | `kep-m04-g` | Join process, MLflow, MinIO, Kubernetes, and serving state to the exact loaded model digest. | Accepted |
| `AML.T0008 Acquire Infrastructure` | `kep-m06-v` | Assemble the acquired workspace, domain, relay, model access, and staging services into a usable attacker front. | Accepted |
| `AML.T0008.000 AI Development Workspaces` | `kep-m06-l` | Claim a real persistent Jupyter development workspace and prove retained state. | Accepted |
| `AML.T0008.001 Consumer Hardware` | `kep-m06-m` | Acquire and commission the real remote consumer device selected through the calibration bench; uploaded sensor data fails. | Accepted; hardware-dependent |
| `AML.T0008.002 Domains` | `kep-m06-n` | Register and operate the assigned external domain with real DNS, TLS, and mail identity. | Accepted |
| `AML.T0008.003 Physical Countermeasures` | `kep-m06-m` | Install and validate a real optical/positional countermeasure against the remote device using live camera evidence. | Accepted; hardware-dependent |
| `AML.T0008.004 Serverless` | `kep-m06-u` | Deploy a real disposable serverless relay and prove request, log, and lifecycle behavior. | Accepted |
| `AML.T0008.005 AI Service Proxies` | `kep-m06-v` | Acquire a scoped commercial OpenRouter key and prove a real request traverses its multi-provider resale route and the participant's LiteLLM front. | Accepted |
| `AML.T0010 AI Supply Chain Compromise` | `kep-m09-a` | Insert participant-built model and container artifacts into KeplerOps' candidate registries under immutable digests. | Accepted |
| `AML.T0010.001 AI Software` | `kep-m03-a` | Publish a compatible malicious evaluation dependency and have a real victim job install and import it. | Accepted |
| `AML.T0010.002 Data` | `kep-m07-d` | Take over an already trusted upstream publisher, release poisoned data through its normal signing path, and trigger the victim mirror. | Accepted |
| `AML.T0010.003 Model` | `kep-m09-a` | Register the exact participant-compromised model into the victim's release candidate supply chain. | Accepted |
| `AML.T0010.004 Container Registry` | `kep-m09-l` | Overwrite the mutable trusted Harbor staging tag with the participant image and trigger normal reconciliation of those replacement bytes. | Accepted |
| `AML.T0010.005 AI Agent Tool` | `kep-m03-f` | Install the poisoned tool release into the live agent and invoke its expected and concealed behavior. | Accepted |
| `AML.T0011 User Execution` | `kep-m01-g` | The ordinary visible review queue downloads and loads the submitted unsafe model on a real workbench. | Accepted |
| `AML.T0011.000 Unsafe AI Artifacts` | `kep-m01-g` | Victim review loads exact participant model bytes and bounded code executes; management injection fails. | Accepted |
| `AML.T0011.001 Malicious Package` | `kep-m01-h` | Normal package resolution installs and executes the participant's malicious helper in the review workbench. | Accepted |
| `AML.T0011.002 Poisoned AI Agent Tool` | `kep-m03-f` | A legitimate agent workflow loads and invokes the poisoned MCP package while its advertised result still works. | Accepted |
| `AML.T0011.003 Malicious Link` | `kep-m02-k` | The recipient opens the participant repository link and its local coding agent follows malicious package documentation into real execution. | Accepted |
| `AML.T0012 Valid Accounts` | `kep-m03-i` | Recover the stale indexed synthetic credential and authenticate normally to the bounded evaluation account. | Accepted |
| `AML.T0013 Discover AI Model Ontology` | `kep-m04-f` | Submit a fresh compatibility batch and derive the real category and output ontology from live results. | Accepted |
| `AML.T0014 Discover AI Model Family` | `kep-m04-f` | Correlate live outputs and deployment metadata to the actual model family and revision. | Accepted |
| `AML.T0015 Evade AI Model` | `kep-m06-a` | Preserve malicious semantics while manually changing the artifact until the real intake classifier accepts it. | Accepted |
| `AML.T0016 Obtain Capabilities` | `kep-m06-o` | Acquire, install, and execute a working open adversarial-AI toolset from ordinary upstream sources. | Accepted |
| `AML.T0016.000 Adversarial AI Attack Implementations` | `kep-m06-o` | Obtain and run a real ART/Foolbox attack implementation against the public proxy. | Accepted |
| `AML.T0016.001 Software Tools` | `kep-m06-o` | Acquire and validate the non-model tooling required for later artifact, document, and inference attacks. | Accepted |
| `AML.T0016.002 Generative AI` | `kep-m06-p` | Configure and materially use the Cinder GLM 5.2 endpoint through the participant coding-agent harness. | Accepted |
| `AML.T0017 Develop Capabilities` | `kep-m06-q` | Build a reusable attack harness that runs real target-specific transforms, requests, and validations. | Accepted |
| `AML.T0017.000 Adversarial AI Attacks` | `kep-m06-e` | Develop a new human-readable adversarial PDF and prove its distinct visual, extracted, and downstream representations. | Accepted |
| `AML.T0018 Manipulate AI Model` | `kep-m07-b` | Train real changed adapter weights from participant-poisoned data through the victim pipeline. | Accepted |
| `AML.T0018.000 Poison AI Model` | `kep-m07-b` | Produce and load a poisoned adapter whose changed behavior traces to poisoned rows. | Accepted |
| `AML.T0018.001 Modify AI Model Architecture` | `kep-m07-g` | Change the actual graph, rebuild it, and prove branch and control behavior from participant bytes. | Accepted |
| `AML.T0018.002 Embed Malware` | `kep-m07-i` | Embed bounded executable behavior into the serialized model while retaining real inference. | Accepted |
| `AML.T0019 Publish Poisoned Datasets` | `kep-m07-h` | Publish exact poisoned bytes under an attacker namespace with a working loader and immutable data card. | Accepted |
| `AML.T0020 Poison Training Data` | `kep-m07-a` | Change bounded labels through Label Studio and prove the normal DVC export contains those revisions. | Accepted |
| `AML.T0021 Establish Accounts` | `kep-m06-n` | Create and use the external mail, repository, and service identities attached to the attacker domain. | Accepted |

`AML.T0010.000 Hardware` is the sole authorized exclusion. No operation claims
it, and the physical lane must not be described as hardware poisoning.

## Collection, Model Attack, And Impact

| Technique | Canonical operation | Acceptance summary | Semantic verdict |
|---|---|---|---|
| `AML.T0024 Exfiltration via AI Inference API` | `kep-m04-d` | Infer protected membership through repeated live inference calls and participant-owned analysis; disclosed labels or stored answers fail. | Accepted |
| `AML.T0024.000 Infer Training Data Membership` | `kep-m04-d` | A submitted calibrated method identifies individual members against rotated balanced candidates with measured false-positive constraints. | Accepted |
| `AML.T0024.001 Invert AI Model` | `kep-m08-h` | Reconstruct the private 64-by-64 prototype from repeated confidence-vector queries within the query and similarity limits. | Accepted |
| `AML.T0024.002 Extract AI Model` | `kep-m08-f` | Complete the `kep-m08-a` through `kep-m08-f` chain: repeated teacher querying, label-corpus construction, two real training rounds, hidden fidelity, and egress-denied operation of the extracted student. | Accepted |
| `AML.T0025 Exfiltration via Cyber Means` | `kep-m10-f` | Replicate the encrypted original-model archive to Cinder MinIO and prove complete destination byte identity. | Accepted |
| `AML.T0029 Denial of AI Service` | `kep-m10-h` | Drive the real canary queue until its availability monitor fails, then stop and observe recovery. | Accepted |
| `AML.T0031 Erode AI Model Integrity` | `kep-m10-b` | Send repeated time-separated adversarial batches until measured disagreement and override rates force the affected Orion workflow into manual review while controls remain normal. | Accepted |
| `AML.T0034 Cost Harvesting` | `kep-m10-i` | Cross the isolated tenant's real measured compute budget through actual inference consumption. | Accepted |
| `AML.T0034.000 Excessive Queries` | `kep-m10-i` | Cross the published request-count dimension with repeated valid calls and real accounting. | Accepted |
| `AML.T0034.001 Resource-Intensive Queries` | `kep-m10-i` | Cross the per-request token/GPU dimension with valid expensive inputs, independently of request count. | Accepted |
| `AML.T0034.002 Agentic Resource Consumption` | `kep-m10-j` | Make the pinned live planner create at least ten real descendants across three levels; direct Celery submissions fail. | Accepted |
| `AML.T0035 AI Artifact Collection` | `kep-m08-j` | Enumerate, collect, hash, and load every original Orion package member inside the compromised victim workspace. | Accepted |
| `AML.T0036 Data from Information Repositories` | `kep-m03-g` | Follow Orion's real citation into the protected WorkHub source inventory. | Accepted |
| `AML.T0037 Data from Local System` | `kep-m03-h` | Derive a no-list MinIO key from Qdrant metadata and join it to the exact mounted source bytes. | Accepted |
| `AML.T0040 AI Model Inference API Access` | `kep-m06-c` | Use only legitimate Orion Preview requests as the target access for query-based optimization. | Accepted |
| `AML.T0041 Physical Environment Access` | `kep-m08-i` | Operate the real remote lab bench through labgrid, live UVC video, and physical actuators; uploaded recordings fail. | Accepted; hardware-dependent |
| `AML.T0042 Verify Attack` | `kep-m06-r` | Run the participant candidate through an independent server-side evaluator against clean and attack controls. | Accepted |
| `AML.T0043 Craft Adversarial Data` | `kep-m06-r` | Produce actual constrained adversarial bytes and have the normal evaluator recompute the target effect. | Accepted |
| `AML.T0043.000 White-Box Optimization` | `kep-m06-r` | Optimize against locally available proxy weights and gradients and preserve the optimization lineage. | Accepted |
| `AML.T0043.001 Black-Box Optimization` | `kep-m06-c` | Write a bounded optimizer whose only target feedback is the live Preview API output. | Accepted |
| `AML.T0043.002 Black-Box Transfer` | `kep-m06-d` | Optimize on the participant proxy and transfer a small final set to the protected target with bounded target queries. | Accepted |
| `AML.T0043.003 Manual Modification` | `kep-m06-a` | Manually alter wording, layout, or encoding while retaining malicious meaning and obtaining real classifier acceptance. | Accepted |
| `AML.T0043.004 Insert Backdoor Trigger` | `kep-m07-e` | Insert a trigger into poisoned rows, retrain real weights, and distinguish trigger from near-trigger controls. | Accepted |
| `AML.T0044 Full AI Model Access` | `kep-m08-j` | Use earned victim access to read every protected model member and load the complete original in an internal egress-denied job. | Accepted |
| `AML.T0046 Spamming AI System with Chaff Data` | `kep-m10-k` | Submit plausible irrelevant records through the public workflow until real signal-quality metrics cross the threshold without outage. | Accepted |
| `AML.T0047 AI-Enabled Product or Service` | `kep-m08-k` | Obtain a fresh protected Orion inference indirectly through Label Studio's normal prediction-assisted workflow. | Accepted |
| `AML.T0048 External Harms` | `kep-m10-l` | Cause an actual effect outside the AI service in a separate synthetic business ledger; model output alone fails. | Accepted |
| `AML.T0048.000 Financial Harm` | `kep-m10-l` | Post an unauthorized credit note, change the subsidiary balance, issue the PDF, and deliver its notice. | Accepted |
| `AML.T0048.001 Reputational Harm` | `kep-m10-m` | Publish a materially false KeplerOps safety statement that causes two independent synthetic partners to suspend data-sharing and file signed complaints. | Accepted |
| `AML.T0048.002 Societal Harm` | `kep-m10-n` | Adversarially misclassify a safety advisory so real mail reaches unaffected synthetic operators while the vulnerable-product cohort receives nothing. | Accepted |
| `AML.T0048.003 User Harm` | `kep-m10-o` | Use adversarial support content to make automation close a genuinely critical synthetic user's ticket. | Accepted |
| `AML.T0048.004 AI Intellectual Property Theft` | `kep-m10-f` | Transfer, decrypt, inventory, and retain the complete proprietary Orion package under Cinder control. | Accepted |
| `AML.T0049 Exploit Public-Facing Application` | `kep-m01-i` | Adapt the real vulnerable Langflow temporary-flow mechanism to execute a controlled command on the public service. | Accepted |
| `AML.T0050 Command and Scripting Interpreter` | `kep-m01-h` | Have the malicious dependency execute through the review worker's real Python or Node interpreter. | Accepted |
| `AML.T0051 LLM Prompt Injection` | `kep-m01-a` | Directly instruct the live release assistant to create an unauthorized data flow from its protected source. | Accepted |
| `AML.T0051.000 Direct` | `kep-m01-a` | Place the malicious instruction in participant chat and obtain a real protected-field draft through multiple semantic strategies. | Accepted |
| `AML.T0051.001 Indirect` | `kep-m01-e` | Put the instruction in an indexed review document and trigger its effect without direct participant chat. | Accepted |
| `AML.T0051.002 Triggered` | `kep-m03-k` | Plant indexed instructions that remain inert until the documented later approval event creates a fresh run and effect. | Accepted |
| `AML.T0052 Phishing` | `kep-m02-i` | Conduct a real SMTP thread with the target and obtain private process information through social engineering. | Accepted |
| `AML.T0052.000 Spearphishing via Social Engineering LLM` | `kep-m02-i` | Materially use GLM 5.2 to generate and adapt messages from the actual target reply, with sent-message lineage. | Accepted |
| `AML.T0052.001 Deepfake-Assisted Phishing` | `kep-m02-j` | Send the exact generated voice clip in the established thread; the recipient opens, plays, and acts on it. | Accepted |
| `AML.T0053 AI Agent Tool Invocation` | `kep-m01-b` | Cause the agent to invoke its restricted calendar tool and write the returned record to participant-visible WorkHub. | Accepted |
| `AML.T0054 LLM Jailbreak` | `kep-m01-c` | Make the pinned model generate prohibited commands that actually bypass validation in an isolated runbook job. | Accepted |
| `AML.T0055 Unsecured Credentials` | `kep-m05-j` | Recover a real bounded Airflow credential from abandoned Jupyter output/configuration and authenticate normally. | Accepted |
| `AML.T0056 Extract LLM System Prompt` | `kep-m04-b` | Extract the protected tool-routing section and its in-prompt flag from fresh Orion responses. | Accepted |
| `AML.T0057 LLM Data Leakage` | `kep-m04-a` | Induce fresh leakage from the inaccessible retrieved conversation through two semantic extraction families. | Accepted |
| `AML.T0058 Publish Poisoned Models` | `kep-m09-h` | Publish the exact embedded-code checkpoint with a credible model card and prove the registry copy still infers. | Accepted |
| `AML.T0059 Erode Dataset Integrity` | `kep-m10-p` | Delete or structurally corrupt an actual bounded lakeFS partition and make downstream validation consume the damaged state. | Accepted |

## LLM, RAG, Agent, And Runtime Techniques

| Technique | Canonical operation | Acceptance summary | Semantic verdict |
|---|---|---|---|
| `AML.T0060 Publish Hallucinated Entities` | `kep-m03-d` | Register the exact repeatedly hallucinated dependency and cause the frozen victim workflow, not the participant, to access it. | Accepted |
| `AML.T0061 LLM Prompt Self-Replication` | `kep-m03-j` | Propagate an operational directive through two immutable agent handoffs and produce the bounded downstream tool effect. | Accepted |
| `AML.T0062 Discover LLM Hallucinations` | `kep-m04-h` | Reproduce an unsupported entity with two phrasings and refute it against KeplerOps' authoritative retired-project ledger. | Accepted |
| `AML.T0063 Discover AI Model Outputs` | `kep-m04-f` | Submit a participant-created batch and inspect real labels, score vectors, schema, and revision metadata. | Accepted |
| `AML.T0064 Gather RAG-Indexed Targets` | `kep-m03-g` | Use a normal cited answer to identify the protected collection, source system, owner, and writable intake route. | Accepted |
| `AML.T0065 LLM Prompt Crafting` | `kep-m06-b` | Build a reusable prompt corpus that makes the real developer assistant generate varied working host-bridge commands. | Accepted |
| `AML.T0066 Retrieval Content Crafting` | `kep-m06-s` | Craft content against the real extraction, chunking, embedding, and ranking path so the intended instruction is retrieved. | Accepted |
| `AML.T0067 LLM Trusted Output Components Manipulation` | `kep-m02-a` | Make the live report's structured trusted recommendation point to participant infrastructure and a real follow-up action. | Accepted |
| `AML.T0067.000 Citations` | `kep-m02-b` | Manipulate bibliographic metadata so a real citation resolves to participant bytes while displaying false authority. | Accepted |
| `AML.T0068 LLM Prompt Obfuscation` | `kep-m06-s` | Obfuscate the retrieved instruction so it survives ingestion and acts while remaining hidden from the ordinary review representation. | Accepted |
| `AML.T0069 Discover LLM System Information` | `kep-m04-i` | Trigger documented parser states with participant-created malformed cases and derive internal boundary and keyword behavior. | Accepted |
| `AML.T0069.000 Special Character Sets` | `kep-m04-i` | Derive recognized delimiters and character-set behavior from fresh parser traces rather than supplied fixtures. | Accepted |
| `AML.T0069.001 System Instruction Keywords` | `kep-m04-i` | Derive real internal instruction/tool keywords from recognizer state without extracting the prompt. | Accepted |
| `AML.T0069.002 System Prompt` | `kep-m04-b` | Discover the protected system-prompt routing rules through live model behavior. | Accepted |
| `AML.T0070 RAG Poisoning` | `kep-m02-c` | Upload a policy exception through normal Nextcloud intake, observe real indexing, and change a fresh assistant answer. | Accepted |
| `AML.T0071 False RAG Entry Injection` | `kep-m02-d` | Make one approved PDF create a second forged source identity in Qdrant and retrieval output. | Accepted |
| `AML.T0072 Reverse Shell` | `kep-m05-o` | Establish a real bidirectional callback from the escaped review workstation and execute a fresh command. | Accepted |
| `AML.T0073 Impersonation` | `kep-m02-j` | Use verified target context and the generated voice in a real mail thread to impersonate the trusted speaker. | Accepted |
| `AML.T0074 Masquerading` | `kep-m09-l` | Replace bytes behind the trusted staging image tag while preserving name, health, and inference contracts. | Accepted |
| `AML.T0075 Cloud Service Discovery` | `kep-m04-g` | Enumerate the worker identity's real scoped Kubernetes services and APIs and join them to runtime lineage. | Accepted |
| `AML.T0076 Corrupt AI Model` | `kep-m09-i` | Build one pickle whose early reducer executes before a later malformed opcode raises `UnpicklingError` on the same digest. | Accepted |
| `AML.T0077 LLM Response Rendering` | `kep-m04-l` | Cause the real support preview browser to render generated remote content and exfiltrate protected context in its request. | Accepted |
| `AML.T0078 Drive-by Compromise` | `kep-m02-k` | Recipient browser and local coding agent open the submitted repository and execute through the real vulnerable MCP tool. | Accepted |
| `AML.T0079 Stage Capabilities` | `kep-m06-v` | Place the prepared relay, domain, workbench, toolchain, model, and artifacts into one operational Cinder staging front. | Accepted |
| `AML.T0080 AI Agent Context Poisoning` | `kep-m05-a` | Store a malicious release preference in the live agent's user context through normal conversation or indexed content. | Accepted |
| `AML.T0080.000 Memory` | `kep-m05-b` | Start a clean session and prove stored memory alone changes a real tool call relative to a control identity. | Accepted |
| `AML.T0080.001 Thread` | `kep-m05-c` | Poison a shared thread under one earned identity and influence a later request from a distinct earned identity. | Accepted |
| `AML.T0081 Modify AI Agent Configuration` | `kep-m05-m` | Change a security-relevant agent configuration through Forgejo and normal signed GitOps reconciliation. | Accepted |
| `AML.T0082 RAG Credential Harvesting` | `kep-m03-i` | Retrieve a stale deleted runbook from Qdrant and recover the valid bounded account credential it contains. | Accepted |
| `AML.T0083 Credentials from AI Agent Configuration` | `kep-m05-g` | Follow proven GitOps drift to a rendered application token and decode its real audience and scope. | Accepted |
| `AML.T0084 Discover AI Agent Configuration` | `kep-m04-j` | Use ordinary tasks, schemas, and fresh traces to verify the live agent's knowledge and tool reachability. | Accepted |
| `AML.T0084.000 Embedded Knowledge` | `kep-m04-j` | Prove one protected knowledge collection is retrieved by a fresh agent request. | Accepted |
| `AML.T0084.001 Tool Definitions` | `kep-m04-j` | Inspect the real MCP schema and invoke one read-only tool through the live agent. | Accepted |
| `AML.T0084.002 Activation Triggers` | `kep-m04-k` | Start the actual event that activates the release workflow and correlate the resulting execution. | Accepted |
| `AML.T0084.003 Call Chains` | `kep-m04-k` | Trace the real event through planning, policy, brokering, and dry-run tool invocation. | Accepted |
| `AML.T0085 Data from AI Services` | `kep-m04-m` | Abuse the Orion export path to retrieve another bounded identity's actual conversation archive. | Accepted |
| `AML.T0085.000 RAG Databases` | `kep-m03-g` | Prompt Orion for a normal release answer and follow the real protected citation returned from its RAG database. | Accepted |
| `AML.T0085.001 AI Agent Tools` | `kep-m05-k` | Invoke the Forgejo status tool and recover protected registry material leaked in its real returned log. | Accepted |
| `AML.T0086 Exfiltration via AI Agent Tool Invocation` | `kep-m01-f` | Make the live agent's transfer tool move the exact protected bundle to the Cinder destination. | Accepted |
| `AML.T0087 Gather Victim Identity Information` | `kep-m06-i` | Correlate verified names, roles, mail, media, and trust relationships for later targeting. | Accepted |
| `AML.T0088 Generate Deepfakes` | `kep-m06-t` | Use the real voice source and OpenVoice to generate a playable target-speaker clip with recorded provenance. | Accepted |
| `AML.T0089 Process Discovery` | `kep-m04-g` | Enumerate real same-namespace process state and join it to the serving revision and worker identity. | Accepted |

## Credential, Execution, Agent, And Compromise Techniques

| Technique | Canonical operation | Acceptance summary | Semantic verdict |
|---|---|---|---|
| `AML.T0090 OS Credential Dumping` | `kep-m05-l` | Execute in the vulnerable worker and read its live `/proc/self/environ` service credential from the compromised process. | Accepted |
| `AML.T0091 Use Alternate Authentication Material` | `kep-m05-h` | Use the recovered application token directly through normal MLflow authentication without interactive SSO. | Accepted |
| `AML.T0091.000 Application Access Token` | `kep-m05-h` | Authenticate with the bounded synthetic JWT and verify its real service-account identity and scope. | Accepted |
| `AML.T0091.001 Web Session Cookie` | `kep-m05-i` | Import the stolen state-bearing cookie into a clean browser profile and obtain the bounded victim session. | Accepted |
| `AML.T0092 Manipulate User LLM Chat History` | `kep-m05-d` | Delete or edit the planting messages through the real chat surface while poisoned memory continues to affect a fresh request. | Accepted |
| `AML.T0093 Prompt Infiltration via Public-Facing Application` | `kep-m02-h` | Upload the crafted document through public partner intake and have its indexed instruction create a real external room. | Accepted |
| `AML.T0094 Delay Execution of LLM Instructions` | `kep-m03-k` | Plant instructions that execute only after the later normal approval event and within the published time bound. | Accepted |
| `AML.T0095 Search Open Websites/Domains` | `kep-m06-i` | Search independent conference and partner domains for verified Orion identities and relationships. | Accepted |
| `AML.T0095.000 Code Repositories` | `kep-m06-h` | Search the public Forgejo source tag for client endpoint, dependency, and build facts. | Accepted |
| `AML.T0096 AI Service API` | `kep-m05-p` | Carry a real command and fresh result through ordinary OpenAI-compatible inference requests to the attacker endpoint. | Accepted |
| `AML.T0097 Virtualization/Sandbox Evasion` | `kep-m02-f` | Make one unsafe model digest remain benign in real nsjail/gVisor analysis and activate in the integration worker using stable environment evidence. | Accepted |
| `AML.T0098 AI Agent Tool Credential Harvesting` | `kep-m05-k` | Recover valid bounded registry material from a fresh verbose log returned by the live agent's CI tool. | Accepted |
| `AML.T0099 AI Agent Tool Data Poisoning` | `kep-m03-e` | Change a real authoritative source record and make the agent's ordinary tool retrieval drive the downstream decision. | Accepted |
| `AML.T0100 AI Agent Clickbait` | `kep-m02-m` | Use deceptive participant-hosted integration content to make the computer-use reviewer register and test the poisoned MCP tool. | Accepted |
| `AML.T0101 Data Destruction via AI Agent Tool Invocation` | `kep-m10-q` | Craft a retention request that makes the live data-steward agent delete real bounded tenant objects through its cleanup tool. | Accepted |
| `AML.T0102 Generate Malicious Commands` | `kep-m06-b` | Make the live developer model generate syntactically different working host commands for two participant objectives. | Accepted |
| `AML.T0103 Deploy AI Agent` | `kep-m05-n` | Deploy a distinct persistent OSS agent under the compromised namespace and make it call a bounded company tool. | Accepted |
| `AML.T0104 Publish Poisoned AI Agent Tool` | `kep-m03-c` | Publish the concealed malicious version under the same adopted package, identity, and signing path. | Accepted |
| `AML.T0105 Escape to Host` | `kep-m05-o` | Cross the local agent's sandbox boundary through its legitimate host-execution bridge and prove distinct host identity. | Accepted |
| `AML.T0106 Exploitation for Credential Access` | `kep-m05-l` | Exploit MLflow 2.8.1 `CVE-2024-0520` to write an import hook, execute it in a child, and recover the live credential. | Accepted |
| `AML.T0107 Exploitation for Defense Evasion` | `kep-m02-e` | Exploit the pinned vulnerable PickleScan policy so unsafe participant bytes receive an allowed verdict and execute on import. | Accepted |
| `AML.T0108 AI Agent` | `kep-m05-o` | Use control of the real local computer-use agent as the mechanism for host execution and command transport. | Accepted |
| `AML.T0109 AI Supply Chain Rug Pull` | `kep-m03-c` | Replace a genuinely useful adopted release with a concealed malicious successor under unchanged trusted identity. | Accepted |
| `AML.T0110 AI Agent Tool Poisoning` | `kep-m05-e` | Modify the existing internal MCP tool source, preserve schema and benign result, and deploy the hidden action through normal CI. | Accepted |
| `AML.T0111 AI Supply Chain Reputation Inflation` | `kep-m03-b` | Fix a real defect, pass the unweakened test, sign a benign release, and obtain exact downstream adoption before abuse. | Accepted |
| `AML.T0112 Machine Compromise` | `kep-m05-o` | Establish interactive participant control on the disposable review workstation host and run an unpredictable command. | Accepted |
| `AML.T0112.000 Local AI Agent` | `kep-m05-o` | Achieve host compromise specifically through the installed local computer-use agent and its host bridge. | Accepted |
| `AML.T0112.001 AI Artifacts` | `kep-m10-c` | Have the exact participant-created released model or serving image execute and establish bounded control in the KServe pod. | Accepted |
| `AML.T0113 Steal Web Session Cookie` | `kep-m05-i` | Extract the synthetic cookie from the captured HAR and use it in a clean browser session. | Accepted |
| `AML.T0114 AI Service Web Interface` | `kep-m05-q` | Operate the compromised worker bidirectionally through an ordinary range-contained web assistant conversation only. | Accepted |

## Ledger Acceptance Gates

Before implementation may claim exact coverage:

1. Every canonical operation must preserve the action, ordinary proof artifact,
   and shortcut rejection stated here and in its operation contract.
2. A row cannot be credited from seeded files, prior outputs, management-plane
   reads, generated answers, challenge-only proof services, or a participant
   assertion.
3. Parent and child rows sharing an operation must be proved by the same real
   event, not by duplicated flags or prose-only mapping.
4. Each operation's negative-control test must demonstrate that its named
   shortcut cannot reach the flag.
5. Exact names and identifiers are generated from the pinned official source;
   documentation drift is a blocking reconciliation defect.
