# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Strands model wrapper that forces tool use for Module 3.1's grounded agent.

Kept out of the notebook because it is a workaround for a Strands library
quirk, not the ``Agent`` / ``BedrockModel`` / ``@tool`` usage the module's
README teaches. The notebook constructs ``GroundedBedrockModel`` the same way
it would construct a plain ``BedrockModel``; only this file needs to know why
a subclass is required at all.
"""

from __future__ import annotations

from strands.models import BedrockModel


class GroundedBedrockModel(BedrockModel):
    """Requires a tool call before the model may answer a fresh question.

    `tool_choice` is not a real `Agent(...)`/`BedrockModel(...)` construction
    argument: Strands only threads `tool_choice` through `Model.stream()` for
    its own internal structured-output calls, so passing it at construction
    time is silently accepted into an unused config key and never reaches a
    request. Overriding `stream()` -- the public method every model
    provider implements -- is the supported way to force tool use for a
    specific call.

    Forces `tool_choice={"any": {}}` only when the latest message is a
    fresh question (the model has not yet returned a tool result for it),
    so grounding is enforced by the API instead of by system-prompt wording
    alone. Once a tool result comes back, tool choice reverts to the
    model's normal "auto" behavior so the final answer can be free text.
    """

    async def stream(
        self,
        messages,
        tool_specs=None,
        system_prompt=None,
        *,
        tool_choice=None,
        **kwargs,
    ):
        last_message = messages[-1] if messages else None
        fresh_question = bool(
            tool_specs
            and last_message
            and last_message.get("role") == "user"
            and not any(
                "toolResult" in block for block in last_message.get("content", [])
            )
        )
        if fresh_question and tool_choice is None:
            tool_choice = {"any": {}}
        async for event in super().stream(
            messages, tool_specs, system_prompt, tool_choice=tool_choice, **kwargs
        ):
            yield event
