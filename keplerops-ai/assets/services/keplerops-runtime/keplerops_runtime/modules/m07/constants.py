from __future__ import annotations

from training_poisoning import CHALLENGE_IDS as TRAINING_POISONING_CHALLENGE_IDS


TRAINING_CHALLENGE_IDS = tuple(sorted(TRAINING_POISONING_CHALLENGE_IDS))

TRAINING_EVIDENCE = {
    "kep-m07-a": ("training_dataset_versioned", "ev-poisoned-row"),
    "kep-m07-b": ("training_target_delta", "ev-targeted-data-poisoning"),
    "kep-m07-c": ("training_clean_tolerance", "ev-clean-tolerance"),
    "kep-m07-d": ("training_low_rate_delta", "ev-low-rate-poisoning"),
    "kep-m07-e": ("training_hidden_trigger", "ev-backdoor-dataset"),
    "kep-m07-f": ("training_poison_verdict", "ev-training-poison"),
    "kep-m07-g": ("training_architecture_sabotage", "ev-architecture-sabotage"),
    "kep-m07-h": ("poisoned_dataset_publication", "ev-poisoned-dataset-publication"),
    "kep-m07-i": ("executable_model_artifact", "ev-executable-model-artifact"),
}
