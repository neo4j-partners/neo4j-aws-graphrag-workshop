# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Narrow, idempotent reservation-request command for Module 3.1.

The command reads one enabled Neo4j rule, matches one prepared fixture hotel,
and writes one workshop-owned ``ReservationRequest``. It does not book a room,
change hotel data, or implement payment, confirmation, or cancellation.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from typing import Any, Mapping
from uuid import UUID

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from neo4j import Driver, GraphDatabase, Transaction
from neo4j.exceptions import AuthError, ConstraintError, DriverError, Neo4jError

from workshop import contracts, graph_connection

LOGGER = logging.getLogger(__name__)

READ_EXISTING_QUERY = """
CYPHER 25
MATCH (request:ReservationRequest {request_id: $request_id})
OPTIONAL MATCH (request)-[relationship:FOR_HOTEL]->(hotel:Hotel)
WITH request,
     count(relationship) AS relationship_count,
     [hotel_id IN collect(DISTINCT hotel.hotel_id)
      WHERE hotel_id IS NOT NULL] AS hotel_ids
RETURN request.workshop_owner AS workshop_owner,
       request.status AS status,
       request.check_in AS check_in,
       request.check_out AS check_out,
       request.guests AS guests,
       toString(request.created_at) AS created_at,
       relationship_count,
       hotel_ids
""".strip()

READ_TARGETS_QUERY = """
CYPHER 25
OPTIONAL MATCH (rule:Rule {rule_id: $rule_id})
WHERE rule.enabled = true AND rule.workshop_owner = $workshop_owner
WITH collect(rule) AS rules
OPTIONAL MATCH (hotel:Hotel {hotel_id: $hotel_id})
WHERE hotel.demo6_fixture = true
RETURN size(rules) AS rule_count,
       CASE WHEN size(rules) = 1 THEN rules[0].max_guests END AS max_guests,
       CASE WHEN size(rules) = 1 THEN rules[0].rejection_message END
           AS rejection_message,
       count(hotel) AS hotel_count,
       head(collect(hotel.hotel_id)) AS hotel_id
""".strip()

CREATE_REQUEST_QUERY = """
CYPHER 25
MATCH (rule:Rule {rule_id: $rule_id})
WHERE rule.enabled = true
  AND rule.workshop_owner = $workshop_owner
WITH collect(rule) AS rules
WHERE size(rules) = 1 AND $guests <= rules[0].max_guests
MATCH (hotel:Hotel {hotel_id: $hotel_id})
WHERE hotel.demo6_fixture = true
WITH rules, collect(hotel) AS hotels
WHERE size(hotels) = 1
WITH hotels[0] AS hotel
CREATE (request:ReservationRequest {
    request_id: $request_id,
    check_in: $check_in,
    check_out: $check_out,
    guests: $guests,
    workshop_owner: $workshop_owner,
    status: 'accepted',
    created_at: datetime()
})
CREATE (request)-[:FOR_HOTEL]->(hotel)
RETURN request.request_id AS request_id,
       hotel.hotel_id AS hotel_id,
       toString(request.created_at) AS created_at
""".strip()


@dataclass(frozen=True)
class Neo4jCommandConfig:
    """Connection values used by the reservation Lambda.

    Near-identical to ``hybrid_retrieval.Neo4jConfig``, and deliberately not
    imported from it. The Lambda deployment package installs this package with
    ``--no-deps``, so every import this module makes has to resolve from the
    Lambda's own short dependency list. ``hybrid_retrieval`` imports
    ``neo4j-graphrag``, which the reservation handler never uses and which would
    add tens of megabytes to the zip; importing from it here builds fine and
    fails at Lambda cold start. Keep the two in step by hand, and keep the
    shared constants they both read in ``contracts``.
    """

    uri: str
    username: str
    password: str
    database: str

    @classmethod
    def from_environment(cls) -> "Neo4jCommandConfig":
        """Load local connection values without making a network call."""
        values = {name: os.environ.get(name) for name in contracts.REQUIRED_NEO4J_ENV}
        missing = [name for name, value in values.items() if not value]
        if missing:
            names = ", ".join(missing)
            raise ValueError(f"Missing required Neo4j environment values: {names}")
        return cls(
            uri=values["NEO4J_URI"] or "",
            username=values["NEO4J_USERNAME"] or "",
            password=values["NEO4J_PASSWORD"] or "",
            database=graph_connection.graph_database(),
        )

    @classmethod
    def from_secret(
        cls,
        secret_id: str,
        *,
        secrets_client: Any | None = None,
    ) -> "Neo4jCommandConfig":
        """Load the deployed command connection from Secrets Manager."""
        client = secrets_client or boto3.client("secretsmanager")
        response = client.get_secret_value(SecretId=secret_id)
        secret = json.loads(response["SecretString"])
        if not isinstance(secret, dict):
            raise ValueError("Neo4j secret must contain a JSON object")
        missing = [name for name in contracts.SECRET_FIELDS if not secret.get(name)]
        if missing:
            names = ", ".join(missing)
            raise ValueError(f"Neo4j secret is missing required fields: {names}")
        return cls(**{name: secret[name] for name in contracts.SECRET_FIELDS})


@dataclass(frozen=True)
class ReservationRequest:
    """Validated command input safe to use as Cypher parameters."""

    request_id: str
    hotel_id: str
    check_in: str
    check_out: str
    guests: int


class InvalidCommand(ValueError):
    """Raised when an event does not satisfy the closed command contract."""


class InvalidDates(InvalidCommand):
    """Raised when reservation dates do not satisfy the date contract."""


class CommandStateError(RuntimeError):
    """Raised when prepared Neo4j state violates the command contract."""


class RequestConflictError(CommandStateError):
    """Raised when a request ID is reused with different command input."""


def _safe_correlation_id(payload: Mapping[str, Any]) -> str:
    value = payload.get("request_id")
    if not isinstance(value, str):
        return "invalid"
    try:
        return str(UUID(value))
    except ValueError:
        return "invalid"


@lru_cache(maxsize=2)
def _get_driver(config: Neo4jCommandConfig) -> Driver:
    """Reuse the Neo4j driver across warm Lambda invocations."""
    return GraphDatabase.driver(
        config.uri,
        auth=(config.username, config.password),
        notifications_min_severity="OFF",
    )


def _extract_payload(event: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(event, Mapping):
        raise InvalidCommand("event must be a JSON object")

    parameters = event.get("parameters")
    if isinstance(parameters, Mapping):
        return parameters

    if "body" in event:
        body = event["body"]
        if isinstance(body, str):
            decoded = json.loads(body)
            if not isinstance(decoded, Mapping):
                raise InvalidCommand("body must contain a JSON object")
            return decoded
        if isinstance(body, Mapping):
            return body
        raise InvalidCommand("body must be an object or a JSON object string")
    return event


def _validate_command(payload: Mapping[str, Any]) -> ReservationRequest:
    expected = {"request_id", "hotel_id", "check_in", "check_out", "guests"}
    if set(payload) != expected:
        raise InvalidCommand("command fields do not match the closed input contract")

    request_id = payload["request_id"]
    hotel_id = payload["hotel_id"]
    guests = payload["guests"]
    if not isinstance(request_id, str):
        raise InvalidCommand("request_id must be a UUID string")
    try:
        normalized_request_id = str(UUID(request_id))
    except (ValueError, AttributeError) as exc:
        raise InvalidCommand("request_id must be a UUID string") from exc
    if normalized_request_id != request_id:
        raise InvalidCommand("request_id must use canonical UUID format")
    if not isinstance(hotel_id, str) or not hotel_id.strip():
        raise InvalidCommand("hotel_id must be a non-empty string")
    if not isinstance(guests, int) or isinstance(guests, bool) or guests < 1:
        raise InvalidCommand("guests must be a positive integer")

    raw_check_in = payload["check_in"]
    raw_check_out = payload["check_out"]
    if not isinstance(raw_check_in, str) or not isinstance(raw_check_out, str):
        raise InvalidDates("dates must use YYYY-MM-DD")
    try:
        check_in = date.fromisoformat(raw_check_in)
        check_out = date.fromisoformat(raw_check_out)
    except (TypeError, ValueError) as exc:
        raise InvalidDates("dates must use YYYY-MM-DD") from exc
    if raw_check_in != check_in.isoformat() or raw_check_out != check_out.isoformat():
        raise InvalidDates("dates must use YYYY-MM-DD")
    if check_out <= check_in:
        raise InvalidDates("check-out must be after check-in")

    return ReservationRequest(
        request_id=normalized_request_id,
        hotel_id=hotel_id.strip(),
        check_in=check_in.isoformat(),
        check_out=check_out.isoformat(),
        guests=guests,
    )


def _accepted(
    request_id: str,
    hotel_id: str,
    created_at: str,
    *,
    duplicate: bool,
) -> contracts.ReservationCommandResponse:
    message = (
        "Reservation request already exists; no changes were made."
        if duplicate
        else "Reservation request created."
    )
    return {
        "status": contracts.ReservationStatus.ACCEPTED.value,
        "request_id": request_id,
        "hotel_id": hotel_id,
        "duplicate": duplicate,
        "message": message,
        "created_at": created_at,
    }


def _rejected(
    command: ReservationRequest,
    reason: contracts.ReservationReason,
    message: str,
    *,
    max_guests: int | None = None,
) -> contracts.ReservationCommandResponse:
    response: contracts.ReservationCommandResponse = {
        "status": contracts.ReservationStatus.REJECTED.value,
        "request_id": command.request_id,
        "hotel_id": command.hotel_id,
        "duplicate": False,
        "reason_code": reason.value,
        "message": message,
    }
    if max_guests is not None:
        response["max_guests"] = max_guests
    return response


def _error(
    request_id: str,
    hotel_id: str,
    reason: contracts.ReservationReason,
    message: str,
) -> contracts.ReservationCommandResponse:
    return {
        "status": contracts.ReservationStatus.ERROR.value,
        "request_id": request_id,
        "hotel_id": hotel_id,
        "duplicate": False,
        "reason_code": reason.value,
        "message": message,
    }


def _invalid_dates_response(
    request_id: str,
    hotel_id: str,
    message: str,
) -> contracts.ReservationCommandResponse:
    return {
        "status": contracts.ReservationStatus.REJECTED.value,
        "request_id": request_id,
        "hotel_id": hotel_id,
        "duplicate": False,
        "reason_code": contracts.ReservationReason.INVALID_DATES.value,
        "message": message,
    }


def _unauthorized(
    command: ReservationRequest,
) -> contracts.ReservationCommandResponse:
    LOGGER.warning(
        "reservation command unauthorized request_id=%s",
        command.request_id,
    )
    return _error(
        command.request_id,
        command.hotel_id,
        contracts.ReservationReason.UNAUTHORIZED,
        "Reservation command is not authorized.",
    )


def _service_failure(
    command: ReservationRequest,
) -> contracts.ReservationCommandResponse:
    LOGGER.error(
        "reservation command failed request_id=%s",
        command.request_id,
    )
    return _error(
        command.request_id,
        command.hotel_id,
        contracts.ReservationReason.SERVICE_ERROR,
        "Reservation service is unavailable.",
    )


def _request_conflict(
    command: ReservationRequest,
) -> contracts.ReservationCommandResponse:
    LOGGER.warning(
        "reservation request conflict request_id=%s",
        command.request_id,
    )
    return _error(
        command.request_id,
        command.hotel_id,
        contracts.ReservationReason.SERVICE_ERROR,
        "Request ID is already used for a different reservation request.",
    )


def _existing_response(
    record: Mapping[str, Any] | None,
    command: ReservationRequest,
) -> contracts.ReservationCommandResponse | None:
    if record is None:
        return None
    hotel_ids = record.get("hotel_ids") or []
    if (
        record.get("workshop_owner") != contracts.WORKSHOP_OWNER
        or record.get("status") != contracts.ReservationStatus.ACCEPTED.value
        or not record.get("created_at")
        or record.get("relationship_count") != 1
        or len(hotel_ids) != 1
    ):
        raise CommandStateError("existing request violates the command contract")
    if (
        record.get("check_in") != command.check_in
        or record.get("check_out") != command.check_out
        or record.get("guests") != command.guests
        or hotel_ids[0] != command.hotel_id
    ):
        raise RequestConflictError("request ID was reused with different input")
    return _accepted(
        command.request_id,
        command.hotel_id,
        record["created_at"],
        duplicate=True,
    )


def _execute_command(
    transaction: Transaction,
    command: ReservationRequest,
    today: date,
) -> contracts.ReservationCommandResponse:
    parameters = {
        "request_id": command.request_id,
        "hotel_id": command.hotel_id,
        "check_in": command.check_in,
        "check_out": command.check_out,
        "guests": command.guests,
        "rule_id": contracts.MAX_GUESTS_RULE_ID,
        "workshop_owner": contracts.WORKSHOP_OWNER,
    }
    existing = transaction.run(
        READ_EXISTING_QUERY,
        request_id=command.request_id,
    ).single()
    duplicate = _existing_response(existing, command)
    if duplicate is not None:
        return duplicate

    if date.fromisoformat(command.check_in) < today:
        return _invalid_dates_response(
            command.request_id,
            command.hotel_id,
            "check-in cannot be in the past",
        )

    targets = transaction.run(READ_TARGETS_QUERY, **parameters).single()
    if (
        targets is None
        or targets.get("rule_count") != 1
        or targets.get("max_guests") is None
    ):
        raise CommandStateError("enabled maximum-guests rule is unavailable")
    if targets.get("hotel_count") == 0:
        return _rejected(
            command,
            contracts.ReservationReason.UNKNOWN_HOTEL,
            "Hotel is not a prepared workshop fixture.",
        )
    if targets.get("hotel_count") != 1 or targets.get("hotel_id") != command.hotel_id:
        raise CommandStateError("fixture hotel identity is ambiguous")

    max_guests = targets["max_guests"]
    if (
        not isinstance(max_guests, int)
        or isinstance(max_guests, bool)
        or max_guests < 1
    ):
        raise CommandStateError("maximum-guests rule is invalid")
    rejection_message = targets.get("rejection_message")
    if not isinstance(rejection_message, str) or not rejection_message.strip():
        raise CommandStateError("maximum-guests rejection message is invalid")
    if command.guests > max_guests:
        return _rejected(
            command,
            contracts.ReservationReason.MAX_GUESTS_EXCEEDED,
            rejection_message,
            max_guests=max_guests,
        )

    created = transaction.run(CREATE_REQUEST_QUERY, **parameters).single()
    if (
        created is None
        or created.get("hotel_id") != command.hotel_id
        or not created.get("created_at")
    ):
        raise CommandStateError("prepared rule or hotel changed during the command")
    return _accepted(
        command.request_id,
        command.hotel_id,
        created["created_at"],
        duplicate=False,
    )


def _read_duplicate(
    transaction: Transaction,
    command: ReservationRequest,
) -> contracts.ReservationCommandResponse:
    record = transaction.run(
        READ_EXISTING_QUERY,
        request_id=command.request_id,
    ).single()
    response = _existing_response(record, command)
    if response is None:
        raise CommandStateError("duplicate request was not readable after retry")
    return response


def create_reservation_request(
    payload: Mapping[str, Any],
    *,
    driver: Driver,
    database: str,
    today: date | None = None,
) -> contracts.ReservationCommandResponse:
    """Validate and execute one reservation request without hidden side effects."""
    request_id = str(payload.get("request_id") or "")
    hotel_id = str(payload.get("hotel_id") or "")
    effective_today = today or date.today()
    try:
        command = _validate_command(payload)
    except InvalidDates as exc:
        return _invalid_dates_response(
            request_id,
            hotel_id,
            str(exc),
        )
    except InvalidCommand:
        return _error(
            request_id,
            hotel_id,
            contracts.ReservationReason.SERVICE_ERROR,
            "Reservation command input is invalid.",
        )

    try:
        with driver.session(database=database) as session:
            return session.execute_write(
                _execute_command,
                command,
                effective_today,
            )
    except ConstraintError:
        # A concurrent delivery may win the request_id uniqueness race. The
        # losing transaction is rolled back, then reads the winner unchanged.
        try:
            with driver.session(database=database) as session:
                return session.execute_read(
                    _read_duplicate,
                    command,
                )
        except AuthError:
            return _unauthorized(command)
        except RequestConflictError:
            return _request_conflict(command)
        except (DriverError, Neo4jError, CommandStateError):
            return _service_failure(command)
    except AuthError:
        return _unauthorized(command)
    except RequestConflictError:
        return _request_conflict(command)
    except (DriverError, Neo4jError, CommandStateError):
        return _service_failure(command)


def handler(
    event: Mapping[str, Any],
    context: Any,
) -> contracts.ReservationCommandResponse:
    """AWS Lambda entry point for the one Gateway command target."""
    del context
    try:
        payload = _extract_payload(event)
    except (InvalidCommand, json.JSONDecodeError):
        return _error(
            "",
            "",
            contracts.ReservationReason.SERVICE_ERROR,
            "Reservation command input is invalid.",
        )

    try:
        secret_id = os.environ.get(contracts.COMMAND_SECRET_ID_ENV)
        config = (
            Neo4jCommandConfig.from_secret(secret_id)
            if secret_id
            else Neo4jCommandConfig.from_environment()
        )
        driver = _get_driver(config)
    except (
        ValueError,
        KeyError,
        json.JSONDecodeError,
        BotoCoreError,
        ClientError,
        DriverError,
        Neo4jError,
    ):
        request_id = _safe_correlation_id(payload)
        LOGGER.error("reservation command configuration failed request_id=%s", request_id)
        return _error(
            request_id,
            str(payload.get("hotel_id") or ""),
            contracts.ReservationReason.SERVICE_ERROR,
            "Reservation service is unavailable.",
        )
    return create_reservation_request(
        payload,
        driver=driver,
        database=config.database,
    )
