from __future__ import annotations

import sys
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_ROOT = PACK_ROOT / "assets/services/keplerops-runtime"
sys.path.insert(0, str(RUNTIME_ROOT))

from green_activity.actions import GreenActionExecutor, GreenActionObservation
from green_activity.runtime import GreenActivityEngine
from raes import parse_sdl_file
from raes_processor.compiler import compile_scenario_runtime_model

SDL_ROOT = PACK_ROOT / "sdl" / "keplerops-ai.sdl.yaml"
GREEN_BEHAVIOR = "participant.behavior-specification.activity.green-company-live-activity"
GREEN_PARTICIPANT = "participant.behavior.activity.green-company-activity"
GREEN_ACTIONS = {
    "participant.action-contract.activity.green-workhub-ticket-triage": "workhub",
    "participant.action-contract.activity.green-mail-thread-review": "mail",
    "participant.action-contract.activity.green-notebook-evaluation-check": "notebook",
    "participant.action-contract.activity.green-mlflow-model-review": "registry",
    "participant.action-contract.activity.green-inference-smoke-request": "inference",
}


class RecordingActions:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def execute(self, action_address: str) -> GreenActionObservation:
        self.calls.append(action_address)
        return GreenActionObservation(
            status="succeeded",
            observation=f"{GREEN_ACTIONS[action_address]} action completed",
            evidence_refs=(f"evidence.green-activity.{GREEN_ACTIONS[action_address]}",),
            measurements={"inference_tokens": 17 if GREEN_ACTIONS[action_address] == "inference" else 0},
        )


def test_green_action_executor_routes_every_compiled_action() -> None:
    calls: list[str] = []
    handlers = {
        action: lambda action=action, label=label: (
            calls.append(action),
            GreenActionObservation(
                status="succeeded",
                observation=f"{label} action completed",
                evidence_refs=(f"evidence.green-activity.{label}",),
            ),
        )[1]
        for action, label in GREEN_ACTIONS.items()
    }
    executor = GreenActionExecutor(handlers)

    observed = {action: executor.execute(action) for action in GREEN_ACTIONS}

    assert calls == list(GREEN_ACTIONS)
    assert {result.status for result in observed.values()} == {"succeeded"}
    assert {result.observation for result in observed.values()} == {
        f"{label} action completed" for label in GREEN_ACTIONS.values()
    }


def test_green_engine_uses_compiled_raes_policy_and_behavior_history(tmp_path: Path) -> None:
    actions = RecordingActions()
    engine = GreenActivityEngine.from_sdl(
        SDL_ROOT,
        actions,
        state_root=tmp_path,
        range_instance="range-a",
        reset_generation=65,
        public_seed="42" * 32,
    )

    first = engine.run_next_due()

    assert first.success
    assert 1 <= len(actions.calls) <= 2
    assert set(actions.calls) <= GREEN_ACTIONS.keys()
    snapshot = engine.snapshot
    history = snapshot.participant_behavior_history[GREEN_PARTICIPANT]
    assert [event["event_type"] for event in history] == (
        [
            "action_attempted",
            "state_transition_recorded",
            "observation_emitted",
        ]
        * len(actions.calls)
    )
    assert history[-1]["details"]["evidence_refs"][0].startswith(
        "evidence.green-activity."
    )
    assert snapshot.proposition_truth_results == {}
    assert snapshot.evaluation_results == {}
    assert GREEN_BEHAVIOR in engine.runtime_model.behavior_specifications


def test_green_engine_is_deterministic_for_range_generation_and_seed(tmp_path: Path) -> None:
    left_actions = RecordingActions()
    right_actions = RecordingActions()
    left = GreenActivityEngine.from_sdl(
        SDL_ROOT,
        left_actions,
        state_root=tmp_path / "left",
        range_instance="range-a",
        reset_generation=65,
        public_seed="17" * 32,
    )
    right = GreenActivityEngine.from_sdl(
        SDL_ROOT,
        right_actions,
        state_root=tmp_path / "right",
        range_instance="range-a",
        reset_generation=65,
        public_seed="17" * 32,
    )

    for _ in range(5):
        assert left.run_next_due().success
        assert right.run_next_due().success

    assert left_actions.calls == right_actions.calls
    assert left.status()["clock"] == right.status()["clock"]
    assert left.status()["attempted_actions"] == len(left_actions.calls)
    assert 5 <= len(left_actions.calls) <= 10


def test_green_engine_pause_resume_drain_and_generation_reset(tmp_path: Path) -> None:
    actions = RecordingActions()
    engine = GreenActivityEngine.from_sdl(
        SDL_ROOT,
        actions,
        state_root=tmp_path,
        range_instance="range-a",
        reset_generation=65,
        public_seed="33" * 32,
    )

    assert engine.control("pause").success
    paused = engine.status()
    assert paused["lifecycle"] == "paused"
    assert paused["accepting_new_work"] is False
    assert engine.run_next_due().success
    assert actions.calls == []

    assert engine.control("resume").success
    assert engine.run_next_due().success
    assert 1 <= len(actions.calls) <= 2

    assert engine.control("drain").success
    drained = engine.status()
    assert drained["lifecycle"] == "quiescent"
    assert drained["accepting_new_work"] is False
    assert drained["in_flight"] == 0

    assert engine.control("reset", reset_generation=66).success
    reset = engine.status()
    assert reset["lifecycle"] == "running"
    assert reset["reset_generation"] == 66
    assert reset["attempted_actions"] == 0
    scheduler_state = next(iter(engine.snapshot.participant_autonomous_execution_states.values()))
    assert scheduler_state["time_segment"] == 1
    assert scheduler_state["random_namespace"].startswith("keplerops-green-")


def test_green_engine_reports_completed_scheduler_lifecycle(tmp_path: Path) -> None:
    engine = GreenActivityEngine.from_sdl(
        SDL_ROOT,
        RecordingActions(),
        state_root=tmp_path,
        range_instance="range-a",
        reset_generation=65,
        public_seed="33" * 32,
    )

    states = engine.snapshot.participant_autonomous_execution_states
    for state in states.values():
        state["lifecycle_state"] = "completed"

    status = engine.status()
    assert status["lifecycle"] == "completed"
    assert status["accepting_new_work"] is False


def test_compiled_green_policy_remains_disjoint_from_challenge_authority() -> None:
    model = compile_scenario_runtime_model(parse_sdl_file(SDL_ROOT))
    behavior = model.behavior_specifications[GREEN_BEHAVIOR]

    assert behavior.autonomous_execution is not None
    assert behavior.autonomous_execution.evaluation_authority_mode == "none"
    boundary = model.observation_boundaries[
        "participant.observation-boundary.activity.green-activity-view"
    ]
    assert set(boundary.evidence_refs) == {
        f"evidence.green-activity.{label}" for label in GREEN_ACTIONS.values()
    }
    assert set(behavior.autonomous_execution.action_contract_addresses) == set(
        GREEN_ACTIONS
    )
    assert not set(GREEN_ACTIONS) & {
        action
        for address, candidate in model.behavior_specifications.items()
        if address != GREEN_BEHAVIOR
        for action in candidate.action_contract_addresses
    }
