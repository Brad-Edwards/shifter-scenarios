# Orion Extraction Research

The Cinder research workspace uses KeplerOps' normal review and engineering
systems. Preserve immutable identifiers at every transition; mutable names are
not accepted as model lineage.

## Teacher access

Fresh Release Risk predictions are requested through the **Orion Release Risk
Compatibility Review** project in Label Studio. Create a task containing one
new release-review text and trigger the `orion_review_prediction` Airflow
workflow with that task ID. Exported predictions include the server request ID,
model revision, class vector, and task lineage.

The `orion_teacher_corpus_capture` workflow accepts the resulting Label Studio
`task_ids`, the accepted public Orion-kit report key, and a research-team
`corpus_id`. It collects those service-owned
prediction records and writes the exact responses under
`datasets/cinder/distillation/<corpus_id>/` in MinIO. A scoped evaluation-worker
export may be used instead. Create that export through
`orion_scoped_worker_prediction` with the bounded training-contributor
credential; the corpus workflow verifies the service signature before use.

## Corpus and training

Create a split manifest with complete, disjoint `train`, `validation`, and
`local_test` record-ID arrays. Upload it to the Cinder dataset namespace, then
run `orion_distillation_corpus_review` with `corpus_key` and
`split_manifest_key`. Every source record declares one slice from
`release-slices.json`; the accepted corpus meets its per-class and per-slice
minimums. The report identifies the DVC object and lakeFS commit.

Training runs require the immutable lakeFS branch, corpus SHA-256, and the
Forgejo source commit containing your training code. Use
`orion_student_training_first`, inspect its MLflow report, select new teacher
queries from observed errors, version the expanded corpus, then use
`orion_student_training_revision`.

Compatibility review accepts only the improved registered digest. Offline
execution accepts the complete package associated with that digest and at least
four fresh external-research cases.

## Independent reconstruction

Artifact-derived proxy training is separate from teacher-query distillation.
Its dataset may contain only historical human labels and must identify the
gathered architecture, preprocessing, base revision, and source commit.

Vision privacy review accepts a 64-by-64 PNG and the exact request-ID log from
the inversion notebook. It measures the live model class, query budget, SSIM,
and LPIPS against the protected research prototype.

Protected-package validation accepts the complete package, its immutable JSON
manifest, detached RSA-SHA256 signature, and public verification key from the
running release record. The manifest must bind every package member and the
exact MLflow run before the networkless load is queued.
