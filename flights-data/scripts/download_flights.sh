#!/bin/bash

# Metro airports
AIRPORTS=("DEL" "BOM" "BLR" "MAA" "CCU" "HYD")
DATE="10/10/2025"
DATE_FILENAME="20251010"

echo "Starting download of flight data for ${#AIRPORTS[@]} airports..."
echo "Date: $DATE"
echo ""

# Counter
TOTAL=0
SUCCESS=0

# Download flights for all combinations
for origin in "${AIRPORTS[@]}"; do
    for dest in "${AIRPORTS[@]}"; do
        # Skip same origin and destination
        if [ "$origin" != "$dest" ]; then
            TOTAL=$((TOTAL + 1))
            FILENAME="flights_${origin}_${dest}_${DATE_FILENAME}.json"

            echo "[$TOTAL/30] Downloading $origin -> $dest..."

            URL="https://www.cleartrip.com/flight/search/v2?from=${origin}&source_header=${origin}&to=${dest}&destination_header=${dest}&depart_date=${DATE}&class=Economy&adults=1&childs=0&infants=0&mobileApp=true&intl=n&responseType=jsonV3&source=DESKTOP&utm_currency=INR&sft=&return_date=&carrier=&cfw=false&multiFare=true&isFFSC=true"

            if curl -s "$URL" -o "$FILENAME" 2>/dev/null; then
                # Check if file has content
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
        fi
    done
done

echo ""
echo "Download complete: $SUCCESS/$TOTAL successful"
