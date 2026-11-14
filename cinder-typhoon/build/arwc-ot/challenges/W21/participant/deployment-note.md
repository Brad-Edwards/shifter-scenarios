# CRR-PLC-COM-364 commissioning note

The Cairn Reach outlet controller was accepted as native OpenPLC project
`arwc-site`, revision `364`, with program `main` scheduled every `T#100ms`.
The accepted engineering target is `OpenPLC Runtime v4` at `172.29.63.20`.

Commissioning acceptance required all of the following at the same time:

- the editor's locally compiled program identity matched the runtime's reported
  program identity;
- the runtime was connected and scanning;
- live variable `ProjectRevision` reported `364` through the native debugger;
- no force was left active.

Re-establish those conditions from the supplied project and the normal OpenPLC
debug and Runtime Status views. A successful connection alone is insufficient:
the program identity, running state, and live revision must agree. Do not accept
an upload prompt; this task observes the installed program and does not replace
it.
