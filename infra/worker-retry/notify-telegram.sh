#!/usr/bin/env bash
# Usage: notify-telegram.sh "message". Reads TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID from /etc/oci-homelab/telegram.env.
# The token goes to curl via stdin config (-K -) so it never shows up in the process list.
set -eu
. /etc/oci-homelab/telegram.env
printf 'url = "https://api.telegram.org/bot%s/sendMessage"\n' "$TELEGRAM_BOT_TOKEN" |
  curl -sS -m 20 -o /dev/null -w '%{http_code}\n' -K - --data-urlencode "chat_id=$TELEGRAM_CHAT_ID" --data-urlencode "text=$1"
