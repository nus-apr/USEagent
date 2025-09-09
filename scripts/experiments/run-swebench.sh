#!/usr/bin/env bash
set -euo pipefail

set -a
source .env
set +a

#MODEL_NAME=google-gla:gemini-2.5-flash
MODEL_NAME=openai:gpt-5-mini
INPUT_FILE="./resources/swe_verified_ids_shuffled.txt"

# Config
MAX=5                 # 0 = all
MAX_THREADS=3
TIMEOUT_SECS=7200     # 0 = no timeout

[[ -f "$INPUT_FILE" ]] || { echo "Input file not found: $INPUT_FILE"; exit 1; }

if [[ "${1:-}" == "--build" ]]; then
  docker rm -f useagent-turbo-test 2>/dev/null || true
  if [[ "${2:-}" == "--rm-image" ]]; then docker image rm -f useagent-turbo:dev 2>/dev/null || true; fi
  DOCKER_BUILDKIT=1 docker build --build-arg COMMIT_SHA="$(git rev-parse HEAD)" --ssh default -t useagent-turbo:dev .
fi

STAMP="$(date +'%F-%H-%M')"
OUTDIR="./${STAMP}-useagent-swe-bench-results"
mkdir -p "$OUTDIR"

# timeout tool (macOS: `brew install coreutils` for gtimeout)
TIMEOUT_BIN="$(command -v timeout || command -v gtimeout || true)"
PREFIX=()
if (( TIMEOUT_SECS > 0 )) && [[ -n "$TIMEOUT_BIN" ]]; then
  PREFIX=("$TIMEOUT_BIN" -k 30 "${TIMEOUT_SECS}s")
elif (( TIMEOUT_SECS > 0 )); then
  echo "WARN: timeout/gtimeout not found; running without hard timeout." >&2
fi

# Load IDs first (no stdin races), strip blanks/comments/CR
mapfile -t IDS < <(awk 'NF && $0 !~ /^#/' "$INPUT_FILE" | tr -d '\r')
if (( MAX > 0 )) && (( ${#IDS[@]} > MAX )); then IDS=( "${IDS[@]:0:MAX}" ); fi
(( ${#IDS[@]} > 0 )) || { echo "No runnable IDs."; exit 0; }

PIDS=()
TASKS=()
started=0
completed=0

start_one() {
  local id="$1"
  echo "$(date +'%F-%H-%M') starting ID ${id}"
  (
    set -o pipefail
    exec </dev/null >/dev/null 2>&1
    CONTAINER_NAME="useagent-turbo-test-${id}"
    "${PREFIX[@]}" docker run --rm \
      --name "${CONTAINER_NAME}" \
      -e GEMINI_API_KEY="${GEMINI_API_KEY:-}" \
      -e OPENAI_API_KEY="${OPENAI_API_KEY:-}" \
      -e TASK_ID="${id}" \
      -e MODEL_NAME="${MODEL_NAME}" \
      -v "${OUTDIR}:/output" \
      useagent-turbo:dev \
      useagent swebench --model "${MODEL_NAME}" --instance-id "${id}" --output-dir /output
  ) &
  local pid=$!
  PIDS+=("$pid")
  TASKS+=("$id")
  ((started+=1))   # avoid set -e trap of var++
}

reap_one() {
  local i pid id rc
  while :; do
    for i in "${!PIDS[@]}"; do
      pid="${PIDS[i]}"
      if ! kill -0 "$pid" 2>/dev/null; then
        # use wait inside if to avoid set -e aborts
        if wait "$pid"; then rc=0; else rc=$?; fi
        id="${TASKS[i]}"
        unset 'PIDS[i]' 'TASKS[i]'
        ((completed+=1))
        local note="exit $rc"; [[ $rc -eq 0 ]] && note="ok"; [[ $rc -eq 124 ]] && note="timeout"
        echo "[$completed] ${id} finished (${note})"
        return 0
      fi
    done
    sleep 0.2
  done
}

for id in "${IDS[@]}"; do
  while (( ${#PIDS[@]} >= MAX_THREADS )); do reap_one; done
  start_one "$id"
done

while (( ${#PIDS[@]} > 0 )); do reap_one; done

echo "Done. Started $started, completed $completed. Outputs: $OUTDIR"
