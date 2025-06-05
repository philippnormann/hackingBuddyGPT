#!/usr/bin/env bash
#
# collect_traces.sh – batch-collect Wintermute traces for one Docker scenario
#   Compatible with https://github.com/ipa-lab/benchmark-privesc-linux
#
# ---------------------------------------------------------------------------
# Usage:
#   ./collect_traces.sh <scenario> <benchmark_host> <runs> [options]
#
# Positional arguments
#   scenario         Scenario folder, e.g. 05_vuln_sudo_gtfo
#   benchmark_host   IP / DNS of the machine running the benchmark containers
#   runs             Number of traces to collect
#
# Optional flags (all have sensible defaults)
#   -u USER        SSH user on benchmark host        (default: root)
#   -m MODEL       LLM model name                    (default: hf.co/unsloth/DeepSeek-R1-Distill-Qwen-32B-GGUF:Q4_K_M)
#   -t TEMPLATE    Wintermute template               (default: ReasoningLinuxPrivesc)
#   -p PROB        Hint probability 0-100            (default: 30)
#   -e PROB        Exploit probability 0-100         (default: 40)
#   -o OUTDIR      Directory to save logs            (default: <repo>/logs)
#   -U URL         LLM API base-URL                  (default: http://localhost:11434)
#   -a KEY         LLM API key                       (default: none)
#
# Each trace run:
#   0. ⏳  build.sh  – ensure images up-to-date   (once)
#   1. 🚀  start.sh  – fresh container for run
#   2. 🎯  inject hint/exploit with PROB % or run unguided
#   3. 📝  run Wintermute; log output to OUTDIR
# ---------------------------------------------------------------------------

set -euo pipefail

# resolve repo root
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WINTERMUTE_PY="$REPO_ROOT/src/hackingBuddyGPT/cli/wintermute.py"

# defaults
USER="root"
MODEL="hf.co/unsloth/DeepSeek-R1-Distill-Qwen-32B-GGUF:Q4_K_M"
TEMPLATE="ReasoningLinuxPrivesc"
HINT_PROB=30
EXPLOIT_PROB=40
OUTDIR="$REPO_ROOT/logs"
API_KEY=""
API_URL="http://localhost:11434"
TEMPERATURE=1.0 # Added default for temperature
LOCAL_MODE=false  # if true, run directly on benchmark host without SSH
 
usage() {
    echo "Usage: $0 <scenario> <benchmark_host> <runs> [options]"
    echo ""
    echo "Positional arguments:"
    echo "  scenario         Scenario folder, e.g. 05_vuln_sudo_gtfo"
    echo "  benchmark_host   IP / DNS of the machine running the benchmark containers"
    echo "  runs             Number of traces to collect"
    echo ""
    echo "Optional flags:"
    echo "  -u USER        SSH user on benchmark host        (default: ${USER})"
    echo "  -m MODEL       LLM model name                    (default: ${MODEL})"
    echo "  -t TEMPLATE    Wintermute template               (default: ${TEMPLATE})"
    echo "  -p PROB        Hint probability 0-100            (default: ${HINT_PROB})"
    echo "  -e PROB        Exploit probability 0-100         (default: ${EXPLOIT_PROB})"
    echo "  -o OUTDIR      Directory to save logs            (default: ${OUTDIR})"
    echo "  -U URL         LLM API base-URL                  (default: ${API_URL})"
    echo "  -a KEY         LLM API key                       (default: none)"
    exit 1
}

# Parse positional arguments first
SCEN="${1:-}"  HOST="${2:-}"  RUNS="${3:-}"
if [[ -z $SCEN || -z $HOST || -z $RUNS ]]; then
  usage
fi

# Shift past the positional arguments
shift 3

# Parse optional flags
while getopts ":u:m:t:p:e:o:a:U:T" opt; do
  case "$opt" in
    u) USER="$OPTARG" ;;
    m) MODEL="$OPTARG" ;;
    t) TEMPLATE="$OPTARG" ;;
    p) HINT_PROB="$OPTARG" ;;
    e) EXPLOIT_PROB="$OPTARG" ;;
    o) OUTDIR="$OPTARG" ;;
    a) API_KEY="$OPTARG" ;;
    U) API_URL="$OPTARG" ;;
    \?)
      echo "Invalid option: -$OPTARG" >&2
      usage
      ;;
    :)
      echo "Option -$OPTARG requires an argument." >&2
      usage
      ;;
  esac
done

# auto-enable local mode for local hosts
if [[ "$HOST" == "localhost" || "$HOST" == "127.0.0.1" ]]; then
  LOCAL_MODE=true
  USER=$(whoami)  # use current user for local runs
fi

echo "Collecting traces with the following settings:"
echo "  Scenario: $SCEN"
echo "  Benchmark host: $HOST"
echo "  Runs: $RUNS"
echo "  User: $USER"
echo "  Model: $MODEL"
echo "  Template: $TEMPLATE"
echo "  Hint probability: $HINT_PROB%"
echo "  Exploit probability: $EXPLOIT_PROB%"
echo "  Output directory: $OUTDIR"
echo "  API URL: $API_URL"
echo "  API Key: ${API_KEY:-<not set>}"

PORT=$((5000 + 10#${SCEN%%_*}))
HOME_DIR=$(eval echo "~$USER")  # resolve home directory for the user
REMOTE_DIR="$HOME/code/benchmark-privesc-linux/docker"

 
# helper to run commands locally or via SSH
run_remote() { if [ "$LOCAL_MODE" = true ]; then eval "$1"; else ssh ${USER}@${HOST} "$1"; fi }

mkdir -p "$OUTDIR"

echo "⏳  Building Docker images${LOCAL_MODE:+ locally} on $HOST …"
run_remote "cd $REMOTE_DIR && ./build.sh" >/dev/null
echo "   ✅  Images built."

HINT=$(run_remote "jq -r '.[\"$SCEN\"] // empty' $REMOTE_DIR/hints.json" || true)

# Download exploit file if available
if run_remote "[ -f $REMOTE_DIR/tests/$SCEN.sh ]"; then
  EXPLOIT_FILE="$OUTDIR/exploits/${SCEN}.sh"
  echo "⏳  Downloading exploit file..."
  if [ "$LOCAL_MODE" = true ]; then
    cp "$REMOTE_DIR/tests/$SCEN.sh" "$EXPLOIT_FILE" 2>/dev/null
    if [[ -s "$EXPLOIT_FILE" ]]; then
      echo "✅  Exploit file downloaded."
    else
      rm -f "$EXPLOIT_FILE"
      EXPLOIT_FILE=""
      echo "⚠️  Failed to copy exploit file locally."
    fi
  else
    scp "${USER}@${HOST}:$REMOTE_DIR/tests/$SCEN.sh" "$EXPLOIT_FILE" 2>/dev/null
    if [[ -s "$EXPLOIT_FILE" ]]; then
      echo "✅  Exploit file downloaded."
    else
      rm -f "$EXPLOIT_FILE"
      EXPLOIT_FILE=""
      echo "⚠️  Failed to download exploit file via scp."
    fi
  fi
else
  echo "ℹ️  No exploit file available for scenario $SCEN."
fi

for ((i=1;i<=RUNS;i++)); do
  echo "──────── Trace $i / $RUNS – $SCEN (port $PORT) ────────"

  run_remote "cd $REMOTE_DIR && ./start.sh $SCEN" >/dev/null
  echo "🚀  Container ready."

  pass_hint=""
  pass_exploit_file=""
  dice_roll=$(shuf -i0-99 -n1)

  # Determine run type based on dice roll
  # Order of checks: Exploit -> Hint -> Unguided
  if [[ -n "$EXPLOIT_FILE" && $dice_roll -lt $EXPLOIT_PROB ]]; then
    # Use Exploit
    pass_exploit_file="$EXPLOIT_FILE"
    echo "🎯  Exploit injected (using downloaded file: $pass_exploit_file)."
  elif [[ -n "$HINT" && $dice_roll -lt $(($EXPLOIT_PROB + $HINT_PROB)) ]]; then
    # Use Hint (only if not using exploit)
    pass_hint="$HINT"
    echo "🎯  Hint injected."
  else
    # Unguided
    echo "🎯  No hint or exploit for this run."
  fi

  # Generate timestamp for unique log filename
  TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
  
  echo "📝  Running Wintermute …"
  cmd=( uv run python "$WINTERMUTE_PY" "$TEMPLATE"
        --llm.model="$MODEL"
        --llm.api_url="$API_URL"
        --llm.api_key="$API_KEY"
        --conn.host="$HOST"
        --conn.username="lowpriv"
        --conn.password="trustno1"
        --conn.port="$PORT"
        --hint="$pass_hint"
        --known_exploit_file="$pass_exploit_file"
        )

  "${cmd[@]}" | tee "$OUTDIR/${SCEN}_${TIMESTAMP}.log"
  echo "   ✅  Trace $i saved to ${SCEN}_${TIMESTAMP}.log"
done

echo "🛑  Stopping container …"
run_remote "cd $REMOTE_DIR && ./stop.sh $SCEN" >/dev/null || true
echo "🏁  Done — logs in '$OUTDIR/'"