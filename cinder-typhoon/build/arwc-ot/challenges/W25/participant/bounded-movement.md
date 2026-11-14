# Cairn Reach bounded movement CRR-OP-W25-R1

Asset: `AST-CRR-017`
Controller project: `arwc-site`, revision 364
Authorized channel: local FUXA HMI
Authorized mode: manual position

The normal challenge baseline is outlet A at 20 percent and outlet B at 20
percent. Measured flow is approximately 0.10 m³/s per outlet and 0.20 m³/s in
total. Confirm the live baseline and the movement conditions before acting.

For `CRR-W25-MOVE-01`, apply one complete FUXA request with outlet A at 30
percent, outlet B at 10 percent, manual mode, and proposed total flow 0.20 m³/s.
The total-flow field remains part of the complete request even though manual mode
uses the two position settings. Do not use the dispatcher, OpenPLC forcing,
program upload, or any alternate write path.

The PLC must see and accept the new sequence under HMI ownership. Acceptance is
not proof of actuation: observe both outlet permissives, measured positions,
measured flows, and native history until the movement has settled.

Restore the site through a second complete FUXA request with outlet A at 20
percent, outlet B at 20 percent, manual mode, and proposed total flow 0.20 m³/s.
Finish only when the second sequence is accepted, both outlets have settled,
measured total flow is approximately 0.20 m³/s, field data is healthy, both
travel faults are clear, and the historian contains good-quality movement and
restoration samples.

The movement may proceed only when field I/O is healthy; both drives are
available and selected remote; low-level protection, operator stop, and travel
faults are clear; the controller is armed; and both outlet permissives are
available. Stop and report the product condition if any of those facts is false.
