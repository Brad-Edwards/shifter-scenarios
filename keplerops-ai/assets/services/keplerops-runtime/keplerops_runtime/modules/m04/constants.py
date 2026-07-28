from __future__ import annotations

from model_secrets import CHALLENGE_IDS as MODEL_SECRETS_CHALLENGE_IDS
from model_secrets_expansion import CHALLENGE_IDS as MODEL_SECRETS_EXPANSION_IDS


SECRETS_CHALLENGE_IDS = tuple(
    sorted((*MODEL_SECRETS_CHALLENGE_IDS, *MODEL_SECRETS_EXPANSION_IDS))
)

SECRETS_EVIDENCE = {
    "kep-m04-a": ("ai_interface_secret_extraction", "ev-model-secrets"),
    "kep-m04-b": ("system_prompt_reconstruction", "ev-system-prompt-reconstruction"),
    "kep-m04-c": ("training_membership_diagnostic", "ev-membership-diagnostic"),
    "kep-m04-d": ("training_membership_inference", "ev-membership-inference"),
    "kep-m04-e": ("population_privacy_inference", "ev-population-privacy"),
    "kep-m04-f": ("model_fingerprint_04", "ev-model-fingerprint"),
    "kep-m04-g": ("runtime_artifact_census_04", "ev-runtime-artifact-census"),
    "kep-m04-h": ("hallucination_cartography_04", "ev-hallucination-cartography"),
    "kep-m04-i": ("system_delimiter_probe_04", "ev-system-delimiter-probe"),
    "kep-m04-j": ("agent_knowledge_map_04", "ev-agent-knowledge-map"),
    "kep-m04-k": ("dormant_wires_04", "ev-dormant-wires"),
    "kep-m04-l": ("rendered_exfil_04", "ev-rendered-exfil"),
    "kep-m04-m": ("service_data_export_04", "ev-service-data-export"),
}

SECRETS_POPULATIONS = {
    "kep-m04-c": "diagnostic",
    "kep-m04-d": "private",
    "kep-m04-e": "cohort",
}
