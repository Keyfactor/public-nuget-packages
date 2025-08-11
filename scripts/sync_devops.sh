#!/usr/bin/env bash

# CONFIG
AZURE_PAT="${AZ_DEVOPS_PAT}"
GITHUB_PAT="${GITHUB_TOKEN}"
GITHUB_ORG="keyfactor"
AZURE_ORG="Keyfactor"
AZURE_PROJECT="Engineering"  # Adjust if needed
#AZURE_FEED="KeyfactorPackages"
AZURE_FEED="b9291bd8-a79d-4353-8a07-09631feaa444"


TMP_DIR="./nupkgs"
mkdir -p "$TMP_DIR"

# Get packages
PACKAGES_URL="https://feeds.dev.azure.com/${AZURE_ORG}/_apis/packaging/feeds/${AZURE_FEED}/packages?api-version=7.1"

echo "Fetching packages..."
echo curl -u ":$AZURE_PAT" "$PACKAGES_URL"
curl -u ":$AZURE_PAT" "$PACKAGES_URL"
PACKAGE_LIST=$(curl -s -u ":$AZURE_PAT" "$PACKAGES_URL")
echo "$PACKAGE_LIST" > packages.json
echo "$PACKAGE_LIST" | jq -c '.value[]' | while read -r pkg; do
  NAME=$(echo "$pkg" | jq -r '.name')
  VERSIONS_URL=$(echo "$pkg" | jq -r '.versionsUrl')

  echo "Fetching versions for $NAME..."
  curl -u ":$AZURE_PAT" "$VERSIONS_URL?api-version=7.1"
  VERSION_LIST=$(curl -s -u ":$AZURE_PAT" "$VERSIONS_URL?api-version=7.1")

  echo $VERSION_LIST
  echo "$VERSION_LIST" | jq -c '.value[]' | while read -r ver; do
    VERSION=$(echo "$ver" | jq -r '.version')
    DOWNLOAD_URL=$(echo "$ver" | jq -r '._links.content.href')

    FILE="$TMP_DIR/${NAME}.${VERSION}.nupkg"
    if [ -f "$FILE" ]; then
      echo "Already downloaded: $FILE"
    else
      echo "Downloading $NAME $VERSION..."
      curl -s -u ":$AZURE_PAT" -L "$DOWNLOAD_URL" -o "$FILE"
    fi

    echo "Pushing $NAME $VERSION to GitHub Packages..."
    dotnet nuget push "$FILE" \
      --source "https://nuget.pkg.github.com/$GITHUB_ORG/index.json" \
      --api-key "$GITHUB_PAT" \
      --skip-duplicate
  done
done

echo "Done!"
