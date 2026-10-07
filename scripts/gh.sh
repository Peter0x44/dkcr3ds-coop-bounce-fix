#!/bin/bash
# usage: [RO=] scripts/gh.sh <3ds|wii> <Script.java> [args...]
# Runs a Ghidra script against the analysed project; prints the script's println output.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export JAVA_HOME="$ROOT/tools/jdk-21.0.12.1+1"
export PATH="$JAVA_HOME/bin:$PATH"
case $1 in 3ds) P=dkcr3ds; F=code_3ds.elf;; wii) P=dkcrwii2; F=main.dol;; esac
shift; S=$1; shift
RO=${RO--readOnly}
cd "$ROOT"
cmd //c "tools\ghidra_12.1.4_PUBLIC\support\analyzeHeadless.bat ghidra_proj $P -process $F -noanalysis $RO -scriptPath scripts\ghidra -postScript $S $*" > work/gh_$$.log 2>&1
python - "$S" "work/gh_$$.log" <<'PY'
import sys, re
s = sys.argv[1]
out = []
for line in open(sys.argv[2], errors="replace"):
    m = re.match(r"INFO  " + re.escape(s) + r"> (.*?)(?: \(GhidraScript\))?\s*$", line)
    if m: out.append(m.group(1)); continue
    if line.startswith(("INFO", "WARN")) or "(GhidraScript)" in line and not out: 
        if "ERROR" in line or "Exception" in line: out.append(line.rstrip())
        continue
    if out or "ERROR" in line or "Exception" in line: out.append(line.rstrip())
print("\n".join(out))
PY
