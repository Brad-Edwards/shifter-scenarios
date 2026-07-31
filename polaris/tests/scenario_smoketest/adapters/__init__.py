"""Per-flag adapters: the executable coverage map.

An adapter executes one flag's canonical participant path against a real
staged range and returns the value that path yields. Each adapter declares the
runner container it executes from and the *kind* of value it produces:

* ``flag``   - the path yields the literal ``FLAG{...}`` from the placement
  contract; the harness compares it for equality against that canonical value.
* ``answer`` - the path yields an evidence string distinct from the canonical
  flag (e.g. a concatenated device-model identifier). The adapter
  records ``expected_answer`` and the harness compares against that.

The coverage universe is derived from the canonical contracts, not from this
registry: a flag with no adapter is reported ``uncovered`` (a failure), never
skipped.

Adapter logic is factored from the existing per-asset smoketests under
``polaris/tests/smoketests/``; this registry does not duplicate
metadata from the canonical flag/challenge contracts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class Produced:
    """A value produced by walking a challenge's hint path."""

    value: str | None
    kind: str  # "flag" | "answer"
    note: str = ""


@dataclass
class AdapterContext:
    """Range connection context handed to every adapter."""

    runner: object  # a runner.Runner (or test double) exposing .exec()
    hosts: dict[str, str] = field(default_factory=dict)
    dns: str = "172.20.0.2"

    def host(self, key: str) -> str:
        """Return the configured hostname for an asset key (e.g. ``a0``)."""
        return self.hosts[key]


@dataclass(frozen=True)
class Adapter:
    """An executable check for one challenge."""

    flag_id: str
    runner: str
    value_kind: str
    solve: Callable[[AdapterContext], Produced]
    expected_answer: str | None = None


ADAPTERS: dict[str, Adapter] = {}


def register(
    flag_id: str,
    *,
    runner: str,
    value_kind: str = "flag",
    expected_answer: str | None = None,
) -> Callable[[Callable[[AdapterContext], Produced]], Callable]:
    """Register an adapter callable for a stable ``flag_id``."""

    def decorator(fn: Callable[[AdapterContext], Produced]):
        if flag_id in ADAPTERS:
            raise ValueError(f"duplicate adapter for flag {flag_id}")
        ADAPTERS[flag_id] = Adapter(
            flag_id=flag_id,
            runner=runner,
            value_kind=value_kind,
            solve=fn,
            expected_answer=expected_answer,
        )
        return fn

    return decorator


# Importing a mission module runs its @register decorators as a side effect.
from . import mission1_osint  # noqa: E402,F401
from . import mission5_bunker  # noqa: E402,F401
