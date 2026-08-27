# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Verify source Neo4j drivers suppress deprecations and keep other notices."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import neo4j
import pytest
import verify
from workshop import fixtures, graph_connection, hybrid_retrieval

REPO_ROOT = Path(__file__).resolve().parents[1]
RESERVATION_COMMAND = (
    REPO_ROOT / "notebooks" / "03-grounded-booking-agent" / "reservation_command.py"
)
DEPRECATION_ONLY = {"notifications_disabled_classifications": ["DEPRECATION"]}


class FakeDriver:
    """Small driver stand-in for connection-construction tests."""

    def verify_connectivity(self) -> None:
        pass

    def close(self) -> None:
        pass

    def session(self, **kwargs):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args) -> None:
        pass

    def run(self, *args, **kwargs) -> list[Any]:
        return []


def load_reservation_command() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "notification_reservation_command", RESERVATION_COMMAND
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_environment_verifier_suppresses_only_deprecations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    def driver(*args, **kwargs) -> FakeDriver:
        calls.append(kwargs)
        return FakeDriver()

    monkeypatch.setattr(neo4j.GraphDatabase, "driver", driver)
    monkeypatch.setattr(verify, "hero_problems", lambda records: [])
    monkeypatch.setattr(graph_connection, "neo4j_uri", lambda: "neo4j+s://example")
    monkeypatch.setattr(graph_connection, "neo4j_auth", lambda: ("neo4j", "secret"))
    monkeypatch.setattr(graph_connection, "graph_database", lambda: "neo4j")

    assert verify.check_neo4j_hero_hotel() == []
    assert calls == [{"auth": ("neo4j", "secret"), **DEPRECATION_ONLY}]


def test_hybrid_retrieval_driver_suppresses_only_deprecations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    def driver(*args, **kwargs) -> FakeDriver:
        calls.append(kwargs)
        return FakeDriver()

    monkeypatch.setattr(hybrid_retrieval.GraphDatabase, "driver", driver)
    hybrid_retrieval._get_driver.cache_clear()
    config = hybrid_retrieval.Neo4jConfig(
        uri="neo4j+s://example",
        username="neo4j",
        password="secret",
        database="neo4j",
    )
    try:
        hybrid_retrieval._get_driver(config)
    finally:
        hybrid_retrieval._get_driver.cache_clear()

    assert calls == [{"auth": ("neo4j", "secret"), **DEPRECATION_ONLY}]


def test_fixture_driver_suppresses_only_deprecations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    def driver(*args, **kwargs) -> FakeDriver:
        calls.append(kwargs)
        return FakeDriver()

    monkeypatch.setattr(fixtures, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setattr(fixtures, "find_dotenv", lambda *args, **kwargs: "")
    monkeypatch.setattr(
        fixtures, "parse_args", lambda: SimpleNamespace(check_only=True)
    )
    monkeypatch.setattr(fixtures, "load_manifest", object)
    monkeypatch.setattr(fixtures, "_missing_configuration", list)
    monkeypatch.setattr(
        fixtures,
        "_configuration",
        lambda: ("neo4j+s://example", ("neo4j", "secret"), "neo4j"),
    )
    monkeypatch.setattr(fixtures.GraphDatabase, "driver", driver)
    monkeypatch.setattr(fixtures, "readiness_problems", lambda *args: [])

    assert fixtures.main() == 0
    assert calls == [{"auth": ("neo4j", "secret"), **DEPRECATION_ONLY}]


def test_reservation_driver_suppresses_only_deprecations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_reservation_command()
    calls: list[dict[str, Any]] = []

    def driver(*args, **kwargs) -> FakeDriver:
        calls.append(kwargs)
        return FakeDriver()

    monkeypatch.setattr(module.GraphDatabase, "driver", driver)
    module._get_driver.cache_clear()
    config = module.Neo4jCommandConfig(
        uri="neo4j+s://example",
        username="neo4j",
        password="secret",
        database="neo4j",
    )
    try:
        module._get_driver(config)
    finally:
        module._get_driver.cache_clear()

    assert calls == [{"auth": ("neo4j", "secret"), **DEPRECATION_ONLY}]
