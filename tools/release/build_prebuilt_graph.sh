#!/usr/bin/env bash
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
#
# Used for: a rare maintainer rebuild of the prebuilt Neo4j release artifact.
#
# Builds a fresh 295-document workshop graph in disposable local Neo4j, then
# writes a candidate dump for review. The five Module 1 documents are omitted
# by prepare_graph.py --mode prebuilt and remain available for live extraction.
#
# Requires Docker, uv, AWS credentials, and Bedrock model access. This script
# never connects to Aura and never replaces graph/neo4j-hotel-graph.dump.
#
# Usage: tools/release/build_prebuilt_graph.sh [--resume]
# Output: evidence/build/neo4j-hotel-graph-prebuilt.dump

set -euo pipefail

# Bash can read a script incrementally. Execute an immutable private copy so an
# edit to this file during the long Bedrock build cannot change later commands.
if [[ -z "${PREBUILT_SCRIPT_SNAPSHOT:-}" ]]; then
  PREBUILT_SCRIPT_SNAPSHOT_DIR="$(mktemp -d)"
  PREBUILT_SCRIPT_SNAPSHOT="$PREBUILT_SCRIPT_SNAPSHOT_DIR/build_prebuilt_graph.sh"
  cp "${BASH_SOURCE[0]}" "$PREBUILT_SCRIPT_SNAPSHOT"
  chmod 700 "$PREBUILT_SCRIPT_SNAPSHOT"
  export PREBUILT_SCRIPT_SNAPSHOT PREBUILT_SCRIPT_SNAPSHOT_DIR
  export PREBUILT_REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
  exec bash "$PREBUILT_SCRIPT_SNAPSHOT" "$@"
fi
trap 'rm -rf "$PREBUILT_SCRIPT_SNAPSHOT_DIR"' EXIT

RESUMABLE=false
case "${1:-}" in
  "") ;;
  --resume) RESUMABLE=true ;;
  -h|--help)
    echo "Usage: tools/release/build_prebuilt_graph.sh [--resume]"
    echo
    echo "Without arguments, build from scratch in a disposable Docker volume."
    echo "With --resume, retain a failed build and reuse only provenance-checked"
    echo "documents on the next --resume invocation."
    exit 0
    ;;
  *)
    echo "Unknown argument: $1" >&2
    echo "Usage: tools/release/build_prebuilt_graph.sh [--resume]" >&2
    exit 2
    ;;
esac
if [[ $# -gt 1 ]]; then
  echo "Expected at most one argument." >&2
  echo "Usage: tools/release/build_prebuilt_graph.sh [--resume]" >&2
  exit 2
fi

REPO_ROOT="${PREBUILT_REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
IMAGE="${NEO4J_IMAGE:-neo4j:latest}"
MEMORY_LIMIT="${NEO4J_MEMORY_LIMIT:-4g}"
BUILD_CONCURRENCY="${GRAPH_BUILD_CONCURRENCY:-3}"
SHUTDOWN_TIMEOUT="${NEO4J_SHUTDOWN_TIMEOUT:-60}"
if [[ "$RESUMABLE" == true ]]; then
  VOLUME="${NEO4J_PREBUILT_VOLUME:-neo4j-prebuilt-checkpoint}"
  PASSWORD="${NEO4J_PREBUILT_PASSWORD:-prebuilt-local-checkpoint}"
else
  VOLUME="neo4j-prebuilt-$$"
  PASSWORD="prebuilt-local-$$"
fi
CHECKPOINT_LABEL="com.aws.graphrag-workshop.prebuilt-checkpoint"
CONTAINER="neo4j-prebuilt-$$"
EVIDENCE_DIR="$REPO_ROOT/evidence/build"
OUTPUT="$EVIDENCE_DIR/neo4j-hotel-graph-prebuilt.dump"
MANIFEST="$EVIDENCE_DIR/neo4j-hotel-graph-prebuilt.manifest.json"
PENDING_MANIFEST="$EVIDENCE_DIR/.neo4j-hotel-graph-prebuilt.manifest.pending.json"
BUILD_SUCCEEDED=false

mkdir -p "$EVIDENCE_DIR"

verify_candidate_manifest() {
  python3 - "$1" "$2" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

manifest_path = Path(sys.argv[1])
candidate = Path(sys.argv[2])
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
recorded = manifest.get("candidate", {})
checksum = hashlib.sha256()
with candidate.open("rb") as source:
    for block in iter(lambda: source.read(1024 * 1024), b""):
        checksum.update(block)
digest = checksum.hexdigest()
if manifest.get("final_success") is not True:
    raise SystemExit("pending manifest is not complete")
if recorded.get("path") != candidate.name:
    raise SystemExit("candidate filename does not match pending manifest")
if recorded.get("byte_size") != candidate.stat().st_size:
    raise SystemExit("candidate size does not match pending manifest")
if recorded.get("sha256") != digest:
    raise SystemExit("candidate checksum does not match pending manifest")
PY
}

if [[ -e "$OUTPUT" && ! -e "$MANIFEST" && -e "$PENDING_MANIFEST" ]]; then
  verify_candidate_manifest "$PENDING_MANIFEST" "$OUTPUT"
  mv "$PENDING_MANIFEST" "$MANIFEST"
  echo "Recovered completed candidate publication: $OUTPUT"
  echo "Manifest: $MANIFEST"
  rm -rf "$PREBUILT_SCRIPT_SNAPSHOT_DIR"
  exit 0
fi
if [[ ! -e "$OUTPUT" && -e "$PENDING_MANIFEST" ]]; then
  echo "Discarding an incomplete candidate-publication manifest." >&2
  rm -f "$PENDING_MANIFEST"
fi

if [[ -e "$OUTPUT" ]]; then
  echo "Refusing to overwrite existing candidate: $OUTPUT" >&2
  echo "Move or delete it after review, then run this script again." >&2
  exit 1
fi
if [[ -e "$MANIFEST" ]]; then
  echo "Refusing to overwrite existing candidate manifest: $MANIFEST" >&2
  echo "Move or delete it after review, then run this script again." >&2
  exit 1
fi

SCRATCH="$(mktemp -d)"
START_SNAPSHOT="$SCRATCH/prebuilt-build-start.json"
MANIFEST_WRITER="$SCRATCH/write_prebuilt_manifest.py"
cp "$REPO_ROOT/tools/release/write_prebuilt_manifest.py" "$MANIFEST_WRITER"
BUILD_STARTED_AT="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
BUILD_STARTED_EPOCH="$(date +%s)"

cleanup() {
  if docker container inspect "$CONTAINER" >/dev/null 2>&1; then
    CONTAINER_RUNNING="$(
      docker container inspect --format '{{.State.Running}}' "$CONTAINER" \
        2>/dev/null || true
    )"
    if [[ "$CONTAINER_RUNNING" == "true" ]]; then
      echo "Stopping Neo4j cleanly (timeout: ${SHUTDOWN_TIMEOUT}s)..." >&2
      if ! docker stop --time "$SHUTDOWN_TIMEOUT" "$CONTAINER" >/dev/null; then
        echo "Graceful Neo4j stop failed; forcing container removal." >&2
      fi
    fi
    docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
  fi
  if [[ "$BUILD_SUCCEEDED" == true ]]; then
    docker volume rm "$VOLUME" >/dev/null 2>&1 || true
  else
    if docker volume inspect "$VOLUME" >/dev/null 2>&1; then
      echo "Retained Neo4j checkpoint volume: $VOLUME" >&2
      echo "Resume with:" >&2
      echo "  NEO4J_PREBUILT_VOLUME='$VOLUME' NEO4J_PREBUILT_PASSWORD='$PASSWORD' tools/release/build_prebuilt_graph.sh --resume" >&2
    fi
  fi
  rm -rf "$SCRATCH"
  rm -rf "$PREBUILT_SCRIPT_SNAPSHOT_DIR"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

mkdir -p "$SCRATCH/dumps-out"
START_ARGS=(
  start
  --repo-root "$REPO_ROOT"
  --output "$START_SNAPSHOT"
  --started-at "$BUILD_STARTED_AT"
  --started-epoch "$BUILD_STARTED_EPOCH"
)
if [[ "$RESUMABLE" == true ]]; then
  START_ARGS+=(--resume)
fi
python3 "$MANIFEST_WRITER" "${START_ARGS[@]}"

if [[ "$RESUMABLE" == true ]] && docker volume inspect "$VOLUME" >/dev/null 2>&1; then
  VOLUME_KIND="$(
    docker volume inspect --format \
      '{{ index .Labels "com.aws.graphrag-workshop.prebuilt-checkpoint" }}' \
      "$VOLUME"
  )"
  if [[ "$VOLUME_KIND" != "v1" ]]; then
    echo "Refusing to reuse unlabeled volume: $VOLUME" >&2
    echo "Choose an unused NEO4J_PREBUILT_VOLUME for this build." >&2
    exit 1
  fi
  USING_CONTAINERS="$(docker ps -aq --filter "volume=$VOLUME")"
  if [[ -n "$USING_CONTAINERS" ]]; then
    echo "Checkpoint volume $VOLUME is already attached to a container." >&2
    echo "Remove that stale build container before starting another resume." >&2
    exit 1
  fi
  echo "Reusing Neo4j checkpoint volume: $VOLUME"
else
  if [[ "$RESUMABLE" == true ]]; then
    docker volume create --label "$CHECKPOINT_LABEL=v1" "$VOLUME" >/dev/null
  else
    docker volume create --label "$CHECKPOINT_LABEL=v1" "$VOLUME" >/dev/null
  fi
  if [[ "$RESUMABLE" == true ]]; then
    echo "Created resumable Neo4j checkpoint volume: $VOLUME"
  fi
fi

echo "Starting disposable Neo4j with $IMAGE..."
docker run -d --name "$CONTAINER" \
  -v "$VOLUME:/data" \
  -p 127.0.0.1::7687 \
  --memory "$MEMORY_LIMIT" \
  --memory-swap "$MEMORY_LIMIT" \
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
    tail -n 1 |
    tr -d '\r'
)"
if [[ "$APOC_PROCEDURE_COUNT" != "1" ]]; then
  echo "APOC prerequisite failed: apoc.merge.relationship is unavailable." >&2
  echo "Check the container startup logs and confirm that $IMAGE can install" >&2
  echo "the APOC plugin before retrying the release build." >&2
  exit 1
fi
echo "APOC prerequisite passed: apoc.merge.relationship is available."

echo "Building the 295-document prebuilt graph..."
echo "Bedrock extraction concurrency: $BUILD_CONCURRENCY"
PREPARE_ARGS=(--mode prebuilt --rebuild)
if [[ "$RESUMABLE" == true ]]; then
  PREPARE_ARGS=(--mode prebuilt --resume)
fi
(
  cd "$REPO_ROOT/notebooks/02-connected-context"
  NEO4J_URI="bolt://localhost:$BOLT_PORT" \
  NEO4J_USERNAME=neo4j \
  NEO4J_PASSWORD="$PASSWORD" \
  NEO4J_DATABASE=neo4j \
  GRAPH_BUILD_CONCURRENCY="$BUILD_CONCURRENCY" \
  uv run --project ../workshop python prepare_graph.py "${PREPARE_ARGS[@]}"
)

# Module 1 deliberately creates these indexes after participants add their five
# documents, so the release artifact must not contain them.
docker exec "$CONTAINER" cypher-shell -u neo4j -p "$PASSWORD" \
  "DROP INDEX hotel_chunk_embeddings IF EXISTS"
docker exec "$CONTAINER" cypher-shell -u neo4j -p "$PASSWORD" \
  "DROP INDEX hotel_chunk_fulltext IF EXISTS"

echo "Stopping Neo4j and creating the candidate dump..."
docker stop "$CONTAINER" >/dev/null
docker run --rm \
  -v "$VOLUME:/data" \
  -v "$SCRATCH/dumps-out:/dumps-out" \
  "$IMAGE" \
  neo4j-admin database dump --to-path=/dumps-out neo4j

STAGED_OUTPUT="$SCRATCH/neo4j-hotel-graph-prebuilt.dump"
cp "$SCRATCH/dumps-out/neo4j.dump" "$STAGED_OUTPUT"
BUILD_COMPLETED_AT="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
BUILD_COMPLETED_EPOCH="$(date +%s)"
IMAGE_ID="$(docker image inspect --format '{{.Id}}' "$IMAGE")"
IMAGE_REPO_DIGESTS_JSON="$(
  docker image inspect --format '{{json .RepoDigests}}' "$IMAGE"
)"
if [[ "$IMAGE_REPO_DIGESTS_JSON" == "null" ]]; then
  IMAGE_REPO_DIGESTS_JSON="[]"
fi
python3 "$MANIFEST_WRITER" finish \
  --snapshot "$START_SNAPSHOT" \
  --candidate "$STAGED_OUTPUT" \
  --manifest "$PENDING_MANIFEST" \
  --completed-at "$BUILD_COMPLETED_AT" \
  --completed-epoch "$BUILD_COMPLETED_EPOCH" \
  --image-tag "$IMAGE" \
  --image-id "$IMAGE_ID" \
  --image-repo-digests-json "$IMAGE_REPO_DIGESTS_JSON"
cp "$STAGED_OUTPUT" "$OUTPUT"
verify_candidate_manifest "$PENDING_MANIFEST" "$OUTPUT"
mv "$PENDING_MANIFEST" "$MANIFEST"
BUILD_SUCCEEDED=true
echo "Done: $OUTPUT"
echo "Manifest: $MANIFEST"
