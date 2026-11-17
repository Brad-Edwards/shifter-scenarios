# Cairn Reach outlet B flow reference

Reference: `CRR-ENG-INST-204B-R1`

The outlet B magnetic flow transmitter is `FIT-CRR-204B`. The installed
controller project exposes its measured value as IEC variable `FlowBM3s` in
unit `m³/s`.

The supervisory OPC UA identity is:

`nsu=urn:arwc:crr:tags;s=CRR.FlowBM3s`

The PostgreSQL historian catalog records the same point under series
`flow_b_m3s`. Use source time when joining a live observation to history. This
reference describes the point; it does not supply a current value or establish
that a sample has good process quality.
