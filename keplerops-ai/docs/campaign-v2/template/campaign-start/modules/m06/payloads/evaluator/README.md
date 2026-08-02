# Cinder Independent Evaluation

This private repository definition runs Cinder's independent artifact and
capability checks. Operators submit exact bytes and manifests to the
`operations/submissions` bucket. The scheduled evaluator reacquires those
bytes, exercises the declared live systems, and publishes accepted records to
the operation's ordinary report, workspace, registry, or public-status path.

The evaluation repository and runner identity are independent of Cinder operators.
Operator repositories may contain harnesses and submitted workloads, but cannot
change these acceptance routines or read their release-reference material.
