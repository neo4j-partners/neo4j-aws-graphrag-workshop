#!/usr/bin/env bash
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
#
# Used for: a maintainer's rare local validation of a release-candidate graph.
#
# Restore a prebuilt candidate into isolated local Neo4j, validate it, and add
# the five Module 1 held-out documents through the participant build path.
# This never connects to Aura. Set --retain to leave the validated 300-document
# container and volume available for subsequent local evidence collection.

set -euo pipefail

usage() {
  echo "Usage: tools/release/run_additive_validation.sh [--retain] [candidate.dump] [output-dir]"
  echo "Environment: NEO4J_IMAGE (default: neo4j:latest)"
}

RETAIN=false
if [[ "${1:-}" == "--retain" ]]; then
  RETAIN=true
  shift
fi
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi
if [[ "$#" -gt 2 ]]; then
  usage >&2
  exit 2
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CANDIDATE="${1:-$REPO_ROOT/evidence/build/neo4j-hotel-graph-prebuilt.dump}"
RUN_TIMESTAMP="$(date -u +"%Y%m%dT%H%M%SZ")"
OUTPUT_DIR="${2:-$REPO_ROOT/evidence/additive-$RUN_TIMESTAMP}"
IMAGE="${NEO4J_IMAGE:-neo4j:latest}"
RUN_ID="additive-validate-$$"
VOLUME="neo4j-$RUN_ID"
LOADER="neo4j-$RUN_ID-loader"
CONTAINER="neo4j-$RUN_ID-server"
PASSWORD="$RUN_ID-password"
DATABASE="neo4j"
SCRATCH="$(mktemp -d)"
cleanup() {
  docker rm -f "$LOADER" >/dev/null 2>&1 || true
  if [[ "$RETAIN" == true ]]; then
    echo "Retained local Neo4j container: $CONTAINER" >&2
    echo "Retained local Neo4j volume: $VOLUME" >&2
  else
    docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
    docker volume rm "$VOLUME" >/dev/null 2>&1 || true
  fi
  rm -rf "$SCRATCH"
}
trap cleanup EXIT

if [[ ! -f "$CANDIDATE" ]]; then
  echo "Candidate dump does not exist: $CANDIDATE" >&2
  exit 1
fi
if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required to restore and validate the candidate." >&2
  exit 1
fi
if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required to run the repository validators." >&2
  exit 1
fi
if [[ -e "$OUTPUT_DIR/additive-wrapper.json" || -e "$OUTPUT_DIR/additive-validation.json" ]]; then
  echo "Evidence already exists in $OUTPUT_DIR; choose a new output directory." >&2
  exit 1
fi

mkdir -p "$SCRATCH/dumps" "$OUTPUT_DIR"
cp "$CANDIDATE" "$SCRATCH/dumps/neo4j.dump"
docker volume create "$VOLUME" >/dev/null

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  docker pull "$IMAGE"
fi
IMAGE_ID="$(docker image inspect --format '{{.Id}}' "$IMAGE")"

echo "Restoring candidate with $IMAGE ($IMAGE_ID)..."
docker run --rm --name "$LOADER" \
  -v "$VOLUME:/data" \
  -v "$SCRATCH/dumps:/dumps:ro" \
  "$IMAGE" \
  neo4j-admin database load \
    --from-path=/dumps "$DATABASE" --overwrite-destination=true \
  >"$OUTPUT_DIR/restore.log" 2>&1

docker run -d --name "$CONTAINER" \
  -v "$VOLUME:/data" \
  -p 127.0.0.1::7687 \
  --memory 4g \
  --memory-swap 4g \
  -e NEO4J_AUTH="neo4j/$PASSWORD" \
  -e 'NEO4J_PLUGINS=["apoc"]' \
  -e 'NEO4J_dbms_security_procedures_unrestricted=apoc.*' \
  -e NEO4J_server_memory_heap_initial__size=512m \
  -e NEO4J_server_memory_heap_max__size=1536m \
  -e NEO4J_server_memory_pagecache_size=1g \
  "$IMAGE" >/dev/null

BOLT_ENDPOINT="$(docker port "$CONTAINER" 7687/tcp)"
BOLT_PORT="${BOLT_ENDPOINT##*:}"
if [[ ! "$BOLT_PORT" =~ ^[0-9]+$ ]]; then
  echo "Could not determine the disposable Neo4j Bolt port: $BOLT_ENDPOINT" >&2
  exit 1
fi

for _ in $(seq 1 60); do
  if docker exec "$CONTAINER" cypher-shell \
    -u neo4j -p "$PASSWORD" "RETURN 1" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
docker exec "$CONTAINER" cypher-shell \
  -u neo4j -p "$PASSWORD" "RETURN 1" >/dev/null

APOC_PROCEDURE_COUNT="$(
  docker exec "$CONTAINER" cypher-shell --format plain \
    -u neo4j -p "$PASSWORD" \
    "SHOW PROCEDURES YIELD name
     WHERE name = 'apoc.merge.relationship'
     RETURN count(*) AS procedure_count" |
    tail -n 1 | tr -d '\r'
)"
if [[ "$APOC_PROCEDURE_COUNT" != "1" ]]; then
  echo "APOC prerequisite failed: apoc.merge.relationship is unavailable." >&2
  exit 1
fi

run_validator() {
  local log_path="$1"
  shift
  NEO4J_URI="bolt://localhost:$BOLT_PORT" \
  NEO4J_USERNAME=neo4j \
  NEO4J_PASSWORD="$PASSWORD" \
  NEO4J_DATABASE="$DATABASE" \
  uv run --project "$REPO_ROOT/notebooks/workshop" --locked \
    python "$@" >"$log_path" 2>&1
}

echo "Validating the restored 295-document candidate..."
run_validator "$OUTPUT_DIR/prebuilt-source-reconciliation.log" \
  "$REPO_ROOT/tools/release/validate_graph_amenities.py" --mode prebuilt
run_validator "$OUTPUT_DIR/prebuilt-candidate-validation.log" \
  "$REPO_ROOT/tools/release/validate_prebuilt_candidate.py"

echo "Adding and reconciling the five held-out documents..."
run_validator "$OUTPUT_DIR/additive-operation.log" \
  "$REPO_ROOT/tools/release/run_additive_validation.py" --output-dir "$OUTPUT_DIR"

python3 - \
  "$OUTPUT_DIR/additive-wrapper.json" \
  "$CANDIDATE" \
  "$IMAGE" \
  "$IMAGE_ID" \
  "$CONTAINER" \
  "$VOLUME" \
  "$RETAIN" \
  "$BOLT_PORT" \
  "$DATABASE" <<'PY'
import hashlib
import json
import pathlib
import sys

(
    output_path,
    candidate_path,
    image,
    image_id,
    container,
    volume,
    retain,
    bolt_port,
    database,
) = sys.argv[1:]
candidate = pathlib.Path(candidate_path)
payload = {
    "status": "passed",
    "candidate": {
        "path": str(candidate.resolve()),
        "byte_size": candidate.stat().st_size,
        "sha256": hashlib.sha256(candidate.read_bytes()).hexdigest(),
    },
    "docker": {
        "image": image,
        "image_id": image_id,
        "container": container,
        "volume": volume,
        "retained": retain == "true",
    },
    "connection": {
        "uri": f"bolt://localhost:{bolt_port}",
        "username": "neo4j",
        "database": database,
        "credential_note": "Use the password printed only to the local terminal.",
    },
}
pathlib.Path(output_path).write_text(
    json.dumps(payload, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY

echo "Additive validation passed: $OUTPUT_DIR/additive-validation.json"
if [[ "$RETAIN" == true ]]; then
  echo "Connection: bolt://localhost:$BOLT_PORT (neo4j / $PASSWORD, database $DATABASE)"
fi
