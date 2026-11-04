#!/usr/bin/env bash
# Retry the worker launch until ap-batam-1 has A1 capacity.
# Guard: each attempt applies a fresh saved plan only if its sole change is creating oci_core_instance.worker.
# Usage (from infra/terraform): scripts/retry-worker.sh [interval_seconds=600] [max_attempts=30]
set -u
interval=${1:-600}; max=${2:-30}
for ((i = 1; i <= max; i++)); do
  ts=$(date '+%F %T')
  terraform plan -input=false -no-color -out=worker.tfplan >/dev/null 2>plan.err || { echo "$ts attempt $i: plan failed: $(tail -1 plan.err)"; sleep "$interval"; continue; }
  ok=$(terraform show -json worker.tfplan | node -e '
    let s="";process.stdin.on("data",d=>s+=d).on("end",()=>{
      const c=(JSON.parse(s).resource_changes||[]).filter(r=>!r.change.actions.includes("no-op"));
      const only=c.length===1&&c[0].address==="oci_core_instance.worker"&&c[0].change.actions.join()==="create";
      console.log(c.length===0?"done":only?"ok":"unsafe:"+c.map(r=>r.address+"="+r.change.actions).join(","));
    })')
  case $ok in
    done) echo "$ts nothing to do: worker exists"; exit 0 ;;
    ok) ;;
    *) echo "$ts attempt $i: refusing, plan has other changes: $ok"; exit 2 ;;
  esac
  if terraform apply -input=false -no-color worker.tfplan >apply.log 2>&1; then
    echo "$ts attempt $i: WORKER CREATED"; rm -f worker.tfplan; exit 0
  fi
  echo "$ts attempt $i: $(grep -oE 'Out of host capacity|Error: [^\n]*' apply.log | head -1)"
  grep -q 'Out of host capacity' apply.log || exit 3
  sleep "$interval"
done
echo "gave up after $max attempts"; exit 1
