#!/usr/bin/env bash
# Backstop: terminate ONLY the given pod at the deadline, then verify. usage: watchdog.sh POD_ID DEADLINE_EPOCH
POD="$1"; DL="$2"; L=/tmp/claude-0/watchdog.log; R=/tmp/claude-0/rest.sh
echo "$(date -u +%FT%TZ) watchdog armed pod=$POD deadline=$(date -u -d @$DL +%FT%TZ)" >> $L
while [ "$(date +%s)" -lt "$DL" ]; do
  [ -f /tmp/claude-0/terminated.$POD ] && { echo "$(date -u +%FT%TZ) already terminated by operator; exit" >> $L; exit 0; }
  sleep 5
done
for i in 1 2 3 4 5 6; do
  out=$($R GET /pods/$POD); echo "$out" | grep -q '"id"' || { echo "$(date -u +%FT%TZ) pod gone: $out" >> $L; exit 0; }
  echo "$(date -u +%FT%TZ) deadline: DELETE /pods/$POD -> $($R DELETE /pods/$POD)" >> $L
  sleep 10
done
echo "$(date -u +%FT%TZ) WARNING: pod may still exist after 6 attempts" >> $L
