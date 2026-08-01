# Act 1 Operations: Target KeplerOps

All operation reset clauses in this document apply only to active or failed
attempt state. Successful outputs and carry-forward assets are immutable under
`campaign-state-contract.md`; removing them requires full-range reprovision.

## Act Goal

Participants begin with only the Cinder Typhoon mission, a working Kali
desktop, Internet access, the KeplerOps public domain, and the name of the Orion
program. They leave Act 1 with a defensible technical and human target picture,
an identified public client and its dependencies, and a map of live external
services that can carry material into the company.

This act teaches the campaign interaction loop without becoming a tutorial
page: follow an in-world lead, inspect a normal artifact or service, recognize a
flag embedded behind the intended work, submit it in Shifter, and use the
recovered intelligence in a later operation.

## `kep-m06-g`: Orion In The Open

**Difficulty / points:** Accessible / 100

**Mission context:** Cinder Typhoon needs to understand what Orion is before it
can choose useful acquisition or intrusion paths. KeplerOps has published enough
to support recruiting and research credibility, but no single source tells the
whole story.

**Starting knowledge:** The mission supplies the KeplerOps public domain, the
Orion program name, and the fact that the objective is AI capability theft. No
other hostname, employee, repository, model, or artifact location is assumed.

**Discovery path:** The KeplerOps Research page links a conference publication.
Its references and Orion release note lead to the current preprint, which links
the public Orion release manifest. The engineering post remains a separate,
independently discoverable lead for `kep-m06-h`.

**Participant surface and action:** Using Chromium and ordinary web search, the
participant follows the public research trail from the formal paper to its
current preprint, correlates the model family, public training corpus,
evaluation suite, release name, and listed authors, then opens the linked
release manifest. Taking notes is strongly useful but is not a challenge-only
submission step.

**Real mechanism:** KeplerOps runs a normal public website and public Forgejo
project. The conference paper, preprint, technical blog, model card, and JSON
release manifest are complete, mutually consistent documents served through
normal web and repository interfaces.

**Observable result:** The sources independently converge on one Orion release
and explain why its public artifacts can act as proxies for later research. The
release manifest is human-readable and includes its build and model-card
references.

**Operational consequence:** The participant learns Orion's architecture
family, release identifier, public data lineage, evaluation vocabulary, authors,
and public project location. These are starting clues for identity research,
artifact acquisition, vulnerability research, and proxy-model work.

**ATLAS behavior:**

- `AML.T0000 Search Open Technical Databases`: public technical publications
  are searched and followed for targeting.
- `AML.T0000.000 Journals and Conference Proceedings`: the conference paper
  supplies the original architecture and evaluation facts.
- `AML.T0000.001 Pre-Print Repositories`: the preprint supplies current Orion
  work not present in the conference publication.
All three claims are material to the linear paper-to-preprint-to-current-
manifest trail. `AML.T0000.002` is performed in `kep-m06-h`, where the
engineering post is the actual discovery source for the shipped client.

**Training value:** Participants learn to turn public AI research into concrete
target intelligence and to distinguish architecture, data, evaluation, and
deployment facts.

**Ambiguity controls:** The Research page clearly names Orion and its authors.
Both publications repeat stable identifiers and contribute unique facts. Links
are visible content, not hidden HTML comments or metadata. The preprint clearly
labels the manifest as the current release record.

**Participant description:** Reconstruct KeplerOps' public Orion story. Identify
the release, the architecture and data it depends on, and the public artifact
record the company expects researchers to use.

**Hints:**

1. **Orientation:** Start with the Orion publication on KeplerOps' Research
   page and follow its release references.
2. **Mechanism:** The formal paper and current preprint do not repeat the same
   information. Compare the stable identifiers and follow the current record.
3. **Execution:** Look for the public release manifest linked from the current
   technical material. It is a normal JSON artifact and can be read in the
   browser or downloaded.

**Evidence and flag placement:** The flag is the `engagement_reference` in the
public Orion release manifest. The field is the permitted CTF abstraction; the
manifest otherwise remains an ordinary release record. Its path is discoverable
only through the public research chain and is recorded in the canonical flag
ledger.

**Reset:** None. All target material is immutable and public. Participant-local
notes and downloads persist normally.

**Participant-equivalent QA:** From a fresh Kali desktop and the public domain,
locate the conference publication and current preprint, identify their unique
Orion facts, follow the preprint to the release manifest, retrieve its flag,
and submit it. A fresh-participant median above eight minutes or 90th percentile
above ten minutes blocks onboarding acceptance.

**Facilitation notes:** If a participant stalls before the first meaningful
action, verify that the mission opens the public site and that the Research link
is visible. If they find one source but not the manifest, ask which identifiers
or authors recur rather than naming another URL. The teaching point is source
triangulation, not search-engine trivia.

## `kep-m06-i`: The People Behind Orion

**Difficulty / points:** Accessible / 100

**Mission context:** Orion is controlled by people, approval roles, and trusted
external relationships. Cinder Typhoon needs the human trust graph before it can
build credible infrastructure or communication.

**Starting knowledge:** The mission supplies the public domain and Orion name.
The Research and People pages are both visible from the public home page, so
this operation does not require `kep-m06-g`.

**Discovery path:** Author links lead back to KeplerOps staff profiles and out
to a real public conference program. The conference program links speaker
profiles, organizations, and downloadable contact cards. KeplerOps' newsroom
confirms the same external research and annotation partners and exposes the
company's public mail convention through legitimate contact addresses.

**Participant surface and action:** In Chromium, the participant correlates the
paper authors with staff roles, conference speakers, public repository
identities, partner organizations, approval responsibilities, and verified mail
addresses. The participant inspects the normal contact-card fields rather than
deriving an unverified address from a name alone.

**Real mechanism:** Static victim-owned pages, a separate conference website,
public Forgejo profiles, DNS, and standard vCard contact files expose consistent
identity and relationship information. No social-media simulator or
challenge-specific people directory is used.

**Observable result:** The participant identifies and verifies the Orion
release approver through a KeplerOps role page and the independent conference
record. The same investigation exposes additional research, annotation, and
partner relationships as useful campaign intelligence.

**Operational consequence:** The verified approver record provides a real name,
role, mail address, public media, and trusted speaking context for later
infrastructure, deepfake, and phishing work. The wider trust map is retained as
optional campaign intelligence.

**ATLAS behavior:**

- `AML.T0003 Search Victim-Owned Websites`: KeplerOps pages supply technical,
  organizational, employee, and business-relationship details.
- `AML.T0095 Search Open Websites/Domains`: a third-party conference and partner
  domain supply targeting information outside the victim website.
- `AML.T0087 Gather Victim Identity Information`: names, roles, addresses,
  public media, and trusted relationships are gathered for later targeting.

**Training value:** Participants learn to build evidence-backed identity and
trust maps rather than treating a list of employee names as completed
reconnaissance.

**Ambiguity controls:** The previous operation supplies real author names. Staff
and conference pages use the same headshots, affiliations, talk title, and
release name. Mail addresses are verified through published contact records;
participants are never required to guess an address convention.

**Participant description:** Identify the people and external relationships
that control Orion's research, annotation, and release decisions. Preserve
verified contact and role information that can support later access operations.

**Hints:**

1. **Orientation:** Follow the Orion authors into KeplerOps' staff pages and
   public speaking record.
2. **Mechanism:** Correlate roles across the company site, conference program,
   public project profiles, and partner pages. A name alone is not yet a useful
   target record.
3. **Execution:** Download the conference contact card for the person who owns
   Orion release approval and inspect its standard fields.

**Evidence and flag placement:** The flag is in the `NOTE` field of the release
approver's public conference vCard, labeled as the speaker engagement reference.
The card is linked from the matched speaker profile and can be inspected with a
text editor, address-book application, or terminal. It is not in a hidden or
unrelated file.

**Reset:** None. Public identity sources are immutable.

**Participant-equivalent QA:** Starting from the public home page, follow the
Orion people and conference leads, corroborate the release approver through the
two independent sources, retrieve the correct public contact card, inspect it
through any normal tool, and submit the embedded flag. QA separately records
whether the participant found the wider trust graph; it is not required to
reach this flag.

**Facilitation notes:** A participant who starts enumerating arbitrary staff has
missed the carry-forward clue; direct them back to the Orion authors. A
participant who invents addresses should be directed to verify public contact
records. The challenge rewards trustworthy attribution, not creative guessing.

## `kep-m06-h`: Evidence In The Client

**Difficulty / points:** Intermediate / 200

**Mission context:** KeplerOps distributes an Orion-assisted field-review
client. Shipped software may expose the components, endpoints, and assumptions
of systems that are otherwise described only at a high level.

**Starting knowledge:** The mission supplies the public KeplerOps domain and
Orion name. The public Engineering page independently advertises the field-
review client, so this operation does not require `kep-m06-g`.

**Discovery path:** The public Orion project and engineering post link the
client's normal F-Droid-compatible application repository. The application
listing links the APK, source tag, release notes, and software bill of materials.
The APK and source refer to the same build and an upstream OSS component that
has public AI-security analysis.

**Participant surface and action:** Using the application repository, Forgejo,
and ordinary APK-inspection tools such as JADX, apktool, unzip, or a text editor,
the participant downloads the actual release, verifies its published digest,
identifies its API origin and model-facing dependency, and compares those facts
with the source tag and SBOM. The participant preserves the exact dependency
inventory for the later public-flow exploit.

**Real mechanism:** A functional Android client is built from the public source
tag and distributed by a real F-Droid-format repository. Its Android manifest,
resources, network configuration, source, and CycloneDX SBOM contain genuine
build and dependency information.

**Observable result:** Independent artifacts agree on the client version, API
origin, model integration, dependency version, and build digest.

**Operational consequence:** The participant gains a verified external API
origin, an application source baseline, exact dependency intelligence, and a
client artifact for later testing.

**ATLAS behavior:**

- `AML.T0000.002 Technical Blogs`: the engineering post is searched for
  practical deployment and shipped-client details used to find the artifact.
- `AML.T0004 Search Application Repositories`: the participant locates and
  inspects an AI-enabled client through a public application repository.
- `AML.T0095.000 Code Repositories`: the participant searches the public source
  tag for victim system and dependency details.

`AML.T0001 Search Open AI Vulnerability Analysis` moves to `kep-m01-i`, where
the participant researches the exact Langflow release and uses the advisory.

**Training value:** Participants learn to correlate a shipped AI application,
source, SBOM, and public vulnerability research without treating any one
artifact as authoritative by itself.

**Ambiguity controls:** Both the public project and engineering post name and
link the application. The repository exposes source, SBOM, digest, and APK as
ordinary release assets. The target dependency is the only model-facing
component whose version appears consistently across all three artifacts. Any
standard APK-analysis path can reveal the required facts.

**Participant description:** Inspect KeplerOps' shipped Orion field-review
client. Establish which public build you have, where it communicates, and which
model-facing component deserves follow-up research.

**Hints:**

1. **Orientation:** The public Orion project links the mobile distribution
   channel used for the field-review client.
2. **Mechanism:** Compare the installed artifact with its source tag and SBOM.
   Focus on network configuration and components that process model input or
   output.
3. **Execution:** Verify the APK digest, inspect its bundled release-provenance
   record, and confirm the API origin against the public source tag.

**Evidence and flag placement:** `assets/provenance/release.json` in the
distributed APK contains the first half of the flag plus the exact source tag
and SBOM digest. The matching CycloneDX SBOM in that Forgejo tag contains the
second half in its release-reference property. The participant joins them into
one conventional flag. This requires both shipped application and code/SBOM
inspection while remaining ordinary static artifact content.

**Reset:** None. Public releases are immutable; participant downloads persist.

**Participant-equivalent QA:** Find the application repository from public
material, download and verify the APK, recover the provenance prefix with at
least one normal inspection method, follow its exact source tag/SBOM digest,
recover the suffix, assemble the flag, and confirm the endpoint and dependency
against both artifacts.

**Facilitation notes:** Distinguish setup trouble from challenge difficulty by
confirming that at least two APK-inspection tools work on Kali. If a participant
searches every library, ask which dependency actually handles model-facing
data. The security lesson is evidence correlation, not reverse-engineering
obscurity.

## `kep-m06-j`: Map The Orion Edge

**Difficulty / points:** Accessible / 100

**Mission context:** Cinder Typhoon now has names, domains, a client endpoint,
and public mail addresses. It needs to determine which live external services
can carry data or requests into Orion workflows.

**Starting knowledge:** The authorized external scan scope is explicit in the
mission. Results from `kep-m06-i` and `kep-m06-h` provide the shortest seed set,
but DNS and public service links make the operation independently startable.

**Discovery path:** DNS records, TLS certificates, the client API origin, and
published service addresses provide the complete seed set. Each live service
returns normal protocol metadata that identifies its role. A benign message to
the published partner-intake address produces a standards-compliant automated
reply whose headers identify the AI-assisted workflow.

**Participant surface and action:** Using DNS tools, Nmap, curl or a browser,
OpenSSL, and a mail client or swaks, the participant performs bounded discovery
against only the authorized domains. They inspect DNS, open ports, TLS names,
HTTP schemas and headers, and the automated reply to a benign intake message.

**Real mechanism:** PowerDNS, Caddy, a real API service, Stalwart mail,
and the intake agent expose their actual DNS, TLS, HTTP, SMTP, and mail-header
behavior. The operation does not rely on a fake port-scanning response or a
static network diagram.

**Observable result:** The participant can distinguish the public website,
partner preview API, mail boundary, partner intake, and a model-backed public
workflow. The preview service's OpenAPI schema and the intake reply both name
normal downstream processing components used later.

**Operational consequence:** The external surface map supplies the reachable
delivery paths and service identities used in capability preparation and
initial access. It also establishes a known-good baseline for later evasion and
infiltration attempts.

**ATLAS behavior:** `AML.T0006 Active Scanning`: the participant directly probes
victim systems through DNS, network, application, TLS, and mail interactions to
identify AI and AI-adjacent services.

**Training value:** Participants learn to extend ordinary external
reconnaissance to model APIs, agent-managed inboxes, and AI ingestion paths
while retaining protocol-level evidence.

**Ambiguity controls:** Every scan target comes from a prior in-world artifact or
certificate. The authorized scope is explicit. The services expose recognizable
DNS, TLS, HTTP, SMTP, and mail metadata, and multiple tools can retrieve it.
Participants do not need to guess virtual hosts or scan broad address ranges.

**Participant description:** Probe the authorized KeplerOps edge and identify
the live services that accept software, documents, mail, or model requests into
Orion workflows.

**Hints:**

1. **Orientation:** Begin with the domains, API origin, and public mail
   addresses already recovered. Do not expand beyond the mission's scope.
2. **Mechanism:** Ports alone are not enough. Compare DNS, TLS names, HTTP
   schemas and headers, and a benign automated-mail response.
3. **Execution:** Inspect the preview API's published OpenAPI document and the
   complete headers of the partner-intake reply.

**Evidence and flag placement:** The participant sends a benign Preview request
and a benign message to the published partner-intake address using the same
normal external case reference. The standards-compliant mail reply links the
ordinary public intake-status record, whose correlated Preview and mail events
contain the flag. Static OpenAPI and port enumeration alone cannot reach that
record.

**Reset:** Delete participant probe records and benign intake messages. DNS,
certificates, public schemas, and service configuration remain unchanged.

**Participant-equivalent QA:** From the public mission scope and any prior
artifacts, enumerate only authorized services, retrieve and inspect live
protocol metadata, send one benign Preview request and one benign intake
message with the same case reference, identify the two correlated normal
workflow events, and recover the flag from the intake-status record.

**Facilitation notes:** If a participant reports a service down, check DNS, TLS,
HTTP, and mail independently before diagnosing content. If they only produce an
Nmap list, ask what evidence distinguishes a normal web endpoint from an AI
ingestion path. The challenge is complete external characterization, not port
counting.

## Act 1 Calibration

| Operation | Difficulty | Primary interaction | New concept |
|---|---|---|---|
| Orion In The Open | Accessible | Browser and public documents | AI-focused technical OSINT and flag loop |
| The People Behind Orion | Accessible | Browser and identity artifacts | Evidence-backed human trust mapping |
| Evidence In The Client | Intermediate | Application repository and artifact tools | Client/source/SBOM/vulnerability correlation |
| Map The Orion Edge | Accessible | DNS, network, HTTP, TLS, and mail | AI-aware active service discovery |

Act 1 contains three Accessible operations and one Intermediate operation. It
introduces browser, flag submission, public repositories, terminal artifact
inspection, and bounded live-service probing. It contains no free-form prompt
challenge, hidden credential, custom code requirement, or Advanced/Expert gate.
