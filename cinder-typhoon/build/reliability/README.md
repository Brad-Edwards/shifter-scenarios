# Single-participant reliability qualification

This qualification checks one Cinder participant range against one immutable
candidate. It covers the Training, KeplerOps, and ARWC golden hosts. It does
not measure multi-range capacity or participant discovery.

## Qualification sequence

1. Verify the candidate and release-manifest digests.
2. Restore each phase to its authored pristine state.
3. Record the participant surface and initial service state.
4. Run the Training known solution.
5. Run the KeplerOps diagnostic delivery and verify the earned ARWC transition.
6. Restart the long-running services and verify recovery.
7. Restart each host and verify recovery and retained transition state.
8. Run the ARWC ending from the earned diagnostic transition.
9. Restore each phase twice. Compare both participant surfaces and initial
   service states.
10. Record host resources, failed units, OOM events, service restarts, and all
    measured times.

The limits in `thresholds.json` are fixed before the acceptance run starts.
The committed report must pass `validate.py` against those limits and the
current candidate and release records.

## Evidence and trust boundaries

```text
candidate.json + release/manifest.json + thresholds.json
                         |
                         v
operator wrappers ---> GCP golden hosts ---> operator-only raw reports
                         |                         |
                         +---- aggregate facts ---+
                                      |
                                      v
                                report.json
```

The golden hosts are test targets. They do not write repository evidence.
The operator collects raw reports under remote `/var/tmp` paths and local
`.operator` paths. Those files can contain operational detail and stay out of
Git. The committed report contains only public deployment names, counts,
times, statuses, and SHA-256 bindings. It must not contain credentials, request
or response content, environment values, private paths, or raw logs.

Service recovery restarts all long-running Compose services. The KeplerOps
`k-dev-seed` service is an intentional one-shot service. A successful pristine
state requires it to exit with code 0. Host recovery restarts each golden VM
and waits for the same phase service contract.

Each pristine-reset surface digest identifies the authored participant-surface
contract after the live unprivileged surface check passes. The digest does not
hash the raw observation. This distinction is required because a restore
rotates generated certificates and authentication material while the authored
participant-visible paths, permissions, ownership, tools, DNS, listeners, and
access controls remain the same. The live check still fails on every surface
change outside that authored contract.

## Limits

The time limits include readiness checks, not image builds. The resource
limits are guardrails for one participant range. Issue #233 owns event-scale
capacity and concurrency.

- Zero unexpected container restarts, failed system units, and OOM events.
- At most 180 seconds for pristine startup and service recovery.
- At most 300 seconds for host recovery.
- At least 256 MiB of available memory and 2 GiB of available root disk.
- A one-minute load average no greater than twice the host vCPU count.

## Validation

Run the focused validator and its mutation tests:

```sh
python3 cinder-typhoon/build/reliability/validate.py
python3 -m unittest cinder-typhoon/tests/test_reliability_report.py -v
```
