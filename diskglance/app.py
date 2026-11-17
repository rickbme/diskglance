import os
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

from . import __version__, config, drives  # noqa: E402
from .scanner import Scan  # noqa: E402
from .widgets import LEVELS, Ring, Treemap, level  # noqa: E402

APP_ID = "io.github.rickbme.DiskGlance"
REFRESH_SECONDS = 5

CSS = """
window.dg-win { background: linear-gradient(155deg, #eef4ff 0%, #f5eefc 60%, #ffeef6 100%); }
window.dg-win.dg-dark { background: linear-gradient(155deg, #080c1a 0%, #131236 55%, #230f3d 100%); }
.dg-win toolbarview, .dg-win toolbarview > *, .dg-win scrolledwindow, .dg-win viewport,
.dg-win navigation-view, .dg-win clamp { background: transparent; }
.dg-win headerbar { background: transparent; box-shadow: none; border: none; }

.dg-brand   { font-weight: 800; font-size: 14pt; letter-spacing: 0.5px; }
.dg-brand b { color: #22d3ee; }
.dg-mono    { font-family: monospace; }
.dg-dim     { opacity: 0.6; }
.dg-small   { font-size: 9pt; }
.dg-hero    { font-family: monospace; font-weight: 800; font-size: 34pt; }
.dg-name    { font-weight: 700; font-size: 12.5pt; }
.dg-pct     { font-family: monospace; font-weight: 800; font-size: 21pt; }

.dg-banner, button.dg-card {
  background: alpha(#ffffff, 0.72); border: 1px solid alpha(#000, 0.08);
  border-radius: 20px; padding: 20px; box-shadow: 0 6px 24px alpha(#5b21b6, 0.10);
}
.dg-dark .dg-banner, .dg-dark button.dg-card {
  background: alpha(#ffffff, 0.055); border: 1px solid alpha(#ffffff, 0.11);
  box-shadow: 0 8px 30px alpha(#000, 0.35);
}
button.dg-card { transition: all 160ms ease; }
button.dg-card:hover { border-color: #22d3ee; box-shadow: 0 0 0 1px #22d3ee, 0 10px 36px alpha(#22d3ee, 0.28); }
button.dg-card:active { opacity: 0.85; }

.dg-chip { font-family: monospace; font-size: 8pt; font-weight: 700; padding: 2px 9px;
           border-radius: 99px; background: alpha(currentColor, 0.10); }
.dg-chip.good { color: #10b981; background: alpha(#10b981, 0.16); }
.dg-chip.bad  { color: #f43f5e; background: alpha(#f43f5e, 0.18); }
.dg-chip.hot  { color: #f59e0b; background: alpha(#f59e0b, 0.18); }

progressbar trough, progressbar progress { min-height: 10px; border-radius: 99px; }
progressbar trough { background: alpha(currentColor, 0.12); }
progressbar.dg-ok   progress { background-image: linear-gradient(90deg, #22d3ee, #8b5cf6); }
progressbar.dg-warn progress { background-image: linear-gradient(90deg, #fbbf24, #f97316); }
progressbar.dg-crit progress { background-image: linear-gradient(90deg, #fb7185, #e11d48); }
progressbar.mini trough, progressbar.mini progress { min-height: 6px; }

list.dg-list { background: transparent; }
list.dg-list row { background: alpha(currentColor, 0.045); border-radius: 12px; margin-bottom: 6px;
                   padding: 8px 12px; transition: all 120ms ease; }
list.dg-list row:hover { background: alpha(#22d3ee, 0.16); }
"""


class DriveCard(Gtk.Button):
    def __init__(self, on_open, cfg):
        super().__init__(css_classes=["dg-card"])
        self.cfg, self.drive = cfg, None
        self.connect("clicked", lambda *_: on_open(self.drive))
        row = Gtk.Box(spacing=20)
        self.ring = Ring(124, cfg["warn"], cfg["crit"])
        ov = Gtk.Overlay(child=self.ring)
        self.pct = Gtk.Label(css_classes=["dg-pct"], halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        ov.add_overlay(self.pct)
        row.append(ov)

        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7, hexpand=True,
                      valign=Gtk.Align.CENTER)
        head = Gtk.Box(spacing=9)
        self.icon = Gtk.Image(pixel_size=22)
        self.name = Gtk.Label(css_classes=["dg-name"], xalign=0, ellipsize=3)
        head.append(self.icon)
        head.append(self.name)
        self.chips = Gtk.Box(spacing=6)
        self.sub = Gtk.Label(css_classes=["dg-mono", "dg-dim", "dg-small"], xalign=0, ellipsize=3)
        self.bar = Gtk.ProgressBar()
        self.stats = Gtk.Label(css_classes=["dg-mono"], xalign=0)
        for w in (head, self.sub, self.bar, self.stats, self.chips):
            col.append(w)
        row.append(col)
        row.append(Gtk.Image(icon_name="go-next-symbolic", css_classes=["dg-dim"]))
        self.set_child(row)

    def _chip(self, text, cls=None, tip=None):
        c = Gtk.Label(label=text, css_classes=["dg-chip"] + ([cls] if cls else []))
        if tip:
            c.set_tooltip_text(tip)
        self.chips.append(c)

    def update(self, d):
        self.drive = d
        css, _, _ = level(d.percent, self.cfg["warn"], self.cfg["crit"])
        for c in ("dg-ok", "dg-warn", "dg-crit"):
            self.bar.remove_css_class(c)
        self.bar.add_css_class(css)
        self.bar.set_fraction(d.percent / 100)
        self.ring.warn, self.ring.crit = self.cfg["warn"], self.cfg["crit"]
        self.ring.set_percent(d.percent)
        self.pct.set_text(f"{d.percent:.0f}%")
        self.icon.set_from_icon_name({
            "ssd": "drive-harddisk-solidstate-symbolic", "removable": "drive-removable-media-symbolic",
            "network": "folder-remote-symbolic"}.get(d.kind, "drive-harddisk-symbolic"))
        self.name.set_text(d.label)
        self.sub.set_text(f"{d.device}  →  {d.mountpoint}")
        self.stats.set_markup(
            f"<b>{drives.human(d.free)}</b> free of {drives.human(d.total)}"
            f"  <span alpha='60%'>· {drives.human(d.used)} used</span>")
        while (c := self.chips.get_first_child()):
            self.chips.remove(c)
        self._chip(f"{d.kind.upper()} · {d.fstype}")
        if d.temp is not None:
            self._chip(f"{d.temp:.0f} °C", "hot" if d.temp >= 60 else None, d.model)
        if d.health:
            tip = f"{d.model or d.disk} · powered on {d.hours:,} h" if d.hours is not None else d.model
            self._chip({"ok": "SMART OK", "warn": "SMART WARNING", "fail": "SMART FAILING"}[d.health],
                       "good" if d.health == "ok" else "bad", tip)


class DetailPage(Adw.NavigationPage):
    """Folder drill-down: treemap + ranked list, sized live by a background scan."""

    def __init__(self, win, path, title, mount_dev=None):
        super().__init__(title=title)
        self.win, self.path = win, path
        self.scan = Scan(path)
        self.built = False

        view = Adw.ToolbarView()
        view.add_top_bar(Adw.HeaderBar())
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14, margin_top=8,
                      margin_bottom=22, margin_start=20, margin_end=20)
        self.path_lbl = Gtk.Label(label=path, xalign=0, css_classes=["dg-mono", "dg-dim", "dg-small"],
                                  ellipsize=1)
        top = Gtk.Box(spacing=12)
        self.total = Gtk.Label(css_classes=["dg-hero"], xalign=0)
        self.status = Gtk.Label(css_classes=["dg-dim", "dg-small"], xalign=0, valign=Gtk.Align.END,
                                margin_bottom=10, hexpand=True)
        self.spin = Gtk.Spinner(spinning=True, valign=Gtk.Align.END, margin_bottom=10)
        top.append(self.total)
        top.append(self.spin)
        top.append(self.status)
        self.map = Treemap(self._open)
        self.list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["dg-list"])
        self.list.connect("row-activated", lambda _l, r: self._open(r.entry))
        for w in (self.path_lbl, top, self.map, self.list):
            col.append(w)
        view.set_content(Gtk.ScrolledWindow(child=Adw.Clamp(maximum_size=1000, child=col),
                                            vexpand=True))
        self.set_child(view)
        self.scan.start()
        GLib.timeout_add(350, self._flush)

    def cancel(self):
        self.scan.stop()

    def _open(self, entry):
        if entry and entry.is_dir:
            self.win.push_folder(entry.path, entry.name)

    def _flush(self):
        if self.scan.cancel.is_set():
            return False
        done = self.scan.finished.is_set()
        if self.scan.ready.is_set():
            self._render(done)
        return not done

    def _render(self, done):
        ents = sorted(self.scan.entries, key=lambda e: e.size, reverse=True)
        total = sum(e.size for e in ents)
        skipped = sum(e.skipped for e in ents)
        self.total.set_text(drives.human(total))
        self.spin.set_visible(not done)
        if self.scan.error:
            self.status.set_text(f"Can't read this folder: {self.scan.error}")
        elif done:
            msg = f"{len(ents)} items"
            if skipped:
                msg += f" · {skipped} folders unreadable (permissions)"
            self.status.set_text(msg)
        else:
            self.status.set_text("scanning…")

        shown = [e for e in ents if e.size > 0]
        items = [(e.size, e, e.name + ("/" if e.is_dir else "")) for e in shown[:36]]
        rest = shown[36:]
        if rest:
            items.append((sum(e.size for e in rest), None, f"{len(rest)} smaller items"))
        self.map.set_items(items)

        while (r := self.list.get_first_child()):
            self.list.remove(r)
        for e in ents[:120]:
            row = Gtk.ListBoxRow(activatable=e.is_dir)
            row.entry = e
            box = Gtk.Box(spacing=12)
            box.append(Gtk.Image(icon_name="folder-symbolic" if e.is_dir else "text-x-generic-symbolic",
                                 css_classes=["dg-dim"]))
            nm = Gtk.Label(label=e.name + ("  …" if not e.done else ""), xalign=0, hexpand=True,
                           ellipsize=3)
            bar = Gtk.ProgressBar(fraction=(e.size / total) if total else 0, css_classes=["mini", "dg-ok"],
                                  valign=Gtk.Align.CENTER, width_request=140)
            sz = Gtk.Label(label=drives.human(e.size), css_classes=["dg-mono"], xalign=1, width_chars=9)
            for w in (nm, bar, sz):
                box.append(w)
            box.append(Gtk.Image(icon_name="go-next-symbolic" if e.is_dir else "",
                                 css_classes=["dg-dim"], width_request=16))
            row.set_child(box)
            self.list.append(row)


class Window(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="DiskGlance", default_width=820, default_height=720)
        self.cfg = app.cfg
        self.app = app
        self.cards: dict[str, DriveCard] = {}
        self.add_css_class("dg-win")

        self.nav = Adw.NavigationView()
        self.nav.connect("popped", lambda _n, page: page.cancel() if hasattr(page, "cancel") else None)
        self.connect("close-request", self._on_close)

        view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        brand = Gtk.Box(spacing=8)
        brand.append(Gtk.Image(icon_name=APP_ID, pixel_size=22))
        brand.append(Gtk.Label(use_markup=True, label="<b>Disk</b>Glance", css_classes=["dg-brand"]))
        header.set_title_widget(brand)
        refresh = Gtk.Button(icon_name="view-refresh-symbolic", tooltip_text="Rescan now (F5)")
        refresh.connect("clicked", lambda *_: self.refresh())
        header.pack_start(refresh)
        header.pack_end(self._menu())
        view.add_top_bar(header)

        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16, margin_top=6,
                      margin_bottom=22, margin_start=20, margin_end=20)
        self.banner = self._banner()
        self.list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.empty = Adw.StatusPage(icon_name="drive-harddisk-symbolic", title="No drives found",
                                    visible=False)
        for w in (self.banner, self.list, self.empty):
            col.append(w)
        view.set_content(Gtk.ScrolledWindow(child=Adw.Clamp(maximum_size=900, child=col), vexpand=True))
        self.nav.add(Adw.NavigationPage(title="DiskGlance", child=view))
        self.set_content(self.nav)

        key = Gtk.ShortcutController()
        key.add_shortcut(Gtk.Shortcut.new(Gtk.ShortcutTrigger.parse_string("F5"),
                                          Gtk.CallbackAction.new(lambda *_: self.refresh() or True)))
        self.add_controller(key)

        self.refresh()
        GLib.timeout_add_seconds(REFRESH_SECONDS, lambda: self.refresh() or True)

    # -- header menu -------------------------------------------------
    def _menu(self):
        pop = Gtk.Popover()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin_top=12,
                      margin_bottom=12, margin_start=14, margin_end=14)
        box.append(Gtk.Label(label="Theme", xalign=0, css_classes=["heading"]))
        first = None
        for key, label in (("dark", "Dark"), ("light", "Light"), ("system", "Follow system")):
            cb = Gtk.CheckButton(label=label, group=first, active=self.cfg["theme"] == key)
            first = first or cb
            cb.connect("toggled", lambda b, k=key: b.get_active() and self._set("theme", k))
            box.append(cb)
        box.append(Gtk.Separator())
        for key, label in (("notify", "Notify when a drive is nearly full"),
                           ("show_system", "Show system / snap mounts")):
            row = Gtk.Box(spacing=18)
            row.append(Gtk.Label(label=label, xalign=0, hexpand=True))
            sw = Gtk.Switch(active=self.cfg[key], valign=Gtk.Align.CENTER)
            sw.connect("notify::active", lambda s, _p, k=key: self._set(k, s.get_active()))
            row.append(sw)
            box.append(row)
        box.append(Gtk.Separator())
        about = Gtk.Button(label="About DiskGlance", css_classes=["flat"])
        about.connect("clicked", lambda *_: (pop.popdown(), self._about()))
        box.append(about)
        pop.set_child(box)
        return Gtk.MenuButton(icon_name="open-menu-symbolic", popover=pop, tooltip_text="Menu")

    def _set(self, key, value):
        self.cfg[key] = value
        config.save(self.cfg)
        if key == "theme":
            self.app.apply_theme()
        else:
            self.refresh()

    def _about(self):
        a = Adw.AboutDialog(application_name="DiskGlance", application_icon=APP_ID,
                            version=__version__, developer_name="DiskGlance contributors",
                            license_type=Gtk.License.MIT_X11,
                            website="https://github.com/rickbme/diskglance",
                            comments="See your disks at a glance.")
        a.present(self)

    # -- main view ---------------------------------------------------
    def _banner(self):
        b = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, css_classes=["dg-banner"])
        row = Gtk.Box(spacing=14)
        self.b_free = Gtk.Label(css_classes=["dg-hero"], xalign=0)
        self.b_text = Gtk.Label(css_classes=["dg-dim"], xalign=0, valign=Gtk.Align.END,
                                margin_bottom=10, hexpand=True, wrap=True)
        row.append(self.b_free)
        row.append(self.b_text)
        self.b_bar = Gtk.ProgressBar()
        b.append(row)
        b.append(self.b_bar)
        return b

    def refresh(self):
        found = drives.scan(self.cfg["show_system"])
        keys = {d.device + d.mountpoint for d in found}
        for k in list(self.cards):
            if k not in keys:
                self.list.remove(self.cards.pop(k))
        for d in found:
            k = d.device + d.mountpoint
            if k not in self.cards:
                self.cards[k] = DriveCard(self.open_drive, self.cfg)
                self.list.append(self.cards[k])
            self.cards[k].update(d)
        real = [d for d in found if not d.is_snap]
        tot, free = sum(d.total for d in real), sum(d.free for d in real)
        self.b_free.set_text(drives.human(free))
        self.b_text.set_text(f"free across {len(real)} drive{'s' if len(real) != 1 else ''} · "
                             f"{drives.human(tot)} total")
        pct = (tot - free) / tot * 100 if tot else 0
        css, _, _ = level(pct, self.cfg["warn"], self.cfg["crit"])
        for c in ("dg-ok", "dg-warn", "dg-crit"):
            self.b_bar.remove_css_class(c)
        self.b_bar.add_css_class(css)
        self.b_bar.set_fraction(pct / 100)
        self.empty.set_visible(not found)
        self.app.check_alerts(found)

    def open_drive(self, d):
        self.push_folder(d.mountpoint, d.label)

    def push_folder(self, path, title):
        self.nav.push(DetailPage(self, path, title))

    def _on_close(self, *_):
        page = self.nav.get_visible_page()
        for p in self.nav.get_navigation_stack():
            if hasattr(p, "cancel"):
                p.cancel()
        return False


class App(Adw.Application):
    def __init__(self, opts):
        super().__init__(application_id=APP_ID)
        self.opts = opts
        self.cfg = config.load()
        self.alerted: set[str] = set()

    def apply_theme(self):
        sm = Adw.StyleManager.get_default()
        sm.set_color_scheme({"dark": Adw.ColorScheme.FORCE_DARK, "light": Adw.ColorScheme.FORCE_LIGHT}
                            .get(self.cfg["theme"], Adw.ColorScheme.DEFAULT))

    def _sync_dark(self, *_):
        for w in self.get_windows():
            (w.add_css_class if Adw.StyleManager.get_default().get_dark() else w.remove_css_class)("dg-dark")

    def check_alerts(self, found):
        if not self.cfg["notify"]:
            return
        for d in found:
            key = d.device + d.mountpoint
            if d.is_snap:
                continue
            if d.percent >= self.cfg["crit"] and key not in self.alerted:
                self.alerted.add(key)
                n = Gio.Notification.new(f"{d.label} is almost full")
                n.set_body(f"{drives.human(d.free)} free of {drives.human(d.total)} "
                           f"({d.percent:.0f}% used) on {d.mountpoint}")
                n.set_priority(Gio.NotificationPriority.HIGH)
                n.set_default_action("app.focus")
                self.send_notification(f"full-{key}", n)
            elif d.percent < self.cfg["crit"] - 2:
                self.alerted.discard(key)

    def do_startup(self):
        Adw.Application.do_startup(self)
        act = Gio.SimpleAction.new("focus", None)
        act.connect("activate", lambda *_: self.props.active_window and self.props.active_window.present())
        self.add_action(act)
        prov = Gtk.CssProvider()
        prov.load_from_string(CSS)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), prov,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        icons = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "icons")
        Gtk.IconTheme.get_for_display(Gdk.Display.get_default()).add_search_path(icons)
        Gtk.Window.set_default_icon_name(APP_ID)
        self.apply_theme()
        Adw.StyleManager.get_default().connect("notify::dark", self._sync_dark)

    def do_activate(self):
        win = self.props.active_window or Window(self)
        win.present()
        self._sync_dark()
        o = self.opts
        if o.get("open"):
            p = os.path.abspath(o["open"])
            win.push_folder(p, os.path.basename(p) or p)
        if o.get("shot"):
            GLib.timeout_add(int(float(o.get("delay", 2.5)) * 1000), self._shot, win)

    def _shot(self, win):
        paint = Gtk.WidgetPaintable.new(win)
        snap = Gtk.Snapshot()
        paint.snapshot(snap, win.get_width(), win.get_height())
        tex = win.get_native().get_renderer().render_texture(snap.to_node(), None)
        tex.save_to_png(self.opts["shot"])
        self.quit()
        return False


def main():
    argv, opts, i = sys.argv[1:], {}, 0
    while i < len(argv):
        a = argv[i]
        if a in ("--shot", "--open", "--delay") and i + 1 < len(argv):
            opts[a[2:]] = argv[i + 1]
            i += 2
        elif a in ("-h", "--help"):
            print("usage: diskglance [FOLDER]\n  FOLDER      open straight into a folder analysis")
            return 0
        elif not a.startswith("-"):
            opts["open"] = a
            i += 1
        else:
            i += 1
    return App(opts).run([sys.argv[0]])
