from __future__ import annotations

from model_extraction import CHALLENGE_IDS as MODEL_EXTRACTION_CHALLENGE_IDS


EXTRACTION_CHALLENGE_IDS = tuple(sorted(MODEL_EXTRACTION_CHALLENGE_IDS))

EXTRACTION_EVIDENCE = {
    "kep-m08-a": ("teacher_corpus_collected", "ev-teacher-corpus"),
    "kep-m08-b": ("teacher_corpus_covered", "ev-corpus-coverage"),
    "kep-m08-c": ("proxy_diagnostic_fidelity", "ev-proxy-diagnostic"),
    "kep-m08-d": ("proxy_budgeted_fidelity", "ev-proxy-budgeted"),
    "kep-m08-e": ("proxy_private_fidelity", "ev-proxy-private"),
    "kep-m08-f": ("proxy_fidelity_verdict", "ev-proxy-fidelity"),
    "kep-m08-g": ("gathered_artifact_proxy_08", "ev-gathered-artifact-proxy"),
    "kep-m08-h": ("model_inversion_08", "ev-model-inversion"),
    "kep-m08-i": ("physical_sensor_evasion_08", "ev-physical-sensor-evasion"),
    "kep-m08-j": ("full_model_access_08", "ev-full-model-access"),
    "kep-m08-k": ("product_side_channel_08", "ev-product-side-channel"),
}
