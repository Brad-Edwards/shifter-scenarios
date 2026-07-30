# Module 06 full-ATLAS expansion walkthrough

This walkthrough covers the source-implemented Module 06 expansion challenges
`kep-m06-g` through `kep-m06-v`.

Use the participant-visible surfaces named in the challenge listing to create
real range state first, then submit digest-safe component evidence to
`/v1/adversarial/expansion/proofs`. The gateway returns the required evidence
kinds from `/v1/adversarial/expansion/challenges`; a receipt is issued only
after the proof API records a passed event for the same participant, range, and
reset generation.

- `kep-m06-g` through `kep-m06-j`: collect research, public web, and active scan
  observations, then submit independent source or scan evidence and the
  reproduced result or live service fingerprint.
- `kep-m06-k` through `kep-m06-p`: acquire range-local datasets, models,
  workspaces, domains, proxy accounts, attack tools, or generative capability
  outputs, then submit digest-bound acquisition, execution, and downstream
  model-probe evidence.
- `kep-m06-q` through `kep-m06-t`: build or generate participant-owned attack
  artifacts, prove source/model/media provenance, and join them to dry-run,
  retrieval, transfer, or classifier evidence.
- `kep-m06-u` and `kep-m06-v`: run only the contained disposable worker or
  vulnerable policy-control surface, prove model-originated commands or exploit
  requests, and verify the bounded marker, paired result, or restored reset
  state. Do not use host, cloud, or management-plane actions as participant
  proof.

## Submit one expansion proof

Complete the participant-facing action described by the matching
[challenge checklist](../playtester-guide/challenges/module-06-adversarial-input/index.md),
then submit its component evidence from the Kali terminal. Set
`CHALLENGE_ID` to exactly one of:

```bash
export TOKEN
export CHALLENGE_ID=kep-m06-h
# kep-m06-g kep-m06-h kep-m06-i kep-m06-j
# kep-m06-k kep-m06-l kep-m06-m kep-m06-n
# kep-m06-o kep-m06-p kep-m06-q kep-m06-r
# kep-m06-s kep-m06-t kep-m06-u kep-m06-v
```

Use a fresh workflow and evidence object set for each challenge:

```bash
python3 - <<'PY'
import hashlib
import json
import os
import ssl
import time
import urllib.request

challenge_id = os.environ["CHALLENGE_ID"]
token = os.environ["TOKEN"]
gateway = "https://inference-gateway.keplerops.lab"
context = ssl.create_default_context(cafile="/run/tls/ca.crt")

def request(path, *, payload=None):
    body = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        gateway + path,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, context=context) as response:
        return json.loads(response.read())

listing = request("/v1/adversarial/expansion/challenges")
required = listing["required_evidence"][challenge_id]
nonce = str(time.time_ns())

def status_for(kind):
    if kind == "reset-restored":
        return "restored"
    if any(word in kind for word in ("execution", "invocation", "command", "state-change")):
        return "executed"
    if any(word in kind for word in (
        "result", "pass", "marker", "decision", "delta", "threshold",
        "inference", "probe", "fingerprint", "success",
    )):
        return "passed"
    return "selected"

evidence = []
for index, kind in enumerate(required):
    object_id = f"{challenge_id}:{kind}:qa:{nonce}:{index}"
    digest_input = json.dumps(
        {
            "challenge_id": challenge_id,
            "kind": kind,
            "object_id": object_id,
            "participant_surface": "shifter-guacamole-kali",
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    evidence.append({
        "kind": kind,
        "object_id": object_id,
        "digest": "sha256:" + hashlib.sha256(digest_input).hexdigest(),
        "status": status_for(kind),
    })

result = request(
    "/v1/adversarial/expansion/proofs",
    payload={
        "challenge_id": challenge_id,
        "workflow_id": f"qa-{challenge_id}-{nonce}",
        "evidence": evidence,
        "participant_interface": "python",
        "assistance_mode": "none",
    },
)
print(json.dumps(result, indent=2))
assert result["objective_status"] == "passed", result
PY
```

The proof must report the selected `challenge_id`, `objective_status: passed`,
`failure_class: passed`, and the complete required-kind set. Reusing one digest
for several evidence objects must fail with `digest-lineage-collapsed`.

Request the challenge's receipt using the flag id shown in its checklist. For
example:

```bash
curl --fail --silent --show-error -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{}' \
  "$GATEWAY/v1/adversarial/receipts/flag-open-vulnerability-research" \
  | python3 -m json.tool
```

Pre-playtest validation is intentionally pragmatic: one positive path, one
representative negative control, and one scoped reset/replay for the mutable
owner before playtest hardening.
