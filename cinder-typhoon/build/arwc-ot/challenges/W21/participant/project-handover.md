# Cairn Reach controller project handover

Asset: `AST-CRR-017`
Controller: Cairn Reach outlet controller
Participant project: `~/CairnReach/controller`
Engineering product: OpenPLC Editor 4.3.4
Runtime target: OpenPLC Runtime v4 at `172.29.63.20`

The handed-over directory is the actual native project copied from the range's
image-owned commissioning source. Open the project in OpenPLC Editor and review:

- `project.json` for the resource and scheduled task;
- `pous/programs/main.fbd` for the main program and declared process variables;
- `devices/configuration.json` for the selected runtime target and address;
- `devices/remote/CairnReachIO.json` for the real Modbus TCP device binding.

Record the project name, main program, language, scheduled task interval,
runtime target and address, and the declared `ProjectRevision`. Do not upload,
start, stop, or force anything. A local project label is not proof that the same
compiled program is running.
