#!/usr/bin/env bash
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
#
# Used for: a maintainer's rare local gate before publishing a prebuilt dump.
#
# Restores a prebuilt candidate into an isolated local Neo4j and runs every
# offline artifact gate. This never calls Bedrock or connects to Aura.
#
# Usage: workfolder/maintenance/release/validate_prebuilt_candidate.sh [candidate.dump]
#
# Set NEO4J_IMAGE to the exact image used by build_prebuilt_graph.sh when the
# candidate was built with an override. The default matches that script. The
# database-load command is also an explicit dump/runtime compatibility gate.

set -euo pipefail

usage() {
  echo "Usage: workfolder/maintenance/release/validate_prebuilt_candidate.sh [candidate.dump]"
  echo "Environment: NEO4J_IMAGE (default: neo4j:latest)"
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi
if [[ "$#" -gt 1 ]]; then
  usage >&2
  exit 2
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
CANDIDATE="${1:-$REPO_ROOT/evidence/build/neo4j-hotel-graph-prebuilt.dump}"
IMAGE="${NEO4J_IMAGE:-neo4j:latest}"
RUN_ID="candidate-validate-$$"
VOLUME="neo4j-$RUN_ID"
LOADER="neo4j-$RUN_ID-loader"
CONTAINER="neo4j-$RUN_ID-server"
PASSWORD="$RUN_ID-password"

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

SCRATCH="$(mktemp -d)"
cleanup() {
  docker rm -f "$CONTAINER" "$LOADER" >/dev/null 2>&1 || true
  docker volume rm "$VOLUME" >/dev/null 2>&1 || true
  rm -rf "$SCRATCH"
}
trap cleanup EXIT

mkdir -p "$SCRATCH/dumps"
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
    --from-path=/dumps neo4j --overwrite-destination=true

docker run -d --name "$CONTAINER" \
  -v "$VOLUME:/data" \
  -p 127.0.0.1::7687 \
  -e NEO4J_AUTH="neo4j/$PASSWORD" \
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

NEO4J_VERSION="$(
  docker exec "$CONTAINER" cypher-shell --format plain \
    -u neo4j -p "$PASSWORD" \
    "CALL dbms.components() YIELD versions RETURN versions[0] AS version" |
    tail -n 1 | tr -d '\r'
)"
echo "Candidate restored into disposable Neo4j $NEO4J_VERSION."

run_validator() {
  local validator="$1"
  shift
  NEO4J_URI="bolt://localhost:$BOLT_PORT" \
  NEO4J_USERNAME=neo4j \
  NEO4J_PASSWORD="$PASSWORD" \
  NEO4J_DATABASE=neo4j \
  uv run --project "$REPO_ROOT/notebooks/workshop" --locked \
    python "$validator" "$@"
}

run_validator "$REPO_ROOT/workfolder/maintenance/release/validate_graph_amenities.py" --mode prebuilt
run_validator "$REPO_ROOT/workfolder/maintenance/release/validate_prebuilt_candidate.py"

cleanup
trap - EXIT
echo "Candidate restore and validation passed; disposable resources removed."
