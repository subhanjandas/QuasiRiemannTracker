#!/usr/bin/env bash
# Run a verification command, keep its full output with the job report, and turn
# the tail of a failure into a workflow annotation so it is visible without logs.
# Usage: run_logged.sh <log file> <command> [args...]
set -o pipefail
log="$1"
shift
mkdir -p "$(dirname "$log")"
"$@" 2>&1 | tee "$log"
status=${PIPESTATUS[0]}
if [ "$status" -ne 0 ]; then
  python3 - "$log" <<'PY'
import sys
lines = open(sys.argv[1], errors='replace').read().splitlines()[-45:]
message = '%0A'.join(l.replace('%', '%25').replace('\r', '') for l in lines)[-6000:]
print(f'::error title=Verification step failed::{message}')
PY
fi
exit "$status"
