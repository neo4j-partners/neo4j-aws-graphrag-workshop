# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Frozen service and graph contracts for the grounded retrieval and write paths.

This module intentionally contains no AWS or Neo4j clients and reads no
environment variables. It is safe to import from local tests, notebooks, the
Runtime package, and the retrieval Lambda without causing network calls or
resource changes. `retrieval_contract`, the one thing it imports, is pure
constants with no imports of its own, so that property survives.

The embedding and index contract values are re-exported rather than redefined.
Module 1 writes the embeddings and creates the indexes; Modules 2 and 3 read
them. A second definition here would let a reader change the index name in one
file, pass every check in that file's module, and leave the read path pointed
at an index the build never created.

The database name is not here. `graph_database()` lives in `graph_connection`
alongside the other environment reads, which keeps this module free of `os`.
"""

from collections.abc import Mapping
from enum import Enum
from typing import Any, Final, Literal, TypedDict

from workshop.retrieval_contract import (
    CHUNK_FULLTEXT_INDEX as CHUNK_FULLTEXT_INDEX,
    CHUNK_VECTOR_INDEX as CHUNK_VECTOR_INDEX,
    DOCUMENT_SOURCE_FILENAME_INDEX as DOCUMENT_SOURCE_FILENAME_INDEX,
    EMBEDDING_DIMENSIONS as EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL_ID as EMBEDDING_MODEL_ID,
    EMBEDDING_PURPOSE as EMBEDDING_PURPOSE,
    HOTEL_NAME_INDEX as HOTEL_NAME_INDEX,
)

HYBRID_RANKER: Final = "NAIVE"
HYBRID_TOP_K: Final = 5
MAX_AMENITIES: Final = 12

WORKSHOP_OWNER: Final = "neo4j-ftw-demo-6"
FIXTURE_MANIFEST_VERSION: Final = 1
MAX_GUESTS_RULE_ID: Final = "demo-06-maximum-guests"
MAX_GUESTS: Final = 10
OVER_LIMIT_GUESTS: Final = 15

# The three with no safe default, as read by callers that build their own config
# dict. `graph_connection.REQUIRED_ENV_VARS` is the shorter list the setup check
# uses, because the username defaults there.
REQUIRED_NEO4J_ENV: Final = (
    "NEO4J_URI",
    "NEO4J_USERNAME",
    "NEO4J_PASSWORD",
)
LOCAL_NEO4J_ENV: Final = (*REQUIRED_NEO4J_ENV, "NEO4J_DATABASE")
RETRIEVAL_SECRET_ID_ENV: Final = "NEO4J_RETRIEVAL_SECRET_ID"
COMMAND_SECRET_ID_ENV: Final = "NEO4J_COMMAND_SECRET_ID"
SECRET_FIELDS: Final = ("uri", "username", "password", "database")


class _StrEnum(str, Enum):
    """`enum.StrEnum` for interpreters that predate it.

    The Vocareum lab image runs CPython 3.10.14, where `enum.StrEnum` does not
    exist. Plain `(str, Enum)` is not a drop-in replacement: it inherits
    `Enum.__str__` and `Enum.__format__`, so `str(member)` and `f"{member}"`
    render as `ReservationStatus.ACCEPTED` rather than `accepted`. Pinning both
    dunders to the `str` versions is exactly what `StrEnum` does, which keeps
    every member interchangeable with its value on 3.10 and on 3.11 or later.
    """

    __str__ = str.__str__
    __format__ = str.__format__


class ReservationStatus(_StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    ERROR = "error"


class ReservationReason(_StrEnum):
    MAX_GUESTS_EXCEEDED = "max_guests_exceeded"
    UNKNOWN_HOTEL = "unknown_hotel"
    INVALID_DATES = "invalid_dates"
    UNAUTHORIZED = "unauthorized"
    SERVICE_ERROR = "service_error"


class HotelContext(TypedDict):
    chunk_text: str
    combined_score: float
    exact_terms: list[str]
    hotel_id: str | None
    hotel_name: str | None
    address: str | None
    guest_rating: float | None
    amenities: list[str]


class ReservationCommandInput(TypedDict):
    request_id: str
    hotel_id: str
    check_in: str
    check_out: str
    guests: int


# Split rather than written with `NotRequired`, which is 3.11 and later only.
# A `total=False` base carries the optional keys, and the subclass below adds
# the required ones, which is the same required and optional split.
class _ReservationCommandResponseOptional(TypedDict, total=False):
    reason_code: Literal[
        "max_guests_exceeded",
        "unknown_hotel",
        "invalid_dates",
        "unauthorized",
        "service_error",
    ]
    max_guests: int
    created_at: str


class ReservationCommandResponse(_ReservationCommandResponseOptional):
    status: Literal["accepted", "rejected", "error"]
    request_id: str
    hotel_id: str
    duplicate: bool
    message: str


def retrieval_input_schema() -> dict[str, object]:
    return {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "minLength": 1,
                "description": "Natural-language hotel question.",
            }
        },
        "required": ["query"],
        "additionalProperties": False,
    }


def reservation_input_schema() -> dict[str, object]:
    return {
        "type": "object",
        "properties": {
            "request_id": {
                "type": "string",
                "format": "uuid",
                "description": "Caller-created UUID. Reuse it if this command is retried.",
            },
            "hotel_id": {
                "type": "string",
                "minLength": 1,
                "description": "Opaque stable hotel ID returned by grounded retrieval.",
            },
            "check_in": {
                "type": "string",
                "format": "date",
                "description": "Check-in date in YYYY-MM-DD format.",
            },
            "check_out": {
                "type": "string",
                "format": "date",
                "description": "Check-out date in YYYY-MM-DD format.",
            },
            "guests": {
                "type": "integer",
                "minimum": 1,
                "description": "Requested number of guests.",
            },
        },
        "required": ["request_id", "hotel_id", "check_in", "check_out", "guests"],
        "additionalProperties": False,
    }


# --------------------------------------------------------------------------- #
# The AgentCore projection
# --------------------------------------------------------------------------- #
#
# AgentCore reads a subset of JSON Schema when a Gateway target registers a
# tool: per property it takes `type`, `description`, and `items`, and it does
# not take `minLength`, `format`, or `additionalProperties`. The schemas above
# keep those, because they are the closed contract each handler validates
# against at its own trust boundary. What the Gateway is handed is the
# projection below.
#
# It lives here rather than beside the Module 4 notebook because Module 5
# registers the same tools and cannot import a module that sits outside the
# `workshop` package. One projection, imported by both, is also the only way a
# key AgentCore later starts accepting gets added in one place.
GATEWAY_PROPERTY_KEYS: Final = frozenset({"type", "description", "items"})


def lambda_function_name(tool_name: str) -> str:
    """Keep the model-visible tool base name in its fresh Lambda name."""
    return f"hotel-booking-{tool_name}"


def gateway_input_schema(schema: Mapping[str, Any]) -> dict[str, Any]:
    """Project the complete contract onto AgentCore's supported subset."""
    return {
        "type": schema["type"],
        "properties": {
            name: {
                key: value
                for key, value in definition.items()
                if key in GATEWAY_PROPERTY_KEYS
            }
            for name, definition in schema["properties"].items()
        },
        "required": schema["required"],
    }


def gateway_base_name(full_name: str) -> str:
    """Remove AgentCore's target prefix from a model-visible tool name."""
    prefix, separator, base_name = full_name.rpartition("___")
    return base_name if prefix and separator else full_name


def gateway_reservation_input_schema() -> dict[str, Any]:
    """Project the closed command schema onto AgentCore's accepted subset."""
    return gateway_input_schema(reservation_input_schema())
