#!/bin/bash

echo "Extracting statistics from flight data..."
echo ""

# Initialize summary JSON
echo "{" > routes_summary.json
echo '  "generatedDate": "'$(date -u +"%Y-%m-%dT%H:%M:%SZ")'",' >> routes_summary.json
echo '  "travelDate": "2025-10-10",' >> routes_summary.json
echo '  "routes": {' >> routes_summary.json

FIRST_ROUTE=true

# Process each JSON file
for file in flights_*_20251010.json; do
    if [ -f "$file" ]; then
        # Extract route info from filename
        ROUTE=$(echo "$file" | sed 's/flights_//' | sed 's/_20251010.json//' | sed 's/_/ -> /')
        ORIGIN=$(echo "$file" | cut -d'_' -f2)
        DEST=$(echo "$file" | cut -d'_' -f3)

        # Extract statistics using jq
        TOTAL=$(jq '.cards.J1 | length' "$file" 2>/dev/null || echo "0")
        DIRECT=$(jq '[.cards.J1[] | select(.summary.stops == 0)] | length' "$file" 2>/dev/null || echo "0")
        CARRIERS=$(jq -r '[.cards.J1[].summary.flights[0].airlineCode] | unique | join(", ")' "$file" 2>/dev/null || echo "N/A")
        LAYOVERS=$(jq -r '[.cards.J1[] | select(.summary.stops > 0) | .layover[].airport] | unique | join(", ")' "$file" 2>/dev/null || echo "N/A")

        # Add comma before route if not first
        if [ "$FIRST_ROUTE" = false ]; then
            echo "    ," >> routes_summary.json
        fi
        FIRST_ROUTE=false

        # Add to JSON summary
        echo "    \"${ORIGIN}_${DEST}\": {" >> routes_summary.json
        echo "      \"origin\": \"$ORIGIN\"," >> routes_summary.json
        echo "      \"destination\": \"$DEST\"," >> routes_summary.json
        echo "      \"totalFlights\": $TOTAL," >> routes_summary.json
        echo "      \"directFlights\": $DIRECT," >> routes_summary.json
        echo "      \"carriers\": \"$CARRIERS\"," >> routes_summary.json
        echo "      \"layoverAirports\": \"$LAYOVERS\"" >> routes_summary.json
        echo -n "    }" >> routes_summary.json

        echo "✓ $ROUTE: $TOTAL flights ($DIRECT direct)"
    fi
done

# Close JSON
echo "" >> routes_summary.json
echo "  }" >> routes_summary.json
echo "}" >> routes_summary.json

echo ""
echo "Statistics extracted successfully!"
echo "Generated: routes_summary.json"
