#!/bin/sh
# Install DiskGlance for the current user (no root needed).
set -e
SRC="$(cd "$(dirname "$0")" && pwd)"
DEST="${XDG_DATA_HOME:-$HOME/.local/share}"
APP="$DEST/diskglance"
BIN="$HOME/.local/bin"

mkdir -p "$APP" "$BIN" "$DEST/applications" "$DEST/icons/hicolor/scalable/apps"
cp -r "$SRC/diskglance" "$SRC/data" "$SRC/diskglance.py" "$APP/"
cat > "$BIN/diskglance" <<LAUNCH
#!/bin/sh
exec /usr/bin/python3 "$APP/diskglance.py" "\$@"
LAUNCH
chmod +x "$BIN/diskglance"
cp "$SRC/data/icons/hicolor/scalable/apps/"*.svg "$DEST/icons/hicolor/scalable/apps/"
sed "s|@EXEC@|$BIN/diskglance|" "$SRC/data/io.github.rickbme.DiskGlance.desktop" \
  > "$DEST/applications/io.github.rickbme.DiskGlance.desktop"
command -v update-desktop-database >/dev/null && update-desktop-database "$DEST/applications" || true
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -qtf "$DEST/icons/hicolor" || true
echo "Installed. Launch 'DiskGlance' from your app menu, or run: diskglance"
