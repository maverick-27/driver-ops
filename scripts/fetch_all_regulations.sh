#!/bin/bash
# Comprehensive fetch: all 13 Canadian jurisdictions + federal regulations

set -e

DEST="corpus/regulations"
LOG="$DEST/fetch_all_regulations.log"

echo "Fetching ALL Canadian trucking regulations (13 jurisdictions)..." | tee "$LOG"
echo "Started: $(date)" >> "$LOG"

# Helper function to fetch and log
fetch_reg() {
    local url=$1
    local output=$2
    local name=$3

    echo -n "Fetching $name... " | tee -a "$LOG"
    if curl -s -L "$url" -o "$output" --max-time 10 2>/dev/null; then
        echo "✓" | tee -a "$LOG"
        return 0
    else
        echo "⚠ (may need manual download)" | tee -a "$LOG"
        return 1
    fi
}

# Federal regulations
echo "" | tee -a "$LOG"
echo "=== FEDERAL ===" | tee -a "$LOG"
mkdir -p $DEST/federal/fmvss
fetch_reg "https://laws-lois.justice.gc.ca/eng/regulations/2009-318/FullText.html" \
    "$DEST/federal/fmvss/FMVSS_Part_318.html" "Federal FMVSS Part 318"

# Ontario (R02) ✓ Already done
echo "" | tee -a "$LOG"
echo "=== PROVINCES ===" | tee -a "$LOG"

# BC (R03) ✓ Already done

# Alberta (R04) ✓ Already done

# Saskatchewan
echo "Saskatchewan:" | tee -a "$LOG"
mkdir -p $DEST/provinces/sk
fetch_reg "https://www.canlii.org/en/sk/laws/stat/ss-1989-c-m-22.1/latest/" \
    "$DEST/provinces/sk/Motor_Vehicle_Act.html" "SK Motor Vehicle Act"

# Manitoba
echo "Manitoba:" | tee -a "$LOG"
mkdir -p $DEST/provinces/mb
fetch_reg "https://www.canlii.org/en/mb/laws/stat/ccsm-m220/latest/" \
    "$DEST/provinces/mb/Highway_Traffic_Act.html" "MB Highway Traffic Act"

# Quebec
echo "Quebec:" | tee -a "$LOG"
mkdir -p $DEST/provinces/qc
fetch_reg "https://www.canlii.org/en/qc/laws/stat/cqlr-c-c-24.2/latest/" \
    "$DEST/provinces/qc/Highway_Safety_Code.html" "QC Highway Safety Code"

# New Brunswick
echo "New Brunswick:" | tee -a "$LOG"
mkdir -p $DEST/provinces/nb
fetch_reg "https://www.canlii.org/en/nb/laws/stat/rsnb-1973-c-m-14.2/latest/" \
    "$DEST/provinces/nb/Motor_Vehicle_Act.html" "NB Motor Vehicle Act"

# Nova Scotia
echo "Nova Scotia:" | tee -a "$LOG"
mkdir -p $DEST/provinces/ns
fetch_reg "https://www.canlii.org/en/ns/laws/stat/rsns-1989-c-293/latest/" \
    "$DEST/provinces/ns/Motor_Vehicle_Act.html" "NS Motor Vehicle Act"

# Prince Edward Island
echo "Prince Edward Island:" | tee -a "$LOG"
mkdir -p $DEST/provinces/pe
fetch_reg "https://www.canlii.org/en/pe/laws/stat/rspei-1988-c-m-17/latest/" \
    "$DEST/provinces/pe/Motor_Vehicle_Act.html" "PE Motor Vehicle Act"

# Newfoundland & Labrador
echo "Newfoundland & Labrador:" | tee -a "$LOG"
mkdir -p $DEST/provinces/nl
fetch_reg "https://www.canlii.org/en/nl/laws/stat/rsnl-1990-c-m-25/latest/" \
    "$DEST/provinces/nl/Highway_Traffic_Act.html" "NL Highway Traffic Act"

# Yukon
echo "Yukon:" | tee -a "$LOG"
mkdir -p $DEST/provinces/yt
fetch_reg "https://www.canlii.org/en/yt/laws/stat/rsy-2002-c-153/latest/" \
    "$DEST/provinces/yt/Motor_Vehicles_Act.html" "YT Motor Vehicles Act"

# Northwest Territories
echo "Northwest Territories:" | tee -a "$LOG"
mkdir -p $DEST/provinces/nt
fetch_reg "https://www.canlii.org/en/nt/laws/stat/snwt-1988-c-m-18/latest/" \
    "$DEST/provinces/nt/Motor_Vehicles_Ordinance.html" "NT Motor Vehicles Ordinance"

# Nunavut
echo "Nunavut:" | tee -a "$LOG"
mkdir -p $DEST/provinces/nu
fetch_reg "https://www.canlii.org/en/nu/laws/stat/snu-2003-c-17/latest/" \
    "$DEST/provinces/nu/Motor_Vehicles_Ordinance.html" "NU Motor Vehicles Ordinance"

echo "" | tee -a "$LOG"
echo "✅ Fetch complete! $(date)" >> "$LOG"
find $DEST -type f -name "*.html" | wc -l | xargs echo "Total HTML files:" | tee -a "$LOG"
