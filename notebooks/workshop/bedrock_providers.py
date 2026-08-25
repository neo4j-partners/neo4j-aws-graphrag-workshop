# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""
Amazon Bedrock providers for neo4j-graphrag.

Replaces OpenAI dependencies with:
- Amazon Nova 2 Multimodal Embeddings for embeddings
- Amazon Bedrock Claude for LLM entity extraction

No OpenAI API key required, AWS credentials only.
"""

import asyncio
import json
import os
from collections.abc import Sequence
from typing import Any

import boto3
from botocore.config import Config
from neo4j_graphrag.llm.base import LLMInterface, LLMResponse
from neo4j_graphrag.embeddings.base import Embedder
from neo4j_graphrag.message_history import MessageHistory
from neo4j_graphrag.types import LLMMessage

from workshop.aws_region import aws_region
from workshop.retrieval_contract import (
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL_ID,
    EMBEDDING_PURPOSE,
)


# botocore defaults to a 60s read timeout, so one hung call can burn minutes.
# graph_builder wraps each document in a 180s asyncio.wait_for, and that outer
# bound cannot govern a larger inner one: the timeout fires while the worker
# thread keeps running underneath, because a thread cannot be cancelled.
#
# Adaptive mode is what makes a room of thirty simultaneous Module 1 builds
# survivable. It adds a client-side rate limiter that slows requests down when
# Bedrock starts returning throttling errors, instead of every participant
# retrying into the same per-region on-demand quota at full speed.
#
# botocore reads max_attempts as a retry count and normalises it to
# total_max_attempts, so 5 here is 6 total attempts. A throttling response comes
# back fast and costs backoff rather than a full read timeout, so those extra
# attempts are cheap in the case they exist for. The expensive case, six
# consecutive sockets that hang for the full 45s, adds up to 270s and outlasts
# the 180s per-document bound: the wait_for still fires and the build moves on,
# while the worker thread underneath keeps running to its own end. That is the
# trade being made here, throughput under throttling against a thread that can
# outlive its document. Raise DOC_TIMEOUT_SECONDS or lower read_timeout if you
# want the inner chain back inside the outer bound.
#
# The longer-term fix is swapping `asyncio.to_thread` for a `ProcessPoolExecutor`
# future: a process can be terminated on timeout where a thread cannot, so
# "timed out" would finally mean "stopped" instead of "abandoned but running."
BEDROCK_CONFIG = Config(
    read_timeout=45, retries={"max_attempts": 5, "mode": "adaptive"}
)

# The one chat model the workshop runs on. Every module that builds an agent or
# an extraction LLM reads it from here rather than restating the literal, so a
# participant who has enabled a different model in their region changes one
# line. `MODEL_ID` overrides it for a module that needs to.
DEFAULT_MODEL_ID = "us.anthropic.claude-sonnet-5"


def default_model_id() -> str:
    """Return the workshop chat model, letting `MODEL_ID` override it."""
    return os.environ.get("MODEL_ID") or DEFAULT_MODEL_ID


def _strip_code_fence(text: str) -> str:
    """Remove a surrounding markdown code fence, if the model added one.

    neo4j-graphrag parses entity-extraction responses as raw JSON, but Claude
    commonly wraps JSON in ```json ... ``` fences. Left in place, every chunk
    fails with "LLM response has improper format" and the graph comes out empty.
    """
    stripped = text.strip()
    if not stripped.startswith("```"):
        return text

    # Only strip when the closing fence is also present. A truncated response
    # carrying an opening fence but no closing one would otherwise drop its
    # first line and hand back broken JSON.
    lines = stripped.splitlines()
    if len(lines) < 2 or lines[-1].strip() != "```":
        return text
    return "\n".join(lines[1:-1]).strip()


def _converse_messages(message_history) -> list[dict]:
    """Convert a neo4j-graphrag message history into Converse API messages.

    `LLMMessage` is a TypedDict, so history entries arrive as plain dicts.
    Attribute access silently misses on those: every turn would collapse to the
    dict's repr carried under role "user", relabelling assistant turns as user.
    A `MessageHistory` object holds the same dicts on `.messages`.
    """
    messages = getattr(message_history, "messages", message_history)

    converted = []
    for msg in messages:
        if isinstance(msg, dict):
            role = msg.get("role", "user")
            content = msg.get("content", "")
        else:
            role = getattr(msg, "role", "user")
            content = getattr(msg, "content", str(msg))
        converted.append({"role": role, "content": [{"text": content}]})
    return converted


class BedrockEmbeddings(Embedder):
    """Amazon Bedrock embeddings using Nova 2 Multimodal Embeddings.

    This is the only embedder in the workshop. Module 1 writes chunk vectors
    with it and Modules 2 onward embed their queries with it, which is what
    keeps the write and read paths on one model, one purpose, and one width. A
    second embedder class defined anywhere else would agree with this one only
    by coincidence, and a disagreement returns wrong results with no error.
    """

    def __init__(
        self,
        model_id: str = EMBEDDING_MODEL_ID,
        region_name: str | None = None,
        dimensions: int = EMBEDDING_DIMENSIONS,
        *,
        bedrock_client: Any | None = None,
    ):
        # The embedding model and its width are frozen contract constants, not
        # a preference, so unlike the chat model they take no environment
        # override. Module 1 writes the chunk vectors with these values and
        # Modules 2 onward query against them; an override would let the read
        # path move while the stored vectors stayed put, which returns wrong
        # results with no error.
        # Resolve the region inside the body: an os.environ default argument is
        # evaluated once at import, before the caller can set AWS_REGION.
        if region_name is None:
            region_name = aws_region()
        self.model_id = model_id
        self.dimensions = dimensions
        # `bedrock_client` exists so a test can assert the request payload
        # without a network call. Production callers leave it unset.
        self.client = bedrock_client or boto3.client(
            "bedrock-runtime", region_name=region_name, config=BEDROCK_CONFIG
        )

    def embed_query(self, text: str) -> list[float]:
        response = self.client.invoke_model(
            modelId=self.model_id,
            body=json.dumps({
                "taskType": "SINGLE_EMBEDDING",
                "singleEmbeddingParams": {
                    "embeddingPurpose": EMBEDDING_PURPOSE,
                    "embeddingDimension": self.dimensions,
                    "text": {"truncationMode": "END", "value": text},
                },
            }),
            contentType="application/json",
            accept="application/json",
        )
        result = json.loads(response["body"].read())
        return result["embeddings"][0]["embedding"]


class BedrockLLM(LLMInterface):
    """Amazon Bedrock LLM using Claude via the Converse API."""

    def __init__(
        self,
        model_id: str | None = None,
        region_name: str | None = None,
        temperature: float | None = None,
        max_tokens: int = 4096,
    ):
        # Resolve the region inside the body: an os.environ default argument is
        # evaluated once at import, before the caller can set AWS_REGION.
        if region_name is None:
            region_name = aws_region()
        # Same reason, and it is the whole point of the MODEL_ID override:
        # defaulting to the DEFAULT_MODEL_ID literal here would bind the model
        # at import and leave Module 1's extraction calls on the built-in one
        # while every Strands agent in the tree honored the environment.
        self.model_id = model_id or default_model_id()
        self.client = boto3.client(
            "bedrock-runtime", region_name=region_name, config=BEDROCK_CONFIG
        )
        self.temperature = temperature
        self.max_tokens = max_tokens

    def invoke(self, input: str,
               message_history: Sequence[LLMMessage] | MessageHistory | None = None,
               system_instruction: str | None = None) -> LLMResponse:
        messages = _converse_messages(message_history) if message_history else []
        messages.append({"role": "user", "content": [{"text": input}]})

        inference_config = {"maxTokens": self.max_tokens}

        # Sonnet 5 rejects `temperature` outright ("deprecated for this model"),
        # so only send it when a caller explicitly asks for one.
        if self.temperature is not None:
            inference_config["temperature"] = self.temperature

        kwargs = {
            "modelId": self.model_id,
            "messages": messages,
            "inferenceConfig": inference_config,
        }

        if system_instruction:
            kwargs["system"] = [{"text": system_instruction}]

        response = self.client.converse(**kwargs)
        blocks = response["output"]["message"]["content"]

        # Sonnet 5 puts a reasoningContent block before the answer, so take the
        # first block that actually carries text instead of assuming index 0.
        content = next((b["text"] for b in blocks if "text" in b), None)
        if content is None:
            raise ValueError(f"No text block in Bedrock response: {[list(b) for b in blocks]}")

        return LLMResponse(content=_strip_code_fence(content))

    async def ainvoke(self, input: str, message_history=None, system_instruction=None) -> LLMResponse:
        # `invoke` is a blocking botocore round trip. Awaiting it inline would
        # block the event loop, so the `asyncio.wait_for` per-document timeout
        # in graph_builder could never fire. Hand it to a worker thread.
        return await asyncio.to_thread(
            self.invoke, input, message_history, system_instruction
        )
