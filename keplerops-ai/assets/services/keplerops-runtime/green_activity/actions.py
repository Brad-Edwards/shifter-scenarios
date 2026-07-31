"""Action dispatch boundary for the KeplerOps green participant."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class GreenActionObservation:
    """Bounded observation returned by one real service interaction."""

    status: Literal["succeeded", "failed"]
    observation: str
    evidence_refs: tuple[str, ...]
    measurements: Mapping[str, int] = field(default_factory=dict)
    failure_class: str | None = None

    def __post_init__(self) -> None:
        if not self.observation:
            raise ValueError("green action observation must be non-empty")
        if not self.evidence_refs:
            raise ValueError("green action evidence_refs must be non-empty")
        if self.status == "failed" and self.failure_class is None:
            raise ValueError("failed green actions require a failure_class")
        if any(value < 0 for value in self.measurements.values()):
            raise ValueError("green action measurements must be non-negative")


class GreenActionExecutor:
    """Routes compiled action addresses to explicit golden-range handlers."""

    def __init__(
        self,
        handlers: Mapping[str, Callable[[], GreenActionObservation]],
    ) -> None:
        if not handlers:
            raise ValueError("green action executor requires at least one handler")
        self._handlers = dict(handlers)

    @property
    def action_addresses(self) -> frozenset[str]:
        return frozenset(self._handlers)

    def execute(self, action_address: str) -> GreenActionObservation:
        try:
            handler = self._handlers[action_address]
        except KeyError as exc:
            raise ValueError(f"no green action handler for {action_address!r}") from exc
        observation = handler()
        if not isinstance(observation, GreenActionObservation):
            raise TypeError("green action handlers must return GreenActionObservation")
        return observation
