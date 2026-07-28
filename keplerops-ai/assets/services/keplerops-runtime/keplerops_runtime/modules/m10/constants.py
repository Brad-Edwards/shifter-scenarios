from __future__ import annotations


CAPSTONE_CHALLENGE_IDS = tuple(f"kep-m10-{suffix}" for suffix in "abcdefghijklmnopq")

CAPSTONE_EVIDENCE = {
    "kep-m10-a": ("production_revision_loaded", "ev-production-revision"),
    "kep-m10-b": ("production_trigger_activated", "ev-production-trigger"),
    "kep-m10-c": ("contained_broker_effect", "ev-contained-effect"),
    "kep-m10-d": ("original_model_accessed", "ev-original-artifact-access"),
    "kep-m10-e": ("deployed_ai_impact", "ev-deployed-impact"),
    "kep-m10-f": ("contained_model_exfil", "ev-artifact-theft"),
    "kep-m10-h": ("service_denial_10", "ev-service-denial"),
    "kep-m10-i": ("cost_amplification_10", "ev-cost-amplification"),
    "kep-m10-j": ("agentic_budget_loop_10", "ev-agentic-budget-loop"),
    "kep-m10-k": ("chaff_flood_10", "ev-chaff-flood"),
    "kep-m10-l": ("financial_harm_10", "ev-financial-harm"),
    "kep-m10-m": ("reputational_harm_10", "ev-reputational-harm"),
    "kep-m10-n": ("societal_harm_10", "ev-societal-harm"),
    "kep-m10-o": ("user_harm_10", "ev-user-harm"),
    "kep-m10-p": ("dataset_integrity_destruction_10", "ev-dataset-integrity-destruction"),
    "kep-m10-q": ("agent_tool_data_destruction_10", "ev-agent-tool-data-destruction"),
}
