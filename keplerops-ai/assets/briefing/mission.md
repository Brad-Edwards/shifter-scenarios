# KeplerOps AI Systems

You are testing an AI security range from the participant point of view. Use
your Shifter account only to reach the event, launch your assigned range, read
the challenges, and submit receipts for scoring. The KeplerOps lab applications
inside the range use their own synthetic lab credentials.

## Start In Shifter

1. Sign in to Shifter with the event account you were given.
2. Open the KeplerOps AI Systems CTF event.
3. Use the event dashboard as your home base. It should show the getting-started
   material, challenge list, hints, score, and range launch controls.
4. Launch your assigned range and open the Kali workstation.

If Shifter asks you to choose a new password, set it for your Shifter event
account. That password does not change any in-range KeplerOps lab account.

## Start In The Range

Open Chromium on Kali and go to:

```text
https://inference-gateway.keplerops.lab/agent-control
```

Use these synthetic KeplerOps lab credentials when a KeplerOps application asks
you to sign in:

```text
Username: operator
Password: KeplerOps-Participant-355!
```

The browser home page should also point at the KeplerOps lab. If it does not,
enter the URL above manually.

## Challenge Flow

Work from the Shifter challenge page, not from this file alone. Shifter is where
you read challenge text, request hints, submit receipts, and see whether a
challenge is solved.

For Module 1, start in the Agent Control Lab at the URL above. The first
challenge, `kep-m01-a`, is solved by making a risky tool request and seeing the
system deny it on record. A denial with a receipt is success for that challenge.

Most challenges require this loop:

1. Perform the required action in the KeplerOps lab UI or Kali terminal.
2. Confirm the in-range service shows a receipt or objective status.
3. Submit the receipt text in Shifter for the matching challenge.
4. Use hints in Shifter if the next step is unclear.

## Boundaries

Attack only `*.keplerops.lab` and the in-range exfiltration sink. Do not attack
Shifter, GCP, cloud metadata, commercial model providers, or any public
internet service. Internet access is provided so you can research techniques and
vulnerabilities, not as a target surface.

If a service appears broken, report the challenge id, range id, what you tried,
and the visible error. Do not repair range infrastructure from inside the
participant environment.