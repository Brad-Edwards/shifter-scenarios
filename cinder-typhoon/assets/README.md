# Scenario assets

[narrative/](narrative/README.md) contains the first workplace story collection:
authored correspondence, company records, contact directories, calendar items,
and their native RAE source artifacts. It is separate from records required to
complete individual challenges.

Challenge-owned data requirements remain in the
[technical data contract](../docs/design/technical-data-contract.md) and individual
challenge technical sections. Further bespoke source, service files, synthetic
data, and briefing material belong under this directory as they are authored.

[Build Operations records](keplerops/build-operations/README.md) now contain the
maintained diagnostic request reference and protected runner note for K09.
Their exact text is bound as native file content on the CI node. They are not
copied into the workplace library or supplied developer workspace.

[Training records](training/README.md) contain the exact tank captures, report
replay, operating guide, private initial tank state, and independent formatter
contract. Two native content modules bind their bytes to exact node paths;
the README distinguishes published documents from service-private state.
