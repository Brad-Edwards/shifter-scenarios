# KeplerOps AI Systems playtest

KeplerOps is an AI-security CTF set inside a working frontier AI laboratory.
You will attack the lab from a dedicated Kali workstation, complete challenges,
and submit objective receipts in Shifter.

## Sign in

1. Open the [Shifter CTF login](https://gcp.shifter.keplerops.com/ctf/login/).
2. Sign in with the participant username and temporary password supplied by the
   organizer.
3. If Shifter asks you to choose a new password, do that before continuing.
4. Open **Range** in Shifter.
5. Find the Kali workstation and select **Open**. Shifter opens the desktop
   through Guacamole.

Your assigned range is private to your participant account. Do not use another
participant's range or credentials.

## Enter the lab

Launch Chromium from the Kali desktop. It should open the KeplerOps Agent
Control portal automatically. If it does not, open:

<https://inference-gateway.keplerops.lab/agent-control>

The Agent Control and module pages use a separate range-local participant
session from Shifter. Sign in there with the lab participant credentials supplied
for the range handoff. Do not use the `EVALUATION-READER` notebook/Airflow
account for challenge APIs; it is scoped to audit workspaces and is not a
gateway participant session.

For browser playtesting, signing in sets the `keplerops_session` cookie used by
the module pages. For terminal-based QA walkthroughs that require
`/tmp/kep-token`, obtain the token through the same gateway login flow and keep
it local to the workstation; do not print it in reports or issue comments.

The desktop also contains `MISSION.md`, which summarizes the mission and range
rules.

Use Shifter's **Challenges** page to read objectives, open hints, and submit the
objective receipts produced by the range. Challenges do not have to be
completed in numerical order.

Good starting areas are:

- agent control;
- model evasion;
- retrieval and context poisoning;
- model-secret and privacy extraction.

You do not need an autonomous offensive agent to begin. You may work through
the browser, terminal, curl, Python, and the applications and documentation
available inside the range.

## Scope

You may attack:

- services under `*.keplerops.lab`;
- the contained exfiltration sink;
- other targets explicitly identified by a Shifter challenge.

Public internet access is available for passive vulnerability research. Do not
attack external systems, use external callback infrastructure, or target
commercial model providers.

Do not use:

- GCP, Terraform, or other infrastructure control planes;
- management-plane SSH or operator interfaces;
- proof database internals or receipt signing material;
- scenario source code or static flag extraction;
- another participant's account, range, receipts, or credentials.

## Playtest feedback

This is a playtest. Record confusing instructions, broken links, unexpected
shortcuts, and actions that appear successful but do not produce credit.

For a suspected defect, send the organizer:

- the challenge identifier and title;
- what you attempted;
- the visible result or error;
- the approximate time;
- whether you used a hint or reset.

Do not repair range infrastructure yourself. Continue with another challenge
when possible.
