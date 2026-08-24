#!/usr/bin/env bash
# PHASE 0 (§17) resource sampler — measurement only.
# Usage: benchmarks/resource_sample.sh <RUN_ID> <TASK_ID> <label: start|end>
# Appends one JSON line to benchmarks/runs/resource_samples.jsonl capturing
# wall-clock timestamp, per-process RSS and CPU% for the Tauri app and the
# FastAPI backend. Never touches agent behavior.
set -euo pipefail

RUN_ID="${1:?usage: resource_sample.sh <RUN_ID> <TASK_ID> <start|end>}"
TASK_ID="${2:?}"
LABEL="${3:?}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="$SCRIPT_DIR/runs/resource_samples.jsonl"
mkdir -p "$SCRIPT_DIR/runs"

ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)

sample() { # $1=friendly name  $2=egrep pattern for command line
  local pid vals rss_mb cpu mem
  pid=$(ps axo pid=,command= | grep -E "$2" | grep -v grep | grep -v resource_sample | head -1 | awk '{print $1}')
  if [ -z "$pid" ]; then
    printf '{"name":"%s","pid":null,"rss_mb":null,"cpu_pct":null,"mem_pct":null}' "$1"
    return
  fi
  # One flat awk pass: KB->MB plus cpu/mem percentages, space-separated.
  vals=$(ps -p "$pid" -o rss=,pcpu=,pmem= | awk '{printf "%.1f %.2f %.2f", $1/1024, $2, $3}')
  read -r rss_mb cpu mem <<<"$vals"
  printf '{"name":"%s","pid":%s,"rss_mb":%s,"cpu_pct":%s,"mem_pct":%s}' "$1" "$pid" "$rss_mb" "$cpu" "$mem"
}

app_line=$(sample "tauri_app" 'matrioshai.*-app|Matrioshai\.app|target/debug/matrioshai')
backend_line=$(sample "fastapi_backend" 'uvicorn.*app\.main|python.*uvicorn')

printf '{"run_id":"%s","task_id":"%s","label":"%s","ts":"%s","app":%s,"backend":%s}\n' \
  "$RUN_ID" "$TASK_ID" "$LABEL" "$ts" "$app_line" "$backend_line" >> "$OUT"
tail -1 "$OUT"
