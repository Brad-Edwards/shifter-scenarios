from __future__ import annotations


BACKDOOR_CHALLENGE_IDS = tuple(f"kep-m09-{suffix}" for suffix in "abcdefghijkl")

BACKDOOR_EVIDENCE = {
    "kep-m09-a": ("model_candidate_registered", "ev-candidate-registration"),
    "kep-m09-b": ("model_trigger_diagnostic", "ev-trigger-verification"),
    "kep-m09-c": ("model_clean_diagnostic", "ev-clean-model-verification"),
    "kep-m09-d": ("model_approval_confused", "ev-approval-confusion"),
    "kep-m09-e": ("model_backdoor_verified", "ev-backdoor-verification"),
    "kep-m09-f": ("model_unauthorized_promotion", "ev-promotion-bypass"),
    "kep-m09-g": ("poisoned_registry_promotion", "ev-poisoned-promotion"),
    "kep-m09-h": ("registry_reputation_seed_09", "ev-registry-reputation-seed"),
    "kep-m09-i": ("poisoned_model_publication_09", "ev-poisoned-model-publication"),
    "kep-m09-j": ("model_rug_pull_09", "ev-model-rug-pull"),
    "kep-m09-k": ("poisoned_tool_publication_09", "ev-poisoned-tool-publication"),
    "kep-m09-l": ("model_corruption_09", "ev-model-corruption"),
}
