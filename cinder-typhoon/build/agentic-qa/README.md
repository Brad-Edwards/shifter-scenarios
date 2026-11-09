# Participant-view agentic QA

This operator-only gate validates the credential-free report for issue #328.
The execution and trust-boundary design is in
[`docs/design/agentic-qa.md`](../../docs/design/agentic-qa.md).

The final report contains one result for every published challenge card. Raw
agent messages, participant commands, service responses, credentials, payloads,
and target artifacts remain in the approved operator evidence directory.

Prepare each operation with `prepare.py`. Reuse one opaque campaign ID for the
complete run. Reuse one participant-container reset identity within each phase
unless an operation is an explicit reset boundary. Give every operation a
distinct session ID. KeplerOps must finish before ARWC starts from its earned
transition.

Assemble the content-free operation exports with `assemble.py`. Pass every
operation export, the candidate-bound reliability report, and each finding.
Use `--reset-boundary PHASE:OPERATION` for each intentional reset identity
change. Use `--reliability-substitute CARD` only when a failed exploratory card
must use its passing candidate-bound known-solution assertion instead. The
substitution contains no participant score or exploratory attempt history.

Validate the committed report with:

```sh
python3 cinder-typhoon/build/agentic-qa/validate.py
```

Run the focused fail-closed tests with:

```sh
python3 -m unittest \
  cinder-typhoon/tests/test_agentic_qa_assemble.py \
  cinder-typhoon/tests/test_agentic_qa_proxy.py \
  cinder-typhoon/tests/test_agentic_qa_report.py \
  -v
```

