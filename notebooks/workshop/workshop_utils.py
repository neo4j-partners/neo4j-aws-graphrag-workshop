# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Workshop utility helpers shared by the agent notebooks.

Four concerns live here for the workshop's agent notebooks:

- log suppression (`quiet_logs`), which quiets verbose third-party SDK
  loggers so notebook output stays readable;
- progress display (`lego_progress`), which prints the workshop-wide
  module-progress tower;
- a Strands trace hook (`ToolTraceHook`), which prints each tool call an
  agent makes as it happens and records what came back;
- routing evidence (`selected_tool_names`), which reads the tools an agent
  turn actually chose out of its result metrics; and
- result printing (`show_result`), which prints an agent turn's text answer
  followed by its token usage.
"""
import json
import logging


def quiet_logs():
    """Suppress verbose third-party SDK logging so notebook output stays clean."""
    for name in ['botocore', 'boto3', 'neo4j', 'httpx', 'opentelemetry',
                 'strands', 'urllib3', 'anthropic']:
        logging.getLogger(name).setLevel(logging.WARNING)
    logging.root.setLevel(logging.WARNING)


def lego_progress(completed: int):
    """Print a visual progress tower showing modules completed so far.

    Args:
        completed: number of modules completed (0-6).
    """
    modules = [
        "Module 1: Build the Graph",
        "Module 2: Graph-Enriched Retrieval",
        "Module 3: Build the Grounded Booking Agent",
        "Module 4: Production Agent with AgentCore",
        "Module 5: Deploy to AgentCore Runtime",
        "Module 6: Neo4j Graph Memory",
    ]
    total = len(modules)
    print("\n" + "=" * 56)
    print("  Workshop progress")
    print("  " + "🟦" * completed + "⬜" * (total - completed))
    for i, label in enumerate(modules):
        if i < completed:
            print(f"  ✅  {label}")
        elif i == completed:
            print(f"  ▶️   {label}  ← you are here")
        else:
            print(f"  ⬜  {label}")
    print("=" * 56 + "\n")


# ---------------------------------------------------------------------------
# Live tool tracing and token metrics for Modules 3 and 4
# ---------------------------------------------------------------------------
#
# `strands` is imported at module scope rather than inside the hook. It is the
# first line of `requirements.txt`, so a missing import here means the
# environment is not set up at all, and that is worth failing on immediately
# with "No module named 'strands'" rather than several cells later inside an
# agent constructor.
from strands.hooks import AfterToolCallEvent, BeforeToolCallEvent, HookProvider, HookRegistry

# Tool inputs and results are echoed into notebook output. A Gateway tool can
# return a page of JSON, and an untruncated trace scrolls the actual teaching
# point off the screen.
TRACE_VALUE_CHARS = 160


def _truncate(value: object, limit: int = TRACE_VALUE_CHARS) -> str:
    """Render `value` on one line, clipped to `limit` characters."""
    text = " ".join(str(value).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _block_payload(block: object) -> object | None:
    """Return one tool-result content block as data, or None if it carries none.

    A content block can hold native JSON or text. Module 3's local tools return
    a `json` block, so numbers reach the model as numbers. A Gateway tool
    returns JSON serialized into a `text` block. Both are read here, and a
    `text` block that parses as JSON is returned as data rather than as a
    string, so a caller reads one shape whichever transport produced it.
    """
    if not isinstance(block, dict):
        return None
    if "json" in block:
        return block["json"]
    text = block.get("text")
    if not isinstance(text, str) or not text.strip():
        return None
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return text


def _payloads(result: object) -> list[object]:
    """Return every content block of a tool result that carried data."""
    if not isinstance(result, dict):
        return []
    found = [_block_payload(block) for block in result.get("content") or []]
    return [payload for payload in found if payload is not None]


def _render(payload: object) -> str:
    """Render one payload for the printed trace."""
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, ensure_ascii=False, default=str)


def selected_tool_names(result: object) -> list[str]:
    """Return the tool names an agent turn used, in name order.

    The trace prints tool calls as they happen, which a participant reads. This
    reads the same fact back as data, out of the event loop's own metrics, so a
    routing check does not depend on parsing printed output. A turn that called
    no tool returns an empty list, which is what the social-turn example needs.
    """
    metrics = getattr(result, "metrics", None)
    return sorted(getattr(metrics, "tool_metrics", None) or {})


class ToolTraceHook(HookProvider):
    """Print each tool call as the agent makes it.

    Module 3 uses it to show which of its two read tools the model chose.
    Module 4 uses it to show that a Strands agent calls a retrieval tool
    through the Gateway. Without a trace the participant sees only the final
    answer and has to take on faith that a remote tool ran at all.

    Registered as `Agent(hooks=[ToolTraceHook()])`. It only reads the events, it
    never sets `cancel_tool` or `retry`, so adding it cannot change what the
    agent does. That matters for a teaching aid: an observer that alters the run
    is not observing the run the participant is being shown.

    `calls` records one entry per completed tool call, holding the tool name,
    its status, and the complete payload of every content block. Only the
    printed line is truncated: a check that reads a returned grounding verdict
    needs the whole payload, and reading it back out of clipped console text is
    how a check ends up asserting on a display limit. Build one hook per
    example so recorded calls cannot leak between them.
    """

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def register_hooks(self, registry: HookRegistry, **kwargs: object) -> None:
        """Subscribe to the before and after tool-call events."""
        registry.add_callback(BeforeToolCallEvent, self._before_tool)
        registry.add_callback(AfterToolCallEvent, self._after_tool)

    def _before_tool(self, event: BeforeToolCallEvent) -> None:
        tool_use = event.tool_use or {}
        print(f"  🔧 {tool_use.get('name', '<unnamed>')}({_truncate(tool_use.get('input', {}))})")

    def _after_tool(self, event: AfterToolCallEvent) -> None:
        # An exception is reported instead of the result. A tool that raised has
        # no useful `result` payload, and silently printing an empty one is how
        # a broken tool looks identical to a tool that returned nothing.
        if event.exception is not None:
            self.calls.append(
                {
                    "name": (event.tool_use or {}).get("name", "<unnamed>"),
                    "status": "exception",
                    "input": (event.tool_use or {}).get("input", {}),
                    "payloads": [],
                }
            )
            print(f"     └─ raised {type(event.exception).__name__}: {_truncate(event.exception)}")
            return
        result = event.result or {}
        status = result.get("status", "unknown")
        marker = "✅" if status == "success" else "⚠️"
        payloads = _payloads(result)
        tool_use = event.tool_use or {}
        self.calls.append(
            {
                "name": tool_use.get("name", "<unnamed>"),
                "status": status,
                "input": tool_use.get("input", {}),
                "payloads": payloads,
            }
        )
        body = " ".join(_render(payload) for payload in payloads)
        print(f"     └─ {marker} {status}: {_truncate(body)}")


def show_result(result: object, label: str = "Agent") -> None:
    """Print an agent turn's text answer followed by its token usage.

    `result` is the `AgentResult` returned by calling the agent. Its `__str__`
    already concatenates the text blocks out of the response message, so the
    answer is taken from there rather than by walking `message["content"]` here
    and duplicating a rule that belongs to the SDK.

    Usage is read defensively. `metrics` is populated by the event loop, and a
    turn that fails early can carry an empty one; a helper whose only job is to
    display a result should not be the thing that raises on a degraded result.
    """
    print(f"\n{label}:")
    text = str(result).strip()
    print(text if text else "(no text in response)")

    metrics = getattr(result, "metrics", None)
    usage = getattr(metrics, "accumulated_usage", None) or {}
    latency = (getattr(metrics, "accumulated_metrics", None) or {}).get("latencyMs")

    # A fresh `EventLoopMetrics` reports zeros rather than nothing, so an empty
    # check is not enough to tell "no tokens recorded" from "no tokens used".
    # A turn that reached the model always spends input tokens, so a zero total
    # means the metrics never got filled in, and printing it as though it were a
    # measurement teaches the participant to distrust the number.
    if not usage.get("totalTokens"):
        return

    parts = [
        f"in {usage.get('inputTokens', 0)}",
        f"out {usage.get('outputTokens', 0)}",
        f"total {usage.get('totalTokens', 0)}",
    ]
    if latency:
        parts.append(f"{latency} ms")
    print(f"   [tokens: {', '.join(parts)}]")
