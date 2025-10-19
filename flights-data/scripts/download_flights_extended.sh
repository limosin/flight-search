#!/bin/bash

# Extended airport list: 6 existing metros + 5 new airports
METRO_AIRPORTS=("DEL" "BOM" "BLR" "MAA" "CCU" "HYD")
NEW_AIRPORTS=("AMD" "PNQ" "GOI" "COK" "JAI")

# Routes between new airports (selected for high demand)
INTER_NEW_ROUTES=(
    "AMD JAI"
    "JAI AMD"
    "AMD PNQ"
    "PNQ AMD"
    "PNQ GOI"
    "GOI PNQ"
    "GOI COK"
    "COK GOI"
    "JAI PNQ"
    "PNQ JAI"
)

DATE="11/10/2025"
DATE_FILENAME="20251011"

echo "==================================================="
echo "EXTENDED FLIGHT DATA DOWNLOAD"
echo "==================================================="
echo "Adding 5 new airports: AMD, PNQ, GOI, COK, JAI"
echo "Target: 70 new routes (100 total)"
echo "Date: $DATE"
echo ""

TOTAL=0
SUCCESS=0
SKIPPED=0

# Function to download a route
download_route() {
    local origin=$1
    local dest=$2

    TOTAL=$((TOTAL + 1))
    FILENAME="flights_${origin}_${dest}_${DATE_FILENAME}.json"

    # Skip if file already exists
    if [ -f "$FILENAME" ]; then
        echo "  ⊘ Skipped (already exists)"
        SKIPPED=$((SKIPPED + 1))
        return
    fi

    URL="https://www.cleartrip.com/flight/search/v2?from=${origin}&source_header=${origin}&to=${dest}&destination_header=${dest}&depart_date=${DATE}&class=Economy&adults=1&childs=0&infants=0&mobileApp=true&intl=n&responseType=jsonV3&source=DESKTOP&utm_currency=INR&sft=&return_date=&carrier=&cfw=false&multiFare=true&isFFSC=true"

    if curl -s "$URL" -o "$FILENAME" 2>/dev/null; then
        if [ -s "$FILENAME" ]; then
            SUCCESS=$((SUCCESS + 1))
            echo "  ✓ Saved to $FILENAME"
        else
            echo "  ✗ Failed - empty response"
        fi
    else
        echo "  ✗ Failed - curl error"
    fi

    # Small delay to avoid rate limiting
    sleep 1
}

# Category 1: New airports to/from existing metros (60 routes)
echo "CATEGORY 1: New Airports ↔ Metro Airports (60 routes)"
echo "========================================================"
for new_airport in "${NEW_AIRPORTS[@]}"; do
    for metro_airport in "${METRO_AIRPORTS[@]}"; do
        # New -> Metro
        echo "[$(($TOTAL + 1))] Downloading $new_airport -> $metro_airport..."
        download_route "$new_airport" "$metro_airport"

        # Metro -> New
        echo "[$(($TOTAL + 1))] Downloading $metro_airport -> $new_airport..."
        download_route "$metro_airport" "$new_airport"
    done
done

echo ""
echo "CATEGORY 2: Routes Between New Airports (10 routes)"
echo "====================================================="
for route in "${INTER_NEW_ROUTES[@]}"; do
    read -r origin dest <<< "$route"
    echo "[$(($TOTAL + 1))] Downloading $origin -> $dest..."
    download_route "$origin" "$dest"
done

echo ""
echo "==================================================="
echo "DOWNLOAD COMPLETE"
echo "==================================================="
echo "Total attempted: $TOTAL"
echo "Successfully downloaded: $SUCCESS"
echo "Skipped (existing): $SKIPPED"
echo ""

# Count total files
TOTAL_FILES=$(ls flights_*_20251010.json 2>/dev/null | wc -l | tr -d ' ')
echo "Total route files now: $TOTAL_FILES"
