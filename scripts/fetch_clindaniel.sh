#!/usr/bin/env bash
# Assets for Study 03: Clindaniel's "AI khipukamayuq" (MIT licensed) and the OKR version it used.
#   - code + tokenizer from github.com/jonclindaniel/colorful-ai-khipukamayuq at a pinned commit
#   - selected Git-LFS files fetched from media.githubusercontent.com and checked against their LFS sha256
#   - Open Khipu Repository v2.0.0 khipu.db (the version used for training and analysis)
set -euo pipefail
COMMIT="41cde6e850664aa31e2b17568887bb2d5d252295"
OKR_V2_COMMIT="0a936e9fd2abaea8c04e2f8b9219f703b1153c21"   # tag v2.0.0
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/data/clindaniel"
LFS_FILES=(
  "pretrained-bert/checkpoint-400/pytorch_model.bin"   # trained model weights (438 MB)
  # published embeddings for small colours, used to check that the checkpoint reproduces them
  "data/test/data-00000-of-00001.arrow"                  # held-out MLM data: checks the checkpoint reaches its logged eval loss
  "data/token_embeddings_M3/data-00000-of-00001.arrow"
  "data/token_embeddings_Y2/data-00000-of-00001.arrow"
  "data/token_embeddings_R2/data-00000-of-00001.arrow"
  "data/token_embeddings_L4/data-00000-of-00001.arrow"
)

if [ ! -d "$DEST/.git" ]; then
  GIT_LFS_SKIP_SMUDGE=1 git clone -q https://github.com/jonclindaniel/colorful-ai-khipukamayuq.git "$DEST"
fi
git -C "$DEST" -c advice.detachedHead=false checkout -q "$COMMIT"

for f in "${LFS_FILES[@]}"; do
  ptr="$(git -C "$DEST" show "$COMMIT:$f")"
  oid="$(echo "$ptr" | sed -n 's/^oid sha256:\(.*\)$/\1/p')"
  if [ -f "$DEST/$f" ] && echo "$oid  $DEST/$f" | sha256sum -c --quiet >/dev/null 2>&1; then continue; fi
  curl -fsSL --retry 4 "https://media.githubusercontent.com/media/jonclindaniel/colorful-ai-khipukamayuq/$COMMIT/$f" -o "$DEST/$f"
  echo "$oid  $DEST/$f" | sha256sum -c --quiet
done

mkdir -p "$ROOT/data/okr-v2.0.0"
[ -f "$ROOT/data/okr-v2.0.0/khipu.db" ] || curl -fsSL --retry 4 \
  "https://raw.githubusercontent.com/khipulab/open-khipu-repository/$OKR_V2_COMMIT/khipu.db" -o "$ROOT/data/okr-v2.0.0/khipu.db"
echo "Clindaniel assets ready in $DEST; OKR v2.0.0 in data/okr-v2.0.0/"
