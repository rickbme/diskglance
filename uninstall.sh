#!/bin/sh
DEST="${XDG_DATA_HOME:-$HOME/.local/share}"
rm -rf "$DEST/diskglance" "$HOME/.local/bin/diskglance" \
  "$DEST/applications/io.github.rickbme.DiskGlance.desktop" \
  "$DEST/icons/hicolor/scalable/apps/io.github.rickbme.DiskGlance.svg"
echo "DiskGlance removed (settings in ~/.config/diskglance were kept)."
