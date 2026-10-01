#!/usr/bin/env bash
# Download the Open Khipu Repository SQLite database at a pinned commit (MIT licensed).
set -euo pipefail
OKR_COMMIT="4039ca51f4de661d80d0160596309c983a62a9c7"   # khipulab/open-khipu-repository, 2026-08-04
DEST="$(dirname "$0")/../data/okr"
mkdir -p "$DEST"
if [ ! -f "$DEST/khipu.db" ]; then
  curl -fsSL "https://raw.githubusercontent.com/khipulab/open-khipu-repository/${OKR_COMMIT}/data/khipu.db" -o "$DEST/khipu.db"
fi
echo "$OKR_COMMIT" > "$DEST/COMMIT"
echo "OKR khipu.db ready at $DEST (commit $OKR_COMMIT)"
