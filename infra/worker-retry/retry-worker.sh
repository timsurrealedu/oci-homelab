#!/usr/bin/env bash
# Runs on the edge from worker-retry.timer (every 5 min). Launches the worker with the edge's
# instance principal; pings Telegram on success, on a non-capacity error, daily, and on give-up.
# After success, adopt it on the Terraform machine: terraform import oci_core_instance.worker <ocid>
set -u
D=/opt/oci-homelab/worker-retry
. "$D/worker.env"
export SUPPRESS_LABEL_WARNING=True PYTHONWARNINGS=ignore
oci() { /opt/oci-homelab/venv/bin/oci --auth instance_principal "$@" 2>&1; }
notify() { "$D/notify-telegram.sh" "$1"; }
finish() { notify "$1"; systemctl disable --now worker-retry.timer; exit 0; }

n=$(( $(cat "$D/attempts" 2>/dev/null || echo 0) + 1 )); echo "$n" > "$D/attempts"

existing=$(oci compute instance list -c "$COMPARTMENT" --display-name worker \
  --query 'data[?"lifecycle-state"!=`TERMINATED`].id | [0]' --raw-output)
case $existing in
  ocid1.instance.*) finish "✅ oci-homelab: worker already exists ($existing). Retry timer stopped." ;;
  ""|null) ;;
  *) finish "⚠️ oci-homelab worker retry: can't list instances (auth/policy?): ${existing:0:300}. Timer stopped." ;;
esac

out=$(oci compute instance launch -c "$COMPARTMENT" --availability-domain "$AD" \
  --display-name worker --shape VM.Standard.A1.Flex --shape-config '{"ocpus":1,"memoryInGBs":6}' \
  --subnet-id "$SUBNET" --assign-public-ip false --private-ip 10.0.1.10 --hostname-label worker \
  --nsg-ids "[\"$NSG\"]" --image-id "$IMAGE" --boot-volume-size-in-gbs 50 \
  --ssh-authorized-keys-file "$D/authorized_keys" --user-data-file "$D/cloud-init.yaml" \
  --instance-options '{"areLegacyImdsEndpointsDisabled":true}' \
  --freeform-tags '{"project":"oci-homelab","managed-by":"terraform"}' \
  --query 'data.id' --raw-output)
rc=$?

if [ $rc -eq 0 ] && [[ $out == ocid1.instance.* ]]; then
  finish "🎉 oci-homelab: worker LAUNCHED after $n attempts: $out. Tell Claude to import it into Terraform. Timer stopped."
elif grep -q '"LimitExceeded"' <<<"$out"; then
  # ap-batam-1 sometimes answers LimitExceeded while the A1 quota has room (seen at attempt 47 with
  # 1/2 OCPU used). Treat it as transient; stop only if it persists for an hour.
  k=$(( $(cat "$D/limit_streak" 2>/dev/null || echo 0) + 1 )); echo "$k" > "$D/limit_streak"
  echo "attempt $n: LimitExceeded ($k in a row)"
  [ "$k" -ge 12 ] && finish "⚠️ oci-homelab: LimitExceeded $k times in a row (attempt $n). Check A1 usage under Limits, Quotas and Usage. Timer stopped."
elif grep -qiE 'out of host capacity|TooManyRequests|InternalError' <<<"$out"; then
  rm -f "$D/limit_streak"
  echo "attempt $n: capacity/transient: $(tr -s '\n ' ' ' <<<"$out" | grep -oE '"(code|message)": "[^"]*"' | tr '\n' ' ' | cut -c1-200)"
  [ $((n % 288)) -eq 0 ] && notify "⏳ oci-homelab: still no A1 capacity in Batam ($n attempts so far)."
  [ "$n" -ge "$MAX_ATTEMPTS" ] && finish "🛑 oci-homelab: gave up on the worker after $n attempts (7 days). Timer stopped."
else
  finish "⚠️ oci-homelab worker retry stopped on an unexpected error (attempt $n): ${out:0:500}"
fi
exit 0
