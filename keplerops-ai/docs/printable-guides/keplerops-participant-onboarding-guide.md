# KeplerOps Participant Onboarding Guide

This is the start-here guide for the KeplerOps AI Systems event. It tells you
how to get in, what kind of CTF this is, how flags work, and what to do in your
first 30 minutes.

## Get In

1. Open the Shifter CTF login at <https://aisf.keplerops.com/ctf/login/>. The trailing slash is required.
2. Get your participant username and temporary password from the organizers.
3. Sign in with those credentials.
4. If Shifter asks you to choose a new password, do that before continuing.
5. Open **Range** in Shifter.
6. Find your Kali workstation and select **Open**.
7. Open Shifter's **Challenges** page in another browser tab.

Your assigned range is private to your participant account. Do not use another
participant's range or credentials.

## What You Are Walking Into

KeplerOps is an AI-security capture-the-flag exercise set inside a simulated AI
company. You are operating from a Kali workstation inside a working lab
environment.

You will interact with AI assistants, model services, internal web apps,
tickets, registries, datasets, notebooks, release workflows, and security
controls. The challenges are not trivia questions. Most of them ask you to make
or find something inside the range, then submit the flag that the range gives
you.

You do not need to understand the whole lab before starting. Begin with one
challenge, follow the objective literally, and learn the environment as you go.

## How Flags Work

Each challenge is solved when Shifter accepts the flag for that challenge.

Most flags come from doing something successfully inside the KeplerOps range.
You usually will not know the flag in advance. The range gives it to you after
the right action, discovery, workflow, or evidence exists.

When you see a value like `FLAG{...}`, copy it into the matching Shifter
challenge and submit it. If Shifter accepts it, you are done with that
challenge.

Do not spend time guessing flags. The fastest path is to make the system
produce the flag.

## Your First 30 Minutes

### 0-5 Minutes: Access

1. Sign in to Shifter.
2. Open your Kali workstation from the **Range** page.
3. Confirm that the Kali desktop loads.
4. Open the Shifter **Challenges** page.
5. Keep both the Kali desktop and the challenge board available.

### 5-10 Minutes: Orient

1. Launch Chromium if it is not already open.
2. Look at the first few challenge categories.
3. Notice that you can use the browser, terminal, curl, Python, and range-local
   applications.
4. Do not try to map the whole environment yet.

The important idea is simple: read a challenge, interact with the relevant
system, get a flag, submit it in Shifter.

### 10-20 Minutes: Pick A Starter Challenge

Start with an early challenge in one of these Shifter categories:

- AI Agent Security;
- Model Security;
- Data and Retrieval;
- Model Privacy.

Those are the category names shown in the challenge list. If organizers call a
module by a different classroom name, use the category name you see in Shifter
when choosing the challenge.

Pick a challenge with no prerequisite if possible. Read the objective and the
first hint. Identify the main system it mentions, then try the smallest action
that seems relevant.

### 20-30 Minutes: Learn The Loop

If you get a `FLAG{...}` value, submit it in Shifter immediately.

If you do not get a flag yet, write down:

- the challenge ID;
- what system you touched;
- what you tried;
- what result or error you saw;
- what you expected to happen.

Then either try one more small step, ask an organizer, or move to another
starter challenge.

## How To Think About Solves

Most challenges are not riddles. They expect you to interact with a system,
cause or discover something specific, and then get a flag from that result.

If you are stuck, ask:

- What action is this challenge asking me to cause, find, compare, or prove?
- Which system would naturally show that result?
- Did I complete any prerequisite challenge first?
- Did I submit the flag to the matching challenge in Shifter?

Keep useful identifiers as you work: issue IDs, conversation IDs, model names,
artifact digests, run IDs, receipt IDs, file paths, and timestamps. These are
often helpful when retracing your steps or asking for help.

## Tools You Can Use

You may use:

- Shifter objectives and hints;
- the Kali desktop;
- Chromium;
- terminal commands;
- curl;
- Python;
- applications and documentation inside the range.

You do not need an autonomous offensive agent to begin.

## Scope

You may attack:

- services under `*.keplerops.lab`;
- the contained exfiltration sink;
- other targets explicitly named by a Shifter challenge.

Public internet access is available for passive vulnerability research. Do not
attack external systems, use external callback infrastructure, or target
commercial model providers.

Do not use:

- GCP, Terraform, or other infrastructure control planes;
- management-plane SSH or operator interfaces;
- proof database internals or receipt signing material;
- scenario source code or static flag extraction;
- another participant's account, range, receipts, or credentials.

## If You Get Stuck

1. Re-read the objective.
2. Open the next Shifter hint if you need it.
3. Check whether the challenge has prerequisites.
4. Try a smaller version of the action first.
5. Move to another starter challenge if you are blocked.
6. Ask an organizer for help with the challenge ID, what you tried, and the
   visible result or error.

Do not repair range infrastructure yourself. If something looks broken, report
it and continue with another challenge when possible.

## Good Help Requests

When asking for help, include:

- the challenge identifier and title;
- what you attempted;
- the visible result or error;
- the approximate time;
- whether you used a hint or reset;
- any relevant receipt ID, run ID, issue ID, digest, or screenshot.

Keep secrets and credentials out of shared channels unless an organizer
explicitly asks for a safe handoff.
