"""Workshop utility helpers shared by Module 4's notebooks.

Four concerns live here, each used by more than one Module 4 notebook:

- log suppression (`quiet_logs`), which quiets verbose third-party SDK
  loggers so notebook output stays readable;
- progress display (`lego_progress`), which prints the workshop-wide
  module-progress tower;
- a Strands trace hook (`ToolTraceHook`), which prints each tool call an
  agent makes as it happens; and
- result printing (`show_result`), which prints an agent turn's text answer
  followed by its token usage.
"""
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
        "Module 2: From Similarity Search to Connected Context",
        "Module 3: Build the Grounded Booking Agent",
        "Module 4: Production Agent with AgentCore",
        "Module 5: Deploy to AgentCore Runtime",
        "Module 6: Inspectable Neo4j Memory",
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
# Live tool tracing and token metrics for Module 4
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


class ToolTraceHook(HookProvider):
    """Print each tool call as the agent makes it.

    Module 4 Part 2 is about watching a Gateway tool call and a memory retrieval
    interleave in one turn. Without a trace the participant sees only the final
    answer and has to take on faith that a tool ran at all, which is exactly the
    claim the module is trying to demonstrate.

    Registered as `Agent(hooks=[ToolTraceHook()])`. It only reads the events, it
    never sets `cancel_tool` or `retry`, so adding it cannot change what the
    agent does. That matters for a teaching aid: an observer that alters the run
    is not observing the run the participant is being shown.
    """

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
            print(f"     └─ raised {type(event.exception).__name__}: {_truncate(event.exception)}")
            return
        result = event.result or {}
        status = result.get("status", "unknown")
        marker = "✅" if status == "success" else "⚠️"
        blocks = result.get("content") or []
        body = " ".join(b.get("text", "") for b in blocks if isinstance(b, dict))
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
