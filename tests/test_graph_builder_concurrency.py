# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Offline regressions for bounded parallel graph extraction."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

CONNECTED_CONTEXT = (
    Path(__file__).resolve().parents[1] / "notebooks" / "02-connected-context"
)
sys.path.insert(0, str(CONNECTED_CONTEXT))

import graph_builder


def test_build_concurrency_defaults_and_fails_closed(monkeypatch) -> None:
    monkeypatch.delenv("GRAPH_BUILD_CONCURRENCY", raising=False)
    assert graph_builder.build_concurrency() == 1

    monkeypatch.setenv("GRAPH_BUILD_CONCURRENCY", "3")
    assert graph_builder.build_concurrency() == 3

    for invalid in ("0", "9", "many"):
        monkeypatch.setenv("GRAPH_BUILD_CONCURRENCY", invalid)
        with pytest.raises(ValueError, match="GRAPH_BUILD_CONCURRENCY"):
            graph_builder.build_concurrency()


def test_ingest_bounds_parallelism_and_preserves_failure_order(
    tmp_path: Path, monkeypatch
) -> None:
    paths = [tmp_path / f"hotel-{index}.txt" for index in range(6)]
    for path in paths:
        path.write_text(f"source for {path.name}", encoding="utf-8")

    class PipelineStub:
        def __init__(self) -> None:
            self.active = 0
            self.maximum_active = 0
            self.metadata: dict[str, dict[str, object]] = {}

        async def run_async(self, **kwargs) -> None:
            self.active += 1
            self.maximum_active = max(self.maximum_active, self.active)
            self.metadata[kwargs["file_path"]] = kwargs["document_metadata"]
            try:
                await asyncio.sleep(0.01)
                if kwargs["file_path"] in {paths[1].name, paths[4].name}:
                    raise RuntimeError("expected test failure")
            finally:
                self.active -= 1

    pipeline = PipelineStub()
    monkeypatch.setenv("GRAPH_BUILD_CONCURRENCY", "3")
    monkeypatch.setattr(graph_builder, "build_contract", Mock(return_value="contract"))

    failures = asyncio.run(graph_builder.ingest(pipeline, paths))

    assert pipeline.maximum_active == 3
    assert failures == [paths[1], paths[4]]
    assert set(pipeline.metadata) == {path.name for path in paths}
    assert all(
        metadata["build_contract"] == "contract"
        for metadata in pipeline.metadata.values()
    )


def test_invalid_concurrency_stops_before_graph_mutation(monkeypatch) -> None:
    connect = Mock()
    monkeypatch.setenv("GRAPH_BUILD_CONCURRENCY", "99")
    monkeypatch.setattr(graph_builder, "connect", connect)

    result = asyncio.run(graph_builder.run_build([Path("hotel.txt")], "build"))

    assert result == 1
    connect.assert_not_called()


def test_release_script_defaults_to_three_parallel_extractions() -> None:
    script = (
        (
            Path(__file__).resolve().parents[1]
            / "tools"
            / "release"
            / "build_prebuilt_graph.sh"
        ).read_text(encoding="utf-8")
    )

    assert 'BUILD_CONCURRENCY="${GRAPH_BUILD_CONCURRENCY:-3}"' in script
    assert 'GRAPH_BUILD_CONCURRENCY="$BUILD_CONCURRENCY"' in script
