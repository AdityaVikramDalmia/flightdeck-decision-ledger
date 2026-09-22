#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STORE="$(mktemp -d "${TMPDIR:-/tmp}/decision-ledger-example.XXXXXXXX")"
trap 'rm -rf "$STORE"' EXIT
TOOL="$ROOT/bin/decision-ledger"
export DECISION_LEDGER_DIR="$STORE/state"
"$TOOL" init
"$TOOL" record --words-stdin --source paste --interpretation 'Keep version 2 until review' <<'WORDS'
Keep version 2. Don't silently substitute version 3.
Keep this second line too.
WORDS
question=$("$TOOL" ask 'May the release proceed?' --actor builder |
  python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
"$TOOL" open
"$TOOL" answer "$question" 'Wait until review is complete.' --actor reviewer
"$TOOL" answer "$question" 'Review is complete; proceed with version 2.' --actor reviewer
"$TOOL" history "$question"
"$TOOL" open
"$TOOL" validate
