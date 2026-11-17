import math
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gsk", "4.0")
from gi.repository import Adw, Gdk, GLib, Gsk, Gtk  # noqa: E402

from . import __version__, drives  # noqa: E402

WARN, CRIT = 80, 90
REFRESH_SECONDS = 5

CSS = b"""
.dg-title   { font-family: monospace; font-weight: 800; font-size: 15pt; }
.dg-card    { padding: 18px; border-radius: 14px; }
.dg-name    { font-weight: 700; font-size: 12pt; }
.dg-mono    { font-family: monospace; }
.dg-big     { font-family: monospace; font-weight: 800; font-size: 20pt; }
.dg-sub     { opacity: 0.65; font-size: 9pt; }
.dg-chip    { font-family: monospace; font-size: 8pt; padding: 1px 8px;
              border-radius: 99px; background: alpha(currentColor, 0.10); }
progressbar.dg-ok    progress { background: #3584e4; }
progressbar.dg-warn  progress { background: #e5a50a; }
progressbar.dg-crit  progress { background: #e01b24; }
progressbar trough, progressbar progress { min-height: 10px; border-radius: 99px; }
"""

KIND_ICON = {
    "ssd": "drive-harddisk-solidstate-symbolic",
    "hdd": "drive-harddisk-symbolic",
    "removable": "drive-removable-media-symbolic",
    "network": "folder-remote-symbolic",
    "other": "drive-harddisk-symbolic",
}


def level(pct: float) -> tuple[str, tuple[float, float, float]]:
    if pct >= CRIT:
        return "dg-crit", (0.88, 0.11, 0.14)
    if pct >= WARN:
        return "dg-warn", (0.90, 0.65, 0.04)
    return "dg-ok", (0.21, 0.52, 0.89)


class Donut(Gtk.Widget):
    """Ring chart: used (coloured) vs free (muted). Native GTK snapshot drawing."""

    def __init__(self, size=120):
        super().__init__()
        self.pct = 0.0
        self.size = size
        self.set_size_request(size, size)

    def set_percent(self, pct):
        self.pct = pct
        self.queue_draw()

    def do_measure(self, orientation, for_size):
        return self.size, self.size, -1, -1

    def do_snapshot(self, snap):
        w, h = self.get_width(), self.get_height()
        cx, cy, thick = w / 2, h / 2, 14
        r = min(w, h) / 2 - thick / 2 - 2

        fg = self.get_color()
        track = Gdk.RGBA(); track.red, track.green, track.blue, track.alpha = fg.red, fg.green, fg.blue, 0.13
        col = Gdk.RGBA(); col.red, col.green, col.blue = level(self.pct)[1]; col.alpha = 1

        def arc(frac):
            pb = Gsk.PathBuilder.new()
            n = max(2, int(180 * frac))
            for i in range(n + 1):
                ang = -math.pi / 2 + 2 * math.pi * frac * i / n
                x, y = cx + r * math.cos(ang), cy + r * math.sin(ang)
                pb.move_to(x, y) if i == 0 else pb.line_to(x, y)
            return pb.to_path()

        snap.append_stroke(arc(0.9999), Gsk.Stroke.new(thick), track)
        if self.pct > 0:
            st = Gsk.Stroke.new(thick)
            st.set_line_cap(Gsk.LineCap.ROUND)
            snap.append_stroke(arc(min(self.pct, 99.99) / 100), st, col)


class DriveCard(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=18)
        self.add_css_class("card")
        self.add_css_class("dg-card")
        self.donut = Donut()
        overlay = Gtk.Overlay(child=self.donut)
        self.pct_label = Gtk.Label(css_classes=["dg-big"], halign=Gtk.Align.CENTER,
                                   valign=Gtk.Align.CENTER)
        overlay.add_overlay(self.pct_label)
        self.append(overlay)

        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, hexpand=True,
                      valign=Gtk.Align.CENTER)
        head = Gtk.Box(spacing=8)
        self.icon = Gtk.Image(pixel_size=20)
        self.name = Gtk.Label(css_classes=["dg-name"], xalign=0, ellipsize=3)
        self.chip = Gtk.Label(css_classes=["dg-chip"])
        head.append(self.icon); head.append(self.name); head.append(self.chip)
        self.sub = Gtk.Label(css_classes=["dg-sub", "dg-mono"], xalign=0, ellipsize=3)
        self.bar = Gtk.ProgressBar()
        self.stats = Gtk.Label(css_classes=["dg-mono"], xalign=0)
        for w in (head, self.sub, self.bar, self.stats):
            col.append(w)
        self.append(col)

    def update(self, d: drives.Drive):
        css, _ = level(d.percent)
        for c in ("dg-ok", "dg-warn", "dg-crit"):
            self.bar.remove_css_class(c)
        self.bar.add_css_class(css)
        self.bar.set_fraction(d.percent / 100)
        self.donut.set_percent(d.percent)
        self.pct_label.set_text(f"{d.percent:.0f}%")
        self.icon.set_from_icon_name(KIND_ICON.get(d.kind, KIND_ICON["other"]))
        self.name.set_text(d.label)
        self.chip.set_text(f"{d.kind.upper()} · {d.fstype}")
        self.sub.set_text(f"{d.device}  →  {d.mountpoint}")
        self.stats.set_markup(
            f"<b>{drives.human(d.free)}</b> free of {drives.human(d.total)}"
            f"   <span alpha='65%'>({drives.human(d.used)} used)</span>")


class Window(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="DiskGlance",
                         default_width=760, default_height=640)
        self.cards: dict[str, DriveCard] = {}
        self.show_system = False

        view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.set_title_widget(Gtk.Label(label="▮▮▯ DiskGlance", css_classes=["dg-title"]))
        refresh = Gtk.Button(icon_name="view-refresh-symbolic", tooltip_text="Rescan now")
        refresh.connect("clicked", lambda *_: self.refresh())
        header.pack_start(refresh)
        toggle = Gtk.ToggleButton(icon_name="view-list-symbolic",
                                  tooltip_text="Show system / snap mounts")
        toggle.connect("toggled", self._on_toggle)
        header.pack_end(toggle)
        view.add_top_bar(header)

        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14,
                           margin_top=18, margin_bottom=18, margin_start=18, margin_end=18)
        self.summary = Gtk.Label(css_classes=["dg-sub", "dg-mono"], xalign=0)
        self.box.append(self.summary)
        self.list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        self.box.append(self.list)
        clamp = Adw.Clamp(maximum_size=900, child=self.box)
        view.set_content(Gtk.ScrolledWindow(child=clamp, vexpand=True))
        self.set_content(view)

        self.refresh()
        GLib.timeout_add_seconds(REFRESH_SECONDS, self._tick)

    def _tick(self):
        self.refresh()
        return True

    def _on_toggle(self, btn):
        self.show_system = btn.get_active()
        self.refresh()

    def refresh(self):
        found = drives.scan(self.show_system)
        keys = {d.device + d.mountpoint for d in found}
        for k in list(self.cards):
            if k not in keys:
                self.list.remove(self.cards.pop(k))
        for d in found:
            k = d.device + d.mountpoint
            if k not in self.cards:
                self.cards[k] = DriveCard()
                self.list.append(self.cards[k])
            self.cards[k].update(d)
        tot = sum(d.total for d in found if not d.is_snap)
        free = sum(d.free for d in found if not d.is_snap)
        self.summary.set_text(
            f"{len(found)} drive(s) · {drives.human(free)} free of {drives.human(tot)} total"
            f" · auto-refresh {REFRESH_SECONDS}s")


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id="io.github.rickbme.DiskGlance")

    def do_activate(self):
        prov = Gtk.CssProvider()
        prov.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        (self.get_active_window() or Window(self)).present()


def main():
    return App().run(sys.argv)
