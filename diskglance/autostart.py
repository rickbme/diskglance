"""Optional start-at-login + background permission. Works on the host and in Flatpak."""
import os
import sys

from gi.repository import Gio, GLib

APP_ID = "io.github.rickbme.DiskGlance"
IN_FLATPAK = os.path.exists("/.flatpak-info")
AUTOSTART = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
                         "autostart", f"{APP_ID}.desktop")


def _launcher() -> str:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return f"{sys.executable} {os.path.join(root, 'diskglance.py')}"


def _portal(background: bool, autostart: bool):
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        opts = {
            "reason": GLib.Variant("s", "Warn you when a drive is almost full"),
            "autostart": GLib.Variant("b", bool(autostart and background)),
            "commandline": GLib.Variant("as", ["diskglance", "--background"]),
            "dbus-activatable": GLib.Variant("b", False),
        }
        bus.call("org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop",
                 "org.freedesktop.portal.Background", "RequestBackground",
                 GLib.Variant("(sa{sv})", ("", opts)), None, Gio.DBusCallFlags.NONE, -1, None, None)
    except Exception:
        pass


def apply(background: bool, autostart: bool):
    """Sync system state with the settings. Autostart only ever applies if background is on."""
    want = bool(background and autostart)
    if IN_FLATPAK:
        _portal(background, want)
        return
    try:
        if want:
            os.makedirs(os.path.dirname(AUTOSTART), exist_ok=True)
            with open(AUTOSTART, "w") as f:
                f.write("[Desktop Entry]\nType=Application\nName=DiskGlance\n"
                        f"Exec={_launcher()} --background\nIcon={APP_ID}\n"
                        "X-GNOME-Autostart-enabled=true\nNoDisplay=true\n")
        elif os.path.exists(AUTOSTART):
            os.remove(AUTOSTART)
    except OSError:
        pass
