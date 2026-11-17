"""Custom-drawn widgets using GTK4's native snapshot API (no Cairo dependency)."""
import math

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gsk", "4.0")
gi.require_version("Graphene", "1.0")
gi.require_version("Pango", "1.0")
from gi.repository import Gdk, Graphene, Gsk, Gtk, Pango  # noqa: E402

from . import drives, treemap  # noqa: E402


def rgba(hex_or_tuple, alpha=1.0) -> Gdk.RGBA:
    c = Gdk.RGBA()
    c.parse(hex_or_tuple)
    c.alpha = alpha
    return c


def stop(offset, color) -> Gsk.ColorStop:
    s = Gsk.ColorStop()
    s.offset, s.color = offset, color
    return s


def rect(x, y, w, h):
    return Graphene.Rect().init(x, y, w, h)


def point(x, y):
    return Graphene.Point().init(x, y)


# (css class, gradient start, gradient end) by usage level
LEVELS = {
    "ok":   ("dg-ok",   "#22d3ee", "#8b5cf6"),
    "warn": ("dg-warn", "#fbbf24", "#f97316"),
    "crit": ("dg-crit", "#fb7185", "#e11d48"),
}


def level(pct, warn=80, crit=90):
    return LEVELS["crit" if pct >= crit else "warn" if pct >= warn else "ok"]


class Ring(Gtk.Widget):
    """Gradient donut: used (gradient arc) vs free (faint track)."""

    def __init__(self, size=124, warn=80, crit=90):
        super().__init__()
        self.pct, self.size, self.warn, self.crit = 0.0, size, warn, crit
        self.set_size_request(size, size)

    def set_percent(self, pct):
        self.pct = pct
        self.queue_draw()

    def do_measure(self, orientation, for_size):
        return self.size, self.size, -1, -1

    def _arc(self, cx, cy, r, frac):
        pb = Gsk.PathBuilder.new()
        n = max(2, int(200 * frac))
        for i in range(n + 1):
            a = -math.pi / 2 + 2 * math.pi * frac * i / n
            x, y = cx + r * math.cos(a), cy + r * math.sin(a)
            pb.move_to(x, y) if i == 0 else pb.line_to(x, y)
        return pb.to_path()

    def do_snapshot(self, snap):
        w, h = self.get_width(), self.get_height()
        cx, cy, thick = w / 2, h / 2, 13
        r = min(w, h) / 2 - thick / 2 - 3
        fg = self.get_color()
        track = Gdk.RGBA()
        track.red, track.green, track.blue, track.alpha = fg.red, fg.green, fg.blue, 0.12
        snap.push_stroke(self._arc(cx, cy, r, 0.9999), Gsk.Stroke.new(thick))
        snap.append_color(track, rect(0, 0, w, h))
        snap.pop()
        if self.pct <= 0:
            return
        frac = min(self.pct, 99.9) / 100
        _, c1, c2 = level(self.pct, self.warn, self.crit)
        st = Gsk.Stroke.new(thick)
        st.set_line_cap(Gsk.LineCap.ROUND)
        snap.push_stroke(self._arc(cx, cy, r, frac), st)
        snap.append_conic_gradient(
            rect(0, 0, w, h), point(cx, cy), -8,   # start a bit early so the round cap stays c1
            [stop(0, rgba(c1)), stop(8 / 360, rgba(c1)), stop(frac + 8 / 360, rgba(c2)), stop(1, rgba(c2))])
        snap.pop()


PALETTE = [("#22d3ee", "#0ea5e9"), ("#a78bfa", "#7c3aed"), ("#f472b6", "#db2777"),
           ("#34d399", "#059669"), ("#fbbf24", "#d97706"), ("#60a5fa", "#2563eb"),
           ("#fb7185", "#e11d48"), ("#2dd4bf", "#0d9488"), ("#c084fc", "#9333ea"),
           ("#a3e635", "#65a30d")]


class Treemap(Gtk.Widget):
    """WinDirStat/Filelight-style map of a folder's children. Click a block to dive in."""

    def __init__(self, on_activate):
        super().__init__()
        self.on_activate = on_activate
        self.items: list = []          # [(size, entry|None, label)]
        self.rects: list = []
        self.hover = -1
        self.set_size_request(-1, 260)
        self.set_hexpand(True)
        self.set_focusable(True)
        mo = Gtk.EventControllerMotion()
        mo.connect("motion", self._motion)
        mo.connect("leave", lambda *_: self._set_hover(-1))
        self.add_controller(mo)
        click = Gtk.GestureClick()
        click.connect("released", self._click)
        self.add_controller(click)

    def set_items(self, items):
        self.items = items
        self._layout()
        self.queue_draw()

    def do_size_allocate(self, w, h, baseline):
        self._layout()

    def _layout(self):
        w, h = self.get_width(), self.get_height()
        self.rects = treemap.squarify([(s, (i)) for i, (s, _, _) in enumerate(self.items)], 0, 0, w, h)

    def _at(self, x, y):
        for rx, ry, rw, rh, i in self.rects:
            if rx <= x < rx + rw and ry <= y < ry + rh:
                return i
        return -1

    def _motion(self, _c, x, y):
        self._set_hover(self._at(x, y))

    def _set_hover(self, i):
        if i != self.hover:
            self.hover = i
            if i >= 0:
                s, e, label = self.items[i]
                self.set_tooltip_text(f"{label}\n{drives.human(s)}")
                self.set_cursor_from_name("pointer" if e is not None and e.is_dir else None)
            else:
                self.set_tooltip_text(None)
                self.set_cursor_from_name(None)
            self.queue_draw()

    def _click(self, _g, _n, x, y):
        i = self._at(x, y)
        if i >= 0 and self.items[i][1] is not None and self.items[i][1].is_dir:
            self.on_activate(self.items[i][1])

    def do_snapshot(self, snap):
        gap = 2
        total = sum(s for s, _, _ in self.items) or 1
        for rx, ry, rw, rh, i in self.rects:
            size, entry, label = self.items[i]
            x, y, w, h = rx + gap, ry + gap, rw - 2 * gap, rh - 2 * gap
            if w < 2 or h < 2:
                continue
            c1, c2 = ("#64748b", "#334155") if entry is None else PALETTE[i % len(PALETTE)]
            rr = Gsk.RoundedRect()
            rr.init_from_rect(rect(x, y, w, h), 8)
            snap.push_rounded_clip(rr)
            snap.append_linear_gradient(rect(x, y, w, h), point(x, y), point(x + w, y + h),
                                        [stop(0, rgba(c1)), stop(1, rgba(c2))])
            if i == self.hover:
                snap.append_color(rgba("#ffffff", 0.18), rect(x, y, w, h))
            snap.pop()
            if w > 70 and h > 38:
                lay = self.create_pango_layout(label)
                lay.set_width(int((w - 16) * Pango.SCALE))
                lay.set_ellipsize(Pango.EllipsizeMode.END)
                lay.set_height(-1)
                fd = Pango.FontDescription.from_string("Bold 10")
                lay.set_font_description(fd)
                snap.save()
                snap.translate(point(x + 8, y + 6))
                snap.append_layout(lay, rgba("#ffffff", 0.95))
                snap.restore()
                sub = self.create_pango_layout(f"{drives.human(size)} · {size / total * 100:.0f}%")
                sub.set_font_description(Pango.FontDescription.from_string("Monospace 8"))
                snap.save()
                snap.translate(point(x + 8, y + 24))
                snap.append_layout(sub, rgba("#ffffff", 0.75))
                snap.restore()
