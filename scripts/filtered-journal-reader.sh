#!/bin/bash

if [[ $(</proc/sys/kernel/hostname) != "etrial" ]]; then
  echo "You should run this from inside the container."
  exit
fi

stdbuf -oL -eL "$(dirname "$0")/filtered-journal.sh" -f | while read -r line; do
echo "$line" | jq -c '"", [.timestamp, .ip], {(.source): (.extra // [.http_status, .msg_clean])}'
done
