"""Bounded local-agent execution on the open-source LangGraph runtime."""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
import time
from collections.abc import Callable
from typing import Any, TypedDict

import jmespath
from langgraph.graph import END, START, StateGraph

from state import canonical_json


MAX_PLAN_STEPS = 8
MAX_DOCUMENT_BYTES = 32_768
MAX_RESULT_BYTES = 32_768


class ToolError(ValueError):
    """A bounded tool invocation was invalid or failed."""


class RunState(TypedDict):
    run_id: str
    agent_id: str
    config_version: str
    plan: list[dict[str, Any]]
    index: int
    max_steps: int
    timeout_ms: int
    allowed_tools: list[str]
    outputs: list[dict[str, Any]]
    error: str | None


EventCallback = Callable[[str, dict[str, Any]], None]


class LocalAgentRuntime:
    """Compile and run a deterministic LangGraph with a strict tool registry."""

    runtime_kind = "langgraph-local"

    def __init__(self, event_callback: EventCallback) -> None:
        self._event_callback = event_callback
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=4, thread_name_prefix="platform-agent-tool"
        )
        builder = StateGraph(RunState)
        builder.add_node("execute", self._execute_step)
        builder.add_edge(START, "execute")
        builder.add_conditional_edges(
            "execute", self._next_step, {"execute": "execute", END: END}
        )
        self.graph = builder.compile()

    @staticmethod
    def _next_step(state: RunState) -> str:
        if state["error"] is not None:
            return END
        if state["index"] >= len(state["plan"]):
            return END
        if state["index"] >= state["max_steps"]:
            return END
        return "execute"

    def _execute_step(self, state: RunState) -> dict[str, Any]:
        invocation = state["plan"][state["index"]]
        tool_ref = invocation["tool"]
        started = time.monotonic()
        try:
            if tool_ref not in state["allowed_tools"]:
                raise ToolError(
                    f"tool is not allowed by active configuration: {tool_ref}"
                )
            handler = self._handler(tool_ref)
            future = self._executor.submit(
                handler,
                invocation.get("arguments", {}),
                state["agent_id"],
                state["config_version"],
            )
            result = future.result(timeout=state["timeout_ms"] / 1000)
            if len(canonical_json(result).encode("utf-8")) > MAX_RESULT_BYTES:
                raise ToolError("tool result exceeds the bounded result size")
            output = {
                "run_id": state["run_id"],
                "step": state["index"],
                "tool": tool_ref,
                "status": "completed",
                "result": result,
                "duration_ms": round((time.monotonic() - started) * 1000, 3),
            }
            self._event_callback("agent.tool.completed", output)
            return {"index": state["index"] + 1, "outputs": [*state["outputs"], output]}
        except concurrent.futures.TimeoutError:
            error = f"tool exceeded {state['timeout_ms']} ms timeout: {tool_ref}"
        except (
            ToolError,
            jmespath.exceptions.JMESPathError,
            TypeError,
            ValueError,
        ) as exc:
            error = str(exc)
        output = {
            "run_id": state["run_id"],
            "step": state["index"],
            "tool": tool_ref,
            "status": "failed",
            "error": error,
            "duration_ms": round((time.monotonic() - started) * 1000, 3),
        }
        self._event_callback("agent.tool.failed", output)
        return {
            "index": state["index"] + 1,
            "outputs": [*state["outputs"], output],
            "error": error,
        }

    @staticmethod
    def _handler(tool_ref: str) -> Callable[[dict[str, Any], str, str], Any]:
        handlers = {
            "hash_text@1.0.0": LocalAgentRuntime._hash_text,
            "query_json@1.0.0": LocalAgentRuntime._query_json,
            "identity_metadata@1.0.0": LocalAgentRuntime._identity_metadata,
        }
        handler = handlers.get(tool_ref)
        if handler is None:
            raise ToolError(f"registered tool has no runtime handler: {tool_ref}")
        return handler

    @staticmethod
    def _hash_text(
        arguments: dict[str, Any], _agent_id: str, _version: str
    ) -> dict[str, Any]:
        if set(arguments) != {"text"}:
            raise ToolError("hash_text requires only the text argument")
        text = arguments["text"]
        if not isinstance(text, str) or not text or len(text) > 8192:
            raise ToolError("text must contain between 1 and 8192 characters")
        encoded = text.encode("utf-8")
        return {
            "algorithm": "sha256",
            "digest": f"sha256:{hashlib.sha256(encoded).hexdigest()}",
            "byte_count": len(encoded),
        }

    @staticmethod
    def _query_json(
        arguments: dict[str, Any], _agent_id: str, _version: str
    ) -> dict[str, Any]:
        if set(arguments) != {"expression", "document"}:
            raise ToolError("query_json requires expression and document arguments")
        expression = arguments["expression"]
        document = arguments["document"]
        if not isinstance(expression, str) or not expression or len(expression) > 256:
            raise ToolError("expression must contain between 1 and 256 characters")
        if not isinstance(document, (dict, list)):
            raise ToolError("document must be a JSON object or array")
        if len(canonical_json(document).encode("utf-8")) > MAX_DOCUMENT_BYTES:
            raise ToolError("document exceeds the bounded input size")
        result = jmespath.search(expression, document)
        # Enforce JSON-compatible output from the query engine.
        json.dumps(result, allow_nan=False)
        return {"expression": expression, "value": result}

    @staticmethod
    def _identity_metadata(
        arguments: dict[str, Any], agent_id: str, config_version: str
    ) -> dict[str, Any]:
        if arguments:
            raise ToolError("identity_metadata does not accept arguments")
        return {
            "agent_id": agent_id,
            "config_version": config_version,
            "runtime": LocalAgentRuntime.runtime_kind,
        }

    def run(
        self,
        *,
        run_id: str,
        agent_id: str,
        config_version: str,
        plan: list[dict[str, Any]],
        allowed_tools: list[str],
        max_steps: int,
        timeout_ms: int,
    ) -> RunState:
        if not plan or len(plan) > MAX_PLAN_STEPS:
            raise ToolError(f"plan must contain between 1 and {MAX_PLAN_STEPS} steps")
        if len(plan) > max_steps:
            raise ToolError("plan exceeds the active configuration step limit")
        for invocation in plan:
            if set(invocation) - {"tool", "arguments"}:
                raise ToolError("tool invocation contains unsupported fields")
            if not isinstance(invocation.get("tool"), str):
                raise ToolError("every invocation requires a string tool reference")
            if invocation["tool"] not in allowed_tools:
                raise ToolError(
                    f"tool is not allowed by active configuration: {invocation['tool']}"
                )
            if not isinstance(invocation.get("arguments", {}), dict):
                raise ToolError("tool arguments must be a JSON object")
        initial: RunState = {
            "run_id": run_id,
            "agent_id": agent_id,
            "config_version": config_version,
            "plan": plan,
            "index": 0,
            "max_steps": max_steps,
            "timeout_ms": timeout_ms,
            "allowed_tools": allowed_tools,
            "outputs": [],
            "error": None,
        }
        return self.graph.invoke(initial, {"recursion_limit": max_steps + 2})
