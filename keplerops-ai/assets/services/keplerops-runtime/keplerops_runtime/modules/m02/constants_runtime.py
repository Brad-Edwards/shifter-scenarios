from __future__ import annotations

from model_evasion import CHALLENGE_IDS as MODEL_EVASION_CHALLENGE_IDS
from model_supply import CHALLENGE_IDS as MODEL_SUPPLY_CHALLENGE_IDS


EVASION_CHALLENGE_IDS = tuple(
    sorted(set(MODEL_EVASION_CHALLENGE_IDS) | set(MODEL_SUPPLY_CHALLENGE_IDS))
)

SUPPLY_CHALLENGE_IDS = tuple(sorted(MODEL_SUPPLY_CHALLENGE_IDS))

EVASION_EVIDENCE = {
    "kep-m02-a": ("model_decision_evasion", "ev-model-evasion"),
    "kep-m02-b": ("model_encoding_evasion", "ev-model-encoding-evasion"),
    "kep-m02-c": ("model_semantic_evasion", "ev-model-semantic-evasion"),
    "kep-m02-d": ("model_repeatable_evasion", "ev-model-repeatable-evasion"),
    "kep-m02-e": ("model_transfer_evasion", "ev-model-transfer-evasion"),
    "kep-m02-f": ("model_ensemble_evasion", "ev-model-ensemble-evasion"),
}

SUPPLY_EVIDENCE = {
    "kep-m02-h": ("masquerading_ai_runtime_executed", "ev-masquerading-ai-runtime"),
    "kep-m02-i": ("poisoned_data_dependency_consumed", "ev-poisoned-data-dependency"),
    "kep-m02-j": ("poisoned_model_dependency_resolved", "ev-poisoned-model-dependency"),
    "kep-m02-k": ("web_exploit_model_delivery", "ev-web-exploit-delivery"),
    "kep-m02-l": ("synthetic_spearphish_token_disclosure", "ev-synthetic-spearphish"),
    "kep-m02-m": ("sandbox_aware_payload_execution", "ev-sandbox-aware-payload"),
}
