# Cinder Typhoon Attacker Workbench

## Purpose

The participant begins with credible attacker-controlled resources, not a
KeplerOps account or a challenge console. The workbench supports reconnaissance,
software development, AI-assisted attack preparation, deepfake production,
mail, and ordinary security testing throughout the campaign.

All participant tools are open source. Participants do not need to supply an
AI subscription or cloud account.

## Participant Workstation

Each range provides a Kali workstation with:

- Chromium with unrestricted Internet access and the public KeplerOps site as
  its initial page;
- a normal terminal with a working TTY;
- OpenCode as the primary coding-agent harness;
- Python, Git, curl, jq, common network and web assessment tools, mail tools,
  archive and hashing tools, and the ML clients required by the campaign;
- a preconfigured attacker-controlled email account;
- a working directory owned by the participant; and
- a concise `MISSION.md` that states the strategic objective, scope, public
  start URL, attacker resources, and how to open Shifter objectives.

The workstation contains no walkthrough artifacts, previous participant state,
KeplerOps credentials, hidden API tokens, proof utilities, or test harnesses.

## Shared GLM 5.2 Access

OpenCode is configured with one custom OpenAI-compatible provider named
`cinder-workbench`. Its only advertised model is GLM 5.2. The provider base URL
is a shared event endpoint backed by the enabled Vertex model.

The endpoint is an event utility, not a victim KeplerOps service. It does not
count toward compromise, does not see hidden challenge state, and does not
perform operations on the participant's behalf. It provides the same general
model capability a real operator might use for research, code, prompts, and
content development.

The initial implementation deliberately has no participant query budget,
provider-selection framework, or per-range model deployment. It only needs:

- a working OpenAI-compatible chat-completions surface;
- GLM 5.2 behind it;
- one scoped event credential installed for the participant environment;
- participant separation in request logging; and
- enough error feedback to distinguish provider failure from a bad prompt.

OpenCode supports custom OpenAI-compatible providers through its documented
provider `baseURL` configuration. `curl` and a small documented Python example
provide fallback access to the same endpoint.

## Attacker Mail

Each participant receives an attacker-controlled mailbox on a range-only
external domain that is visibly separate from KeplerOps. The account is already
configured in a normal webmail or desktop mail client. Its credential is
attacker infrastructure and may be stated in the mission material.

The mailbox must support:

- composing messages manually;
- attachments with preserved bytes and MIME metadata;
- SMTP delivery into the KeplerOps mail boundary;
- receiving employee replies;
- multi-message conversations;
- viewing headers and downloading attachments; and
- isolation from other participants.

KeplerOps employee mailboxes and recipient automation use the same real mail
state. A challenge API cannot send, read, or answer the message on the
participant's behalf.

## Deepfake Capability

The workbench must include an OSS pipeline capable of creating a genuine
synthetic impersonation, not a generic generated image.

The simplest acceptable participant workflow is:

1. locate victim-provided public image and audio or video material for a trusted
   KeplerOps person;
2. write or generate a target-specific script with GLM 5.2;
3. synthesize or clone speech with an OSS voice model;
4. animate or lip-sync the trusted person's public image with OSS software;
5. inspect and export the resulting audio or video file; and
6. attach those exact bytes to the participant-composed phishing message.

The initial implementation should use a working OSS voice and talking-head
pipeline selected during the enterprise build spike. OpenVoice plus
LivePortrait is the preferred starting combination because it separates voice
generation from face animation and produces a normal media artifact. The build
must verify the licenses of both code and required weights before admission.
If a required checkpoint is not redistributable for this event, replace it with
another OSS checkpoint rather than silently converting the operation into a
generic image-generation task.

The phishing evidence joins the participant-created media digest, message
attachment digest, mail delivery, target conversation, and resulting access.
The range does not grade visual quality with an opaque beauty score. The target
workflow evaluates whether the message uses the expected identity and context,
whether the delivered attachment was produced by the admitted deepfake
pipeline, and whether the participant completes the social-engineering
conversation.

## Internet Access

Participants may research vulnerabilities, documentation, models, and tooling
on the public Internet. Egress is normal workstation egress and is not routed
through the KeplerOps victim network.

Event rules prohibit attacking Internet systems, using real stolen data, or
sending range phishing outside the provided range mail domains. The mail
boundary rejects external recipients so an accidental message cannot leave the
exercise.

## Participant Experience Acceptance

Before the enterprise baseline is frozen, a participant-equivalent check must
prove that a fresh workstation can:

1. launch Chromium and browse both the Internet and public KeplerOps pages;
2. launch a working interactive terminal;
3. start OpenCode and receive a GLM 5.2 response;
4. call the same model through curl or Python;
5. compose, send, receive, and reply to a range email with an attachment;
6. create and play a deepfake media artifact through the admitted OSS pipeline;
7. clone a public repository and install documented participant dependencies;
   and
8. preserve files and session state across an ordinary workstation reconnect.

These are enterprise-baseline tests. They must pass before challenge weaknesses
are layered onto the environment.

## Deferred Optimization

Capacity tuning, provider failover, inference caching, autoscaling, detailed
cost controls, and alternate model support are explicitly deferred. The first
requirement is a working shared GLM 5.2 service that the participant can use
through OpenCode and ordinary API clients.
