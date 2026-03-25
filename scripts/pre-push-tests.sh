#!/bin/bash
# Run pytest on services that have changed since the last push

set -e

CHANGED_FILES=$(git diff --name-only HEAD~1 HEAD 2>/dev/null || git diff --name-only HEAD)

SERVICES_TO_TEST=()
for file in $CHANGED_FILES; do
  if [[ "$file" == services/*/app/* ]] || [[ "$file" == services/*/tests/* ]]; then
    SERVICE_DIR=$(echo "$file" | cut -d'/' -f1-2)
    if [[ ! " ${SERVICES_TO_TEST[@]} " =~ " ${SERVICE_DIR} " ]]; then
      SERVICES_TO_TEST+=("$SERVICE_DIR")
    fi
  fi
done

if [ ${#SERVICES_TO_TEST[@]} -eq 0 ]; then
  echo "No service changes detected, skipping tests."
  exit 0
fi

for SERVICE in "${SERVICES_TO_TEST[@]}"; do
  echo "Running tests for $SERVICE..."
  (cd "$SERVICE" && poetry run pytest --tb=short -q)
done

echo "All tests passed!"
