# KeplerOps QA challenge walkthrough

This is the spoiler-heavy QA guide for completing and verifying the 132
issue-62 in-scope KeplerOps challenges. It links the participant-facing instructions,
expected results, receipt steps, and negative controls used for the manual
participant-equivalent walkthrough.

Do not give this guide to participants in a blind playtest. Use the
[participant start guide](../playtester-guide/participant-start.md) for normal
participant onboarding.

## Enter the QA range

1. Open the [Shifter CTF login](https://gcp.shifter.keplerops.com/ctf/login/).
2. Sign in with the QA participant credentials supplied by the organizer.
3. Complete the password-change prompt if Shifter presents one.
4. Open **Range**, find the Kali workstation, and select **Open**.
5. Use the browser UI or Kali terminal exactly as each walkthrough instructs.
   Do not replace a UI step with curl unless the walkthrough says the terminal
   is the participant path for that challenge.
6. Use Shifter's **Challenges** page to confirm challenge visibility, inspect
   hints, and submit the receipt produced by the range.

Some detailed walkthroughs were authored against the same Kali participant
workstation before its current Shifter integration. Where they say **Kasm**,
use the Kali desktop opened from Shifter through Guacamole. Where historical
text says **CTFd**, use Shifter's **Challenges** page.

## Run the challenges

Work through both linked files where a module has separate core and expansion
instructions. Together they cover all 132 issue-62 in-scope challenges. The
unimplemented hardware rows `kep-m06-m` and `kep-m08-i` are authored catalog
entries but are not part of this participant-only pass.

| Module | Challenges | Participant-path walkthroughs | QA checklist |
| --- | ---: | --- | --- |
| 01 - Agent Control | 10 | [All challenges](module-01-agent-control.md) | Included in walkthrough |
| 02 - Model Evasion | 12 | [All challenges](module-02-model-evasion.md) | [Checklist](../playtester-guide/challenges/module-02-model-evasion/index.md) |
| 03 - Context Poisoning | 11 | [Core](module-03-context-poisoning.md), [expansion](module-03-full-atlas-expansion.md) | [Checklist](../playtester-guide/challenges/module-03-context-poisoning/index.md) |
| 04 - Model Secrets | 13 | [Core](module-04-model-secrets.md), [expansion](module-04-full-atlas-expansion.md) | [Checklist](../playtester-guide/challenges/module-04-model-secrets/index.md) |
| 05 - Agent Persistence | 17 | [Core](module-05-agent-persistence.md), [expansion](module-05-full-atlas-expansion.md) | [Checklist](../playtester-guide/challenges/module-05-agent-persistence/index.md) |
| 06 - Adversarial Input | 21 | [Core](module-06-adversarial-input.md), [expansion](module-06-full-atlas-expansion.md) | [Checklist](../playtester-guide/challenges/module-06-adversarial-input/index.md) |
| 07 - Training Poisoning | 9 | [Core](module-07-training-poisoning.md), [expansion](module-07-full-atlas-expansion.md) | [Checklist](../playtester-guide/challenges/module-07-training-poisoning/index.md) |
| 08 - Model Extraction | 10 | [Core](module-08-model-extraction.md), [expansion](module-08-full-atlas-expansion.md) | [Checklist](../playtester-guide/challenges/module-08-model-extraction/index.md) |
| 09 - Model Backdoor | 12 | [Core](module-09-model-backdoor.md), [expansion](module-09-full-atlas-expansion.md) | [Checklist](../playtester-guide/challenges/module-09-model-backdoor/index.md) |
| 10 - AI Capstone | 17 | [Core](module-10-ai-capstone.md), [expansion](module-10-full-atlas-expansion.md) | [Checklist](../playtester-guide/challenges/module-10-ai-capstone/index.md) |
| **Total** | **132** | | |

The module walkthroughs above contain the actual participant actions. The
[all-challenge index](../playtester-guide/challenges/README.md) remains a
secondary navigation surface for generated challenge records and should not
override a module walkthrough.

## Verify each challenge

For each challenge:

1. Confirm it appears in Shifter and that its authored hints open.
2. Complete any listed prerequisites in the same range and reset generation.
3. Follow the detailed walkthrough from the Kali participant surface.
4. Compare the visible response with the documented expected result.
5. Request the receipt only after the qualifying action succeeds.
6. Verify the receipt through the participant-visible proof route when the
   walkthrough provides one.
7. Submit the receipt to the matching Shifter challenge and confirm the score
   changes exactly once.
8. Run the documented negative control when it will not contaminate a later
   challenge.
9. Record the result in the challenge's QA capture template.

A receipt issued before its qualifying evidence, accepted for another
participant or range, accepted twice for score, or accepted after a reset is a
defect.

## Record defects

For every failure, record:

- challenge identifier and title;
- participant username and assigned range;
- approximate time and current reset generation, when visible;
- exact step and action;
- visible response or error;
- hints used;
- whether the in-range action succeeded;
- whether a receipt was issued, verified, and accepted by Shifter;
- whether the failure persists on a clean retry.

Do not use GCP, management-plane SSH, Terraform, database or proof internals,
generated service credentials, or operator-only files to complete a challenge.
Do not reset or repair the range unless the playtest coordinator asks you to.

## Completion

A QA pass is complete when all 132 in-scope checklist entries have a result, every
successful challenge has a verified and scored receipt, every required
negative control has behaved as documented, and every failure has a
reproducible defect record.
