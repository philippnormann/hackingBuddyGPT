#!/usr/bin/env bash
#
# collect_all.sh - Run collect_traces.sh for all 13 scenarios
#

set -euo pipefail

# Default configuration
HOST="" # Host must be provided via -h
RUNS=100
MODEL="mistral-large-123b"
EXPLOIT_PROB=100
API_URL=http://localhost:11434 # Default Ollama port (can be overridden by -U)
API_KEY=""  # Default API Key (can be overridden by -a)

usage() {
    echo "Usage: $0 -h <HOST> [options]"
    echo "Options:"
    echo "  -h <HOST>       Target host (Mandatory)"
    echo "  -a <API_KEY>    API Key (Default: none)"
    echo "  -U <API_URL>    API URL (Default: ${API_URL})"
    echo "  -r <RUNS>       Runs per scenario (Default: ${RUNS})"
    echo "  -m <MODEL>      Model name (Default: ${MODEL})"
    echo "  -e <EXPLOIT_PROB> Exploit probability (Default: ${EXPLOIT_PROB})"
    exit 1
}

while getopts ":a:U:h:r:m:e:" opt; do
  case ${opt} in
    a )
      API_KEY=$OPTARG
      ;;
    U )
      API_URL=$OPTARG
      ;;
    h )
      HOST=$OPTARG
      ;;
    r )
      RUNS=$OPTARG
      ;;
    m )
      MODEL=$OPTARG
      ;;
    e )
      EXPLOIT_PROB=$OPTARG
      ;;
    \? )
      echo "Invalid option: $OPTARG" 1>&2
      usage
      ;;
    : )
      echo "Invalid option: $OPTARG requires an argument" 1>&2
      usage
      ;;
  esac
done
shift $((OPTIND -1))

if [ -z "${HOST}" ]; then
    echo "Error: Target host (-h) is mandatory."
    usage
fi

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
COLLECT_SCRIPT="$SCRIPT_DIR/collect_traces.sh"

# All scenarios
SCENARIOS=(
    "01_vuln_suid_gtfo"
    "02_vuln_password_in_shell_history"
    "03_vuln_sudo_no_password"
    # "04_vuln_sudo_gtfo_interactive"
    "05_vuln_sudo_gtfo"
    "06_vuln_docker"
    "07_root_password_reuse_mysql"
    "08_root_password_reuse"
    "09_root_password_root"
    "10_root_allows_lowpriv_to_ssh"
    "11_cron_calling_user_wildcard"
    "12_cron_calling_user_file"
    "13_file_with_root_password"
)

echo "🚀 Starting batch collection for ${#SCENARIOS[@]} scenarios..."
echo "   Host: $HOST"
echo "   Runs per scenario: $RUNS"
echo "   Model: $MODEL"
echo "   Total estimated runs: $((${#SCENARIOS[@]} * RUNS))"
echo

for scenario in "${SCENARIOS[@]}"; do
    echo "═══════════════════════════════════════════════════════════"
    echo "🎯 Starting scenario: $scenario"
    echo "═══════════════════════════════════════════════════════════"
    
    start_time=$(date +%s)
    
    "$COLLECT_SCRIPT" "$scenario" "$HOST" "$RUNS" \
        -m "$MODEL" \
        -U "$API_URL" \
        -a "$API_KEY" \
        -e "$EXPLOIT_PROB"
    
    end_time=$(date +%s)
    duration=$((end_time - start_time))
    
    echo "✅ Completed $scenario in ${duration}s"
    echo
done

echo "🏁 All scenarios completed!"