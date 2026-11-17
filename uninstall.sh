#!/bin/sh
DEST="${XDG_DATA_HOME:-$HOME/.local/share}"
rm -rf "$DEST/diskglance" "$HOME/.local/bin/diskglance" \
  "$DEST/applications/io.github.rickbme.DiskGlance.desktop" \
  "$DEST"/icons/hicolor/*/apps/io.github.rickbme.DiskGlance.png \
  "$HOME/.config/autostart/io.github.rickbme.DiskGlance.desktop"
echo "DiskGlance removed (settings in ~/.config/diskglance were kept)."
