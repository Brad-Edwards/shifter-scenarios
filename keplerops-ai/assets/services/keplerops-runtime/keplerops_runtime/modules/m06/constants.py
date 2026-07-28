from __future__ import annotations

from adversarial_input import CHALLENGE_IDS as ADVERSARIAL_INPUT_CHALLENGE_IDS


ADVERSARIAL_CHALLENGE_IDS = tuple(sorted(ADVERSARIAL_INPUT_CHALLENGE_IDS))

ADVERSARIAL_EVIDENCE = {
    "kep-m06-a": ("adversarial_manual_counterexample", "ev-manual-adversarial-input"),
    "kep-m06-b": ("adversarial_paired_counterexample", "ev-paired-adversarial-input"),
    "kep-m06-c": ("adversarial_budgeted_search", "ev-budgeted-adversarial-search"),
    "kep-m06-d": ("adversarial_revision_transfer", "ev-transfer-adversarial-input"),
    "kep-m06-e": ("adversarial_input_verdict", "ev-adversarial-input"),
    "kep-m06-f": ("adversarial_robust_transfer", "ev-robust-adversarial-transfer"),
    "kep-m06-g": ("open_literature_triangulation", "ev-open-literature-triangulation"),
    "kep-m06-h": ("open_vulnerability_research", "ev-open-vulnerability-research"),
    "kep-m06-i": ("victim_web_recon", "ev-victim-web-recon"),
    "kep-m06-j": ("active_ai_surface_scan", "ev-active-ai-surface-scan"),
    "kep-m06-k": ("public_artifact_kit", "ev-public-artifact-kit"),
    "kep-m06-l": ("cloud_attack_workbench", "ev-cloud-attack-workbench"),
    "kep-m06-m": ("edge_acquisition", "ev-edge-acquisition"),
    "kep-m06-n": ("domain_proxy_front", "ev-domain-proxy-front"),
    "kep-m06-o": ("capability_procurement", "ev-capability-procurement"),
    "kep-m06-p": ("generative_capability_procurement", "ev-generative-capability-procurement"),
    "kep-m06-q": ("custom_attack_builder", "ev-custom-attack-builder"),
    "kep-m06-r": ("white_box_optimizer", "ev-white-box-optimizer"),
    "kep-m06-s": ("retrieval_trust_forge", "ev-retrieval-trust-forge"),
    "kep-m06-t": ("synthetic_impersonation", "ev-synthetic-impersonation"),
    "kep-m06-u": ("generated_host_escape", "ev-generated-host-escape"),
    "kep-m06-v": ("security_control_exploit", "ev-security-control-exploit"),
}
