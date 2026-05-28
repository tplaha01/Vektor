#!/usr/bin/env bash
set -euo pipefail

FEATURE_FILE="${1:-feature_list.json}"

if [[ ! -f "$FEATURE_FILE" ]]; then
  echo "feature file not found: $FEATURE_FILE" >&2
  exit 1
fi

node -e '
const fs=require("fs");
const p=process.argv[1];
let json;
try{json=JSON.parse(fs.readFileSync(p,"utf8"));}catch{console.error(`failed to parse ${p}`);process.exit(2);}
const pending=(json||[]).filter(x=>x&&x.passes===false);
if(pending.length===0){console.log("ALL_FEATURES_COMPLETE");process.exit(0);}
const next=pending[0];
console.log(`category=${next.category||""}`);
console.log(`description=${next.description||""}`);
console.log(`step_count=${Array.isArray(next.steps)?next.steps.length:0}`);
console.log(`passes=${next.passes}`);
' "$FEATURE_FILE"
