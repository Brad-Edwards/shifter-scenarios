"""RAES-backed runtime for deterministic ordinary company activity."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from raes import parse_sdl_file
from raes_backend_protocols.participant_resource_budgets import (
    ParticipantResourceBudgetCapabilities,
    ParticipantResourcePoolCapacity,
)
from raes_backend_protocols.participant_runtime_base import BaseParticipantRuntime
from raes_contracts.contracts import (
    ParticipantActionResultModel,
    ParticipantImplementationManifestModel,
    ParticipantImplementationSelectionModel,
)
from raes_contracts.contracts.participant_resource_budgets import (
    ParticipantResourceMeasurementModel,
)
from raes_contracts.participant_binding import (
    ParticipantActionAdmissionRequest,
    ParticipantNativeActionExecution,
)
from raes_contracts.random_stream_engine import derive_stream_key
from raes_contracts.runtime_state import ApplyResult, RuntimeSnapshot
from raes_processor.compiler import compile_scenario_runtime_model
from raes_runtime.control_plane_store import LocalControlPlaneStore
from raes_runtime.participant_activity import ParticipantActivityRandomControl
from raes_runtime.participant_scheduler import ParticipantScheduler
from raes_runtime.time_coordinator import TimeCoordinator

from .actions import GreenActionExecutor, GreenActionObservation

GREEN_BEHAVIOR = "participant.behavior-specification.activity.green-company-live-activity"
GREEN_IMPLEMENTATION = "participant-implementation-manifests.keplerops-green-activity.v1"
_RANDOM_PROFILE = "blake3-xof-participant-v1"
_SHA256_PREFIX = "sha256:"
_ACTION_EVIDENCE = {
    "participant.action-contract.activity.green-workhub-ticket-triage": "evidence.green-activity.workhub",
    "participant.action-contract.activity.green-mail-thread-review": "evidence.green-activity.mail",
    "participant.action-contract.activity.green-notebook-evaluation-check": "evidence.green-activity.notebook",
    "participant.action-contract.activity.green-mlflow-model-review": "evidence.green-activity.registry",
    "participant.action-contract.activity.green-inference-smoke-request": "evidence.green-activity.inference",
}


def _manifest() -> ParticipantImplementationManifestModel:
    return ParticipantImplementationManifestModel.model_validate(
        {
            "schema_version": "participant-implementation-manifest/v1",
            "identity": {"name": "keplerops-green-activity", "version": "1.0.0"},
            "implementation_kind": "agent",
            "supported_contract_versions": [
                "participant-implementation-manifest-v1",
                "participant-implementation-provenance-v1",
                "participant-episode-state-envelope-v1",
                "participant-episode-history-event-stream-v1",
                "participant-behavior-history-event-stream-v1",
            ],
            "compatibility": {"participant_runtimes": ["keplerops-golden-runtime"]},
            "concept_bindings": [
                {"scope": "implementation_kind", "family": "apparatus-declarations"},
                {
                    "scope": "capabilities.supported_participant_contracts",
                    "family": "apparatus-declarations",
                },
                {
                    "scope": "capabilities.supported_decision_surface_modes",
                    "family": "apparatus-declarations",
                },
                {
                    "scope": "capabilities.tool_affordance_expectations",
                    "family": "tools-and-artifacts",
                },
                {
                    "scope": "capabilities.exposure_policy_kinds",
                    "family": "provenance-and-evidence",
                },
            ],
            "capabilities": {
                "supported_participant_contracts": [
                    "participant-episode-state-envelope-v1",
                    "participant-episode-history-event-stream-v1",
                    "participant-behavior-history-event-stream-v1",
                ],
                "supported_decision_surface_modes": ["autonomous"],
                "tool_affordance_expectations": ["http-api"],
                "exposure_policy_kinds": ["observation-stream"],
            },
        }
    )


def _selection(participant_address: str) -> ParticipantImplementationSelectionModel:
    return ParticipantImplementationSelectionModel.model_validate(
        {
            "participant_address": participant_address,
            "implementation_identity": {
                "name": "keplerops-green-activity",
                "version": "1.0.0",
            },
            "manifest_ref": GREEN_IMPLEMENTATION,
            "manifest_digest": _SHA256_PREFIX + hashlib.sha256(b"keplerops-green-activity-v1").hexdigest(),
            "selected_decision_surface_mode": "autonomous",
            "participant_contract_versions": [
                "participant-episode-state-envelope-v1",
                "participant-behavior-history-event-stream-v1",
            ],
            "exposure_policy": {
                "policy_id": "keplerops-green-observation-boundary",
                "policy_version": "1.0.0",
                "policy_digest": _SHA256_PREFIX
                + hashlib.sha256(b"keplerops-green-observation-boundary-v1").hexdigest(),
                "exposure_policy_kinds": ["observation-stream"],
                "disclosed_refs": ["participant.observation-boundary.activity.green-activity-view"],
                "withheld_refs": [],
                "tool_affordance_refs": [],
                "visibility_scope_refs": ["participants.green.visible"],
            },
        }
    )


class _GreenParticipantRuntime(BaseParticipantRuntime):
    def __init__(self, actions: GreenActionExecutor | Any) -> None:
        super().__init__()
        self._actions = actions
        self._manifest = _manifest()

    def bind_autonomous_action(
        self,
        participant_address: str,
        action_contract_address: str,
        observation_boundary_address: str,
        participant_implementation_ref: str,
        action_instance_id: str,
        temporal_contexts: tuple[object, ...],
        snapshot: RuntimeSnapshot,
    ) -> ParticipantActionAdmissionRequest:
        del snapshot
        if participant_implementation_ref != GREEN_IMPLEMENTATION:
            raise ValueError("compiled green implementation reference is not supported")
        return ParticipantActionAdmissionRequest(
            participant_address=participant_address,
            action_contract_address=action_contract_address,
            observation_boundary_address=observation_boundary_address,
            action_instance_id=action_instance_id,
            implementation_manifest=self._manifest,
            implementation_selection=_selection(participant_address),
            evidence_refs=(_ACTION_EVIDENCE[action_contract_address],),
            observation_boundary_evidence_refs=(_ACTION_EVIDENCE[action_contract_address],),
            temporal_contexts=temporal_contexts,
        )

    def _model_action(
        self,
        request: ParticipantActionAdmissionRequest,
        snapshot: RuntimeSnapshot,
        *,
        episode_id: str,
    ) -> ParticipantNativeActionExecution:
        observed: GreenActionObservation = self._actions.execute(request.action_contract_address)
        measurements = []
        for requirement in request.resource_measurement_requirements:
            if requirement.resource_kind in {"action_rate", "concurrent_actions"}:
                measured = requirement.reserved
            else:
                measured = min(
                    int(observed.measurements.get(requirement.resource_kind, 0)),
                    requirement.reserved,
                )
            measurements.append(
                ParticipantResourceMeasurementModel(
                    budget_state_ref=requirement.budget_state_ref,
                    operation_id=request.action_instance_id,
                    execution_generation=request.execution_generation or 0,
                    resource_kind=requirement.resource_kind,
                    unit=requirement.unit,
                    meter_profile_ref=requirement.meter_profile_ref,
                    measured=measured,
                    evidence_refs=observed.evidence_refs,
                )
            )
        return ParticipantNativeActionExecution(
            apply_result=ApplyResult(success=True, snapshot=snapshot),
            action_result=ParticipantActionResultModel(
                status=observed.status,
                participant_address=request.participant_address,
                episode_id=episode_id,
                action_instance_id=request.action_instance_id,
                action_contract_address=request.action_contract_address,
                observation_point=request.temporal_contexts[0].observation_point,
                failure_class=observed.failure_class,
                observations=[observed.observation],
                resource_measurements=measurements,
                evidence_refs=list(observed.evidence_refs),
            ),
        )


def _resource_capabilities(policy: Any) -> ParticipantResourceBudgetCapabilities:
    fairness = policy.resource_fairness
    pools = tuple(
        ParticipantResourcePoolCapacity(
            pool_ref=demand.pool_ref,
            owner_kind=demand.owner_kind,
            owner_ref=demand.owner_address,
            resource_kind=demand.resource_kind,
            unit=demand.unit,
            accounting_mode=demand.accounting_mode,
            meter_profile_ref=demand.meter_profile_ref,
            capacity=demand.limit,
            tenant_isolation="tenant_partitioned",
            configuration_digest=_SHA256_PREFIX
            + hashlib.sha256(
                f"{policy.address}|{demand.budget_id}|{demand.limit}".encode()
            ).hexdigest(),
            fairness_policy=fairness.policy,
            priority_classes=("evaluated", "standard", "background"),
            borrowing=fairness.borrowing,
            reclaim=fairness.reclaim,
            max_queue_ticks=fairness.max_queue_ticks,
            starvation_bound_ticks=fairness.starvation_bound_ticks,
            protected_capacity=0,
            evidence_contract_ids=("participant-resource-budget-event-v1",),
        )
        for demand in policy.resource_demands
    )
    return ParticipantResourceBudgetCapabilities(
        support_strength="exact",
        supported_owner_kinds=frozenset(demand.owner_kind for demand in policy.resource_demands),
        supported_resource_kinds=frozenset(demand.resource_kind for demand in policy.resource_demands),
        supported_accounting_modes=frozenset(demand.accounting_mode for demand in policy.resource_demands),
        supported_reset_modes=frozenset(demand.reset for demand in policy.resource_demands),
        supported_fairness_policies=frozenset({fairness.policy}),
        supported_isolation_strengths=frozenset({"tenant_partitioned"}),
        configured_pools=pools,
        realization_contract_ids=frozenset(
            {
                "participant-resource-budget-policy-v1",
                "participant-resource-pool-capacity-v1",
                "participant-resource-budget-event-v1",
            }
        ),
    )


class GreenActivityEngine:
    """Small golden backend adapter around the portable RAES runtime."""

    def __init__(
        self,
        runtime_model: Any,
        actions: GreenActionExecutor | Any,
        *,
        state_root: Path,
        range_instance: str,
        reset_generation: int,
        public_seed: str,
    ) -> None:
        self.runtime_model = runtime_model
        behavior = runtime_model.behavior_specifications[GREEN_BEHAVIOR]
        if behavior.autonomous_execution is None:
            raise ValueError("green behavior requires compiled autonomous execution")
        self._policy = behavior.autonomous_execution
        if self._policy.evaluation_authority_mode != "none":
            raise ValueError("green activity must not carry evaluation authority")
        actual_actions = frozenset(self._policy.action_contract_addresses)
        declared_actions = getattr(actions, "action_addresses", actual_actions)
        if frozenset(declared_actions) != actual_actions:
            raise ValueError("green action handlers must exactly match the compiled policy")
        self._participant_runtime = _GreenParticipantRuntime(actions)
        self._coordinator = TimeCoordinator(runtime_model.time_model)
        self._store = LocalControlPlaneStore(state_root)
        self._range_instance = range_instance
        self._reset_generation = reset_generation
        self._public_seed = public_seed
        self._lifecycle = "running"
        self._controls = self._random_controls()

        snapshot = self._store.load_snapshot()
        if snapshot.time_model_state is None:
            snapshot = self._coordinator.initialize(snapshot)
            initialized = ParticipantScheduler.initialize(
                (self._policy,),
                runtime_model.time_model,
                self._participant_runtime,
                snapshot,
                self._controls,
                _resource_capabilities(self._policy),
            )
            if not initialized.success:
                raise ValueError(
                    "green scheduler initialization failed: "
                    + "; ".join(item.message for item in initialized.diagnostics)
                )
            snapshot = initialized.snapshot
            snapshot = snapshot.with_entries(
                dict(snapshot.entries),
                metadata={
                    **snapshot.metadata,
                    "green_range_instance": range_instance,
                    "green_reset_generation": reset_generation,
                },
            )
            self._store.save_snapshot(snapshot)
        else:
            expected = (range_instance, reset_generation)
            observed = (
                snapshot.metadata.get("green_range_instance"),
                snapshot.metadata.get("green_reset_generation"),
            )
            if observed != expected:
                raise ValueError("persisted green activity state belongs to another range generation")
        self.snapshot = snapshot

    @classmethod
    def from_sdl(
        cls,
        sdl_path: Path,
        actions: GreenActionExecutor | Any,
        **kwargs: Any,
    ) -> GreenActivityEngine:
        return cls(
            compile_scenario_runtime_model(parse_sdl_file(sdl_path)),
            actions,
            **kwargs,
        )

    def _random_controls(self) -> dict[str, ParticipantActivityRandomControl]:
        entropy = bytes.fromhex(self._public_seed)
        if len(entropy) != 32:
            raise ValueError("green public seed must be 32 bytes of hexadecimal")
        instance_digest = hashlib.sha256(self._range_instance.encode()).hexdigest()[:16]
        namespace = f"keplerops-green-{instance_digest}"
        control = ParticipantActivityRandomControl(
            control_id=self._policy.stochastic_control_ref,
            profile_id=_RANDOM_PROFILE,
            namespace=namespace,
            stream_key=derive_stream_key(profile_id=_RANDOM_PROFILE, root_entropy=entropy),
        )
        return {control.control_id: control}

    def _persist(self, result: ApplyResult) -> ApplyResult:
        self.snapshot = result.snapshot
        self._store.save_snapshot(self.snapshot)
        return result

    def run_next_due(self) -> ApplyResult:
        if self._lifecycle != "running":
            return ApplyResult(success=True, snapshot=self.snapshot)
        states = tuple(self.snapshot.participant_autonomous_execution_states.values())
        running = [state for state in states if state.get("lifecycle_state") == "running"]
        if not running:
            return ApplyResult(success=True, snapshot=self.snapshot)
        target_tick = min(int(state["next_tick"]) for state in running)
        reading = self._coordinator.reading(self.snapshot, self._policy.clock_address)
        step = next(
            item.step_ticks
            for item in self.runtime_model.time_model.progression_policies
            if item.address == self._policy.progression_policy_address
        )
        while reading.tick < target_tick:
            self.snapshot = self._coordinator.advance(
                self.snapshot,
                self._policy.clock_address,
                ticks=step,
            )
            reading = self._coordinator.reading(self.snapshot, self._policy.clock_address)
        return self._persist(
            ParticipantScheduler.run_due(
                (self._policy,),
                self.runtime_model.time_model,
                self._participant_runtime,
                self.snapshot,
                self._controls,
            )
        )

    def seconds_until_next_due(self) -> float:
        states = tuple(self.snapshot.participant_autonomous_execution_states.values())
        running = [state for state in states if state.get("lifecycle_state") == "running"]
        if not running or self._lifecycle != "running":
            return 5.0
        target_tick = min(int(state["next_tick"]) for state in running)
        reading = self._coordinator.reading(self.snapshot, self._policy.clock_address)
        clock = next(
            item
            for item in self.runtime_model.time_model.clocks
            if item.address == self._policy.clock_address
        )
        domain = next(
            item
            for item in self.runtime_model.time_model.domains
            if item.address == clock.time_domain_address
        )
        tick_seconds = domain.tick_period_numerator / domain.tick_period_denominator
        return max(0.0, (target_tick - reading.tick) * tick_seconds)

    def control(self, action: str, *, reset_generation: int | None = None) -> ApplyResult:
        if action in {"pause", "drain"}:
            if self._lifecycle == "running":
                self.snapshot = self._coordinator.pause(self.snapshot, self._policy.clock_address)
                result = ParticipantScheduler.set_clock_lifecycle(
                    self.snapshot,
                    self._policy.clock_address,
                    "paused",
                )
                self.snapshot = result.snapshot
            self._lifecycle = "quiescent" if action == "drain" else "paused"
            return self._persist(ApplyResult(success=True, snapshot=self.snapshot))
        if action == "resume":
            if self._lifecycle in {"paused", "quiescent"}:
                self.snapshot = self._coordinator.resume(self.snapshot, self._policy.clock_address)
                result = ParticipantScheduler.set_clock_lifecycle(
                    self.snapshot,
                    self._policy.clock_address,
                    "running",
                )
                self.snapshot = result.snapshot
            self._lifecycle = "running"
            return self._persist(ApplyResult(success=True, snapshot=self.snapshot))
        if action == "reset":
            if reset_generation is None or reset_generation <= self._reset_generation:
                raise ValueError("reset requires a newer reset_generation")
            self.snapshot = self._coordinator.reset(self.snapshot, self._policy.clock_address)
            reset = ParticipantScheduler.reset_clock(
                (self._policy,),
                self.runtime_model.time_model,
                self._participant_runtime,
                self.snapshot,
                self._policy.clock_address,
                activity_controls=self._controls,
            )
            if not reset.success:
                return self._persist(reset)
            self._reset_generation = reset_generation
            self.snapshot = reset.snapshot.with_entries(
                dict(reset.snapshot.entries),
                metadata={
                    **reset.snapshot.metadata,
                    "green_reset_generation": reset_generation,
                },
            )
            self._lifecycle = "running"
            return self._persist(ApplyResult(success=True, snapshot=self.snapshot))
        raise ValueError(f"unsupported green activity control action {action!r}")

    def status(self) -> dict[str, object]:
        states = tuple(self.snapshot.participant_autonomous_execution_states.values())
        attempted = sum(int(state.get("attempted_actions", 0)) for state in states)
        reading = self._coordinator.reading(self.snapshot, self._policy.clock_address)
        service = self.snapshot.participant_execution_services[self._policy.address]
        lifecycle = self._lifecycle
        scheduler_lifecycles = {
            str(state.get("lifecycle_state", "unknown")) for state in states
        }
        if lifecycle == "running" and states and "running" not in scheduler_lifecycles:
            lifecycle = (
                "completed" if scheduler_lifecycles == {"completed"} else "failed"
            )
        return {
            "lifecycle": lifecycle,
            "accepting_new_work": lifecycle == "running",
            "in_flight": int(service.get("in_flight", 0)),
            "reset_generation": self._reset_generation,
            "clock": {
                "segment": reading.segment,
                "tick": reading.tick,
                "microstep": reading.microstep,
            },
            "attempted_actions": attempted,
        }
