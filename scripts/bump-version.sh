#!/usr/bin/env bash
# Usage: ./scripts/bump-version.sh 0.2.0
NEW_VERSION=$1
if [ -z "$NEW_VERSION" ]; then
  echo "Usage: $0 <version>"
  exit 1
fi

for f in services/*/pyproject.toml; do
  sed -i '' "s/^version = \".*\"/version = \"$NEW_VERSION\"/" "$f"
  echo "Updated $f"
done

echo "All services bumped to $NEW_VERSION"
echo "Next: git add services/*/pyproject.toml && git commit -m \"chore: bump version to $NEW_VERSION\""
