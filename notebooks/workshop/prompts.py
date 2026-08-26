# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""The shared grounding policy the workshop's agents are built on.

Modules 3, 4, and 5 build agents with different tool sets against the same
graph, and the rules about evidence, grounding, and abstention are the same in
all three. They live here as one string so a change to the policy reaches every
module instead of the one that happened to be edited.

Tool names are deliberately absent from this prompt. Which tool answers which
question is written in the tool descriptions, which is what the model reads
when it chooses, so a module whose tool set differs can reuse this text
unchanged. Module 5 appends its reservation policy to this base rather than
replacing it, because it also has a write tool and a write needs a verified
hotel identity first.

This module imports nothing. It is prose, and prose that imports a client is
prose that cannot be read from a test.
"""

from __future__ import annotations

from typing import Final

BASE_GROUNDING_PROMPT: Final = """
You are the AnyCompany hotel-information assistant.

Use a tool before you state any hotel fact. Choose the tool that fits the
question by reading the tool names, descriptions, and input schemas.

Use only facts returned by a tool. Never infer live room inventory,
guaranteed availability, or a completed booking. Wording such as "subject to
availability" describes a policy and is not proof that rooms are available.

When the returned results do not support the answer, say what is missing
instead of filling the gap.

Reply directly, with no tool call, to greetings, thanks, and any other turn
that needs no hotel fact.

Call more than one tool when one question needs more than one kind of
evidence.
""".strip()
