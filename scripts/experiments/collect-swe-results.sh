#!/usr/bin/env bash
# merge_foo.sh — Merge all foo.json objects from given folders into a JSON array file.
# Usage: ./merge_foo.sh output.json dir1 [dir2 dir3 ...]

set -euo pipefail

if [ $# -lt 2 ]; then
  echo "Usage: $0 output.json dir1 [dir2 ...]" >&2
  exit 1
fi

out="$1"
shift

# Ensure output directory exists (if a path is given)
out_dir="$(dirname -- "$out")"
[ "$out_dir" != "." ] && mkdir -p -- "$out_dir"

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

# Build JSON array
first=1
printf '[' > "$tmp"

# Use process substitution to avoid a subshell (so $first persists)
while IFS= read -r -d '' f; do
  if [ "$first" -eq 1 ]; then
    first=0
  else
    printf ',\n' >> "$tmp"
  fi
  cat -- "$f" >> "$tmp"
done < <(find "$@" -type f -name 'swe_datapoint.json' -print0)

printf ']\n' >> "$tmp"

# Atomically move into place
mv -- "$tmp" "$out"
trap - EXIT

