#!/usr/bin/env bash
# Downloads the official regulation documents listed in manifest.csv.
# Run from the driver-ops folder on your own machine:   bash fetch_corpus.sh
# Needs: bash, curl. Output: corpus/regulations/<doc_id>.<html|pdf> + fetch_log.txt
set -u
cd "$(dirname "$0")"
OUT="corpus/regulations"
LOG="$OUT/fetch_log.txt"
UA="Mozilla/5.0 (DriverOps corpus fetch; personal research)"
: > "$LOG"
ok=0; fail=0

tail -n +2 "$OUT/manifest.csv" | while IFS=, read -r id title juris fmt url; do
  dest="$OUT/$id.$fmt"
  if [ -s "$dest" ]; then echo "skip $id (exists)"; continue; fi
  code=$(curl -sSL -A "$UA" --retry 2 --max-time 60 -o "$dest" -w "%{http_code}" "$url" || echo "000")
  if [ "$code" = "200" ] && [ -s "$dest" ]; then
    echo "ok   $id  $title" | tee -a "$LOG"
  else
    echo "FAIL $id  HTTP $code  $url" | tee -a "$LOG"
    rm -f "$dest"
  fi
  sleep 2   # be polite to government servers
done

echo
echo "Done. See $LOG. Re-run to retry failures (existing files are skipped)."
