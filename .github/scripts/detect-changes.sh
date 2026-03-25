#!/bin/bash

# Script to detect which services have changed

set -e

# Get changed files
CHANGED_FILES=$(git diff --name-only HEAD^ HEAD)

# Extract unique service names
SERVICES=()
for file in $CHANGED_FILES; do
    if [[ $file == services/* ]]; then
        service=$(echo $file | cut -d'/' -f2)
        if [[ ! " ${SERVICES[@]} " =~ " ${service} " ]]; then
            SERVICES+=("$service")
        fi
    fi
done

# Convert to JSON array
if [ ${#SERVICES[@]} -eq 0 ]; then
    echo "[]"
else
    printf '%s\n' "${SERVICES[@]}" | jq -R . | jq -s .
fi
