#!/usr/bin/env bash
# Download the word lists used by the lexical null tests (pinned commits).
set -euo pipefail
DEST="$(dirname "$0")/../data/lexicons"
mkdir -p "$DEST"
# Quechua (Ayacucho) headwords from the MINEDU dictionary, via the AmericasNLP 2021 shared task (CC BY-SA / research use)
ANLP_COMMIT="${ANLP_COMMIT:-d3f519c6b38299d8149311e65a369047350e6849}"
curl -fsSL "https://raw.githubusercontent.com/AmericasNLP/americasnlp2021/${ANLP_COMMIT}/data/quechua-spanish/dict.quy" -o "$DEST/quechua_minedu_dict.quy"
# Swahili Hunspell word list from LibreOffice dictionaries (used as a 'wrong language' control)
LO_COMMIT="${LO_COMMIT:-32b006a2c22a4ac7e8ed3f03346f7b3d85a970a4}"
curl -fsSL "https://raw.githubusercontent.com/LibreOffice/dictionaries/${LO_COMMIT}/sw_TZ/sw_TZ.dic" -o "$DEST/swahili_sw_TZ.dic"
(cd "$DEST" && sha256sum quechua_minedu_dict.quy swahili_sw_TZ.dic | tee SHA256SUMS)
