#!/usr/bin/env bash
# M1 Stage 2 — Analyze the real Road Rage default.xbe with the xboxrecomp toolkit.
#
# Runs the supported read-only analysis pipeline in order and captures every
# command's output to logs/. Nothing here mutates the game file. Translation
# (Stage 3) is a separate, heavier step.
#
# Usage:  bash scripts/m1_analyze.sh ["<path to default.xbe>"]
#
# Requires: the xboxrecomp clone at third_party/xboxrecomp, Python 3 (`py -3`).

set -u

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TOOLKIT="$REPO_ROOT/third_party/xboxrecomp"
XBE="${1:-$REPO_ROOT/game/The Simpsons Road Rage/default.xbe}"
LOGDIR="$REPO_ROOT/logs"
PY="py -3"

mkdir -p "$LOGDIR"

if [ ! -f "$XBE" ]; then
  echo "ERROR: XBE not found: $XBE" >&2
  echo "       Place your legally obtained default.xbe there, or pass a path." >&2
  exit 2
fi

XBE="$(cd "$(dirname "$XBE")" && pwd)/$(basename "$XBE")"
STEM="$(basename "$XBE" .xbe)"

echo "== XBE : $XBE"
echo "== STEM: $STEM"
echo "== LOGS: $LOGDIR"
echo

run() {
  # run <logname> <command...>
  local name="$1"; shift
  echo "---- $name"
  echo "\$ $*" | tee "$LOGDIR/$name.cmd"
  ( cd "$TOOLKIT" && "$@" ) > "$LOGDIR/$name.log" 2>&1
  local rc=$?
  echo "   exit=$rc  -> logs/$name.log ($(wc -l < "$LOGDIR/$name.log") lines)"
  return $rc
}

# 0. Confirm the XBE magic/format up front.
echo "---- magic"
python - "$XBE" <<'EOF' | tee "$LOGDIR/magic.log"
import sys
with open(sys.argv[1], "rb") as f:
    head = f.read(4)
print("first4:", head, head.hex())
print("is_XBE:", head == b"XBEH")
EOF

# 1. Parse: sections, entry point, imports, characteristics.
# The JSON must sit beside the XBE as <stem>_analysis.json so every
# downstream tool auto-detects it (see tools/disasm/loader.py:_find_analysis_json).
ANALYSIS_JSON="$(dirname "$XBE")/${STEM}_analysis.json"
run xbe_parser $PY -m tools.xbe_parser "$XBE" --json "$ANALYSIS_JSON"
cp -f "$ANALYSIS_JSON" "$LOGDIR/${STEM}_analysis.json" 2>/dev/null || true

# 2. Disassemble + function identification (text section first — fast path).
run disasm $PY -m tools.disasm "$XBE" --text-only

# 3. Classify library/game functions (confirms/refutes RenderWare, CRT, vtable).
run func_id $PY -m tools.func_id "$XBE" -v

# 4. Heuristic ABI recovery.
run abi_analysis $PY -m tools.abi_analysis "$XBE" -v

# 5. Bring-up health report (expects to find the toolkit's default dirs).
run doctor $PY tools/doctor.py

echo
echo "== analysis complete. Inspect logs/*.log and logs/${STEM}_analysis.json."
echo "== If disasm found code outside .text (XDK libs), re-run with:"
echo "   py -3 -m tools.disasm \"$XBE\" --extra-sections XIPS,DOLBY"
