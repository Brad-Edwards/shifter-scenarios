"""Minimal guest pairing for the Cinder Typhoon three-image range."""

from __future__ import annotations

from shifter_adapter_sdk.runtime import PROTOCOL, GuestAction, PluginManifest, RuntimeInput, RuntimePlan

from ._runtime_common import _PREFIX


def manifest(worker_image: str) -> PluginManifest:
    return PluginManifest(
        protocol=PROTOCOL,
        plugin_id="panw.cinder-typhoon-direct",
        version="0.3.0",
        distribution="shifter-panw-adapter",
        entry_point="cinder_direct",
        worker_image=worker_image,
        capabilities=["guest.configure", "guest.verify"],
        required_bindings=["training", "keplerops", "arwc"],
        required_parameters=[],
    )


_IMPORT_KEPLEROPS = """#!/bin/bash
set -euo pipefail
peer=$(read_runtime_value arwc-address)
/usr/local/libexec/cinder-peer-ca import keplerops "$peer"
"""

_IMPORT_ARWC = """#!/bin/bash
set -euo pipefail
peer=$(read_runtime_value keplerops-address)
/usr/local/libexec/cinder-peer-ca import arwc "$peer"
"""

_ADDRESS_VALUES = {
    "arwc-address": {"binding": "arwc", "field": "private_address"},
    "keplerops-address": {"binding": "keplerops", "field": "private_address"},
}


class CinderTyphoonDirectAdapter:
    """Pair the two existing carriers, then verify all three image-owned phases."""

    def plan(self, request: RuntimeInput) -> RuntimePlan:
        request = RuntimeInput.model_validate(request)
        if (
            request.manifest != manifest(request.manifest.worker_image)
            or request.provider != "gcp"
            or any(target.os_family != "linux" for target in request.targets.values())
        ):
            raise ValueError("Incompatible Cinder Typhoon runtime binding")

        scripts: list[tuple[str, str, str, int, dict[str, dict[str, str]]]]
        if request.phase == "configure":
            scripts = [
                (
                    "keplerops-ca-export",
                    "keplerops",
                    "/usr/local/libexec/cinder-peer-ca export keplerops 18081",
                    300,
                    {},
                ),
                (
                    "arwc-ca-export",
                    "arwc",
                    "/usr/local/libexec/cinder-peer-ca export arwc 18082",
                    300,
                    {},
                ),
                (
                    "keplerops-peer-import",
                    "keplerops",
                    _PREFIX + _IMPORT_KEPLEROPS,
                    120,
                    {"arwc-address": _ADDRESS_VALUES["arwc-address"]},
                ),
                (
                    "arwc-peer-import",
                    "arwc",
                    _PREFIX + _IMPORT_ARWC,
                    120,
                    {"keplerops-address": _ADDRESS_VALUES["keplerops-address"]},
                ),
                (
                    "keplerops-ca-export-stop",
                    "keplerops",
                    "/usr/local/libexec/cinder-peer-ca stop keplerops",
                    30,
                    {},
                ),
                (
                    "arwc-ca-export-stop",
                    "arwc",
                    "/usr/local/libexec/cinder-peer-ca stop arwc",
                    30,
                    {},
                ),
            ]
        elif request.phase == "verify":
            scripts = [
                (
                    "training-ready",
                    "training",
                    "/usr/local/libexec/cinder-image-verify training",
                    300,
                    {},
                ),
                (
                    "keplerops-ready",
                    "keplerops",
                    "/usr/local/libexec/cinder-image-verify keplerops",
                    300,
                    {},
                ),
                (
                    "arwc-ready",
                    "arwc",
                    "/usr/local/libexec/cinder-image-verify arwc",
                    300,
                    {},
                ),
            ]
        else:
            scripts = []

        plan = RuntimePlan(
            protocol=request.protocol,
            invocation_id=request.invocation_id,
            input_digest=request.digest,
            phase=request.phase,
            status="planned",
            actions=[
                GuestAction(
                    action_id=action_id,
                    binding=binding,
                    script=script,
                    timeout_seconds=timeout,
                    runtime_values=runtime_values,
                )
                for action_id, binding, script, timeout, runtime_values in scripts
            ],
        )
        plan.authorize(request)
        return plan
