#!/bin/bash
# Fetch Canadian trucking regulations from official government sources

set -e

DEST="corpus/regulations"
LOG="corpus/regulations/fetch_log.txt"

echo "Fetching Canadian trucking regulations..." | tee "$LOG"
echo "Started: $(date)" >> "$LOG"

# Federal FMVSS (Motor Vehicle Safety Regulations)
echo "Fetching Federal FMVSS (Motor Vehicle Safety)..." | tee -a "$LOG"
mkdir -p $DEST/federal/fmvss
curl -s "https://laws-lois.justice.gc.ca/eng/regulations/2009-318/FullText.html" \
  -o "$DEST/federal/fmvss/FMVSS_2009_318.html" 2>/dev/null && \
  echo "✓ FMVSS Part 318 downloaded" | tee -a "$LOG" || \
  echo "⚠ FMVSS fetch failed (may require manual download)" | tee -a "$LOG"

# Ontario Highway Traffic Act
echo "Fetching Ontario Highway Traffic Act..." | tee -a "$LOG"
mkdir -p $DEST/provinces/on
curl -s "https://www.ontario.ca/laws/statute/990390" \
  -o "$DEST/provinces/on/Highway_Traffic_Act.html" 2>/dev/null && \
  echo "✓ Ontario HTA downloaded" | tee -a "$LOG" || \
  echo "⚠ Ontario HTA fetch failed" | tee -a "$LOG"

# BC Motor Vehicle Act
echo "Fetching BC Motor Vehicle Act..." | tee -a "$LOG"
mkdir -p $DEST/provinces/bc
curl -s "https://www.bclaws.ca/civix/document/id/complete/statreg/00_96333_01" \
  -o "$DEST/provinces/bc/Motor_Vehicle_Act.html" 2>/dev/null && \
  echo "✓ BC MVA downloaded" | tee -a "$LOG" || \
  echo "⚠ BC MVA fetch failed" | tee -a "$LOG"

# Alberta Traffic Safety Act
echo "Fetching Alberta Traffic Safety Act..." | tee -a "$LOG"
mkdir -p $DEST/provinces/ab
curl -s "https://www.canlii.org/en/ab/laws/stat/rsa-2000-c-t-6/latest/rsa-2000-c-t-6.html" \
  -o "$DEST/provinces/ab/Traffic_Safety_Act.html" 2>/dev/null && \
  echo "✓ Alberta TSA downloaded" | tee -a "$LOG" || \
  echo "⚠ Alberta TSA fetch failed" | tee -a "$LOG"

echo "" | tee -a "$LOG"
echo "Fetch complete! $(date)" >> "$LOG"
echo "Check: corpus/regulations/ for downloaded files"
