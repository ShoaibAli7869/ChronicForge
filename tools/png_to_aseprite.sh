#!/usr/bin/env bash
# tools/png_to_aseprite.sh
# Converts all female_hero PNG strips to .aseprite source files.
# Requires full Aseprite license (trial version blocks --save-as).
set -e
SPRITES="assets/sprites"
ASEPRITE="/usr/bin/aseprite"

for png in "$SPRITES"/female_hero-*.png; do
    base="${png%.png}"
    ase="${base}.aseprite"
    echo "Converting $(basename "$png") → $(basename "$ase")"
    "$ASEPRITE" --batch "$png" --save-as "$ase"
done
echo "Done. $(ls "$SPRITES"/female_hero-*.aseprite 2>/dev/null | wc -l) .aseprite files created."
