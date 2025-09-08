#!/usr/bin/env bash
set -euo pipefail

set -a
source .env
set +a

#MODEL_NAME=google-gla:gemini-2.5-flash
MODEL_NAME=openai:gpt-5-mini
INPUT_FILE="./resources/swe_verified_ids_shuffled.txt"

# Config
MAX=5                 # max entries to start
MAX_THREADS=3         # max concurrent tasks
TIMEOUT_SECS=7200     # per-task timeout (2h)

[[ -f "$INPUT_FILE" ]] || { echo "Input file not found: $INPUT_FILE"; exit 1; }

if [[ "${1:-}" == "--build" ]]; then
  docker rm -f useagent-turbo-test 2>/dev/null || true
  if [[ "${2:-}" == "--rm-image" ]]; then
    #This will delete the image, but you will loose caching.
    docker image rm -f useagent-turbo:dev 2>/dev/null || true
  fi
  DOCKER_BUILDKIT=1 docker build --build-arg COMMIT_SHA="$(git rev-parse HEAD)" --ssh default -t useagent-turbo:dev .
fi

STAMP="$(date +'%F-%H-%M')"
OUTDIR="./${STAMP}-useagent-swe-bench-results"
LOGDIR="${OUTDIR}/logs"
mkdir -p "$OUTDIR" "$LOGDIR"

# FIFO for completion notifications
STATUS_FIFO="$(mktemp -u)"
mkfifo "$STATUS_FIFO"

active=0
started=0
completed=0

print_completion() {
  local tid="$1" rc="$2" note="exit $rc"
  [[ "$rc" -eq 0 ]] && note="ok"
  [[ "$rc" -eq 124 ]] && note="timeout"
  ((completed++))
  echo "[$completed] ${tid} finished (${note})"
}

# Drain one completion (blocks until a task finishes)
drain_one() {
  local tid rc
  if read -r tid rc < "$STATUS_FIFO"; then
    ((active--))
    print_completion "$tid" "$rc"
  fi
}

while IFS= read -r raw || [[ -n "${raw:-}" ]]; do
  TASK_ID="$(echo "$raw" | tr -d '[:space:]')"
  [[ -z "$TASK_ID" || "${TASK_ID:0:1}" = "#" ]] && continue
  (( MAX > 0 && started >= MAX )) && break

  # throttle concurrency
  while (( active >= MAX_THREADS )); do drain_one; done

  LOG_FILE="${LOGDIR}/${TASK_ID}.log"
  (
    set -o pipefail
    CONTAINER_NAME="useagent-turbo-test-${TASK_ID}"
    timeout -k 30 "${TIMEOUT_SECS}s" docker run --rm \
      --name "${CONTAINER_NAME}" \
      -e GEMINI_API_KEY="${GEMINI_API_KEY:-}" \
      -e OPENAI_API_KEY="${OPENAI_API_KEY:-}" \
      -e TASK_ID="${TASK_ID}" \
      -e MODEL_NAME="${MODEL_NAME}" \
      -v "${OUTDIR}:/output" \
      useagent-turbo:dev \
      useagent swebench --model "${MODEL_NAME}" --instance-id "${TASK_ID}" --output-dir /output
    rc=$?
    printf "%s %s\n" "$TASK_ID" "$rc" > "$STATUS_FIFO"
    exit 0
  ) >"$LOG_FILE" 2>&1 &

  ((active++))
  ((started++))
done < "$INPUT_FILE"

# wait for remaining tasks
while (( active > 0 )); do drain_one; done

rm -f "$STATUS_FIFO"
echo "Done. Started $started, completed $completed. Outputs: $OUTDIR  Logs: $LOGDIR"
