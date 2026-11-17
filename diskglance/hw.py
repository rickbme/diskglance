"""Hardware info for a physical disk: temperature + SMART health, no root needed.

Temperature comes from sysfs hwmon; health from UDisks2 over D-Bus (which keeps a
cached SMART snapshot that unprivileged users may read).
"""
import glob
import time

try:
    from gi.repository import Gio, GLib
except Exception:  # pragma: no cover - GUI-less environments
    Gio = GLib = None

_TTL = 30
_cache: dict[str, tuple[float, dict]] = {}
_bus = None


def _hwmon_temp(disk: str):
    for pat in (f"/sys/block/{disk}/device/hwmon*/temp1_input",
                f"/sys/block/{disk}/device/device/hwmon*/temp1_input"):
        for p in glob.glob(pat):
            try:
                return int(open(p).read()) / 1000
            except (OSError, ValueError):
                pass
    return None


def _props(path: str, iface: str) -> dict:
    global _bus
    if _bus is None:
        _bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    r = _bus.call_sync(
        "org.freedesktop.UDisks2", path, "org.freedesktop.DBus.Properties", "GetAll",
        GLib.Variant("(s)", (iface,)), GLib.VariantType("(a{sv})"),
        Gio.DBusCallFlags.NONE, 500, None)
    return r.unpack()[0]


def _udisks(disk: str) -> dict:
    out = {}
    try:
        blk = _props(f"/org/freedesktop/UDisks2/block_devices/{disk}",
                     "org.freedesktop.UDisks2.Block")
        drive = blk["Drive"]
        d = _props(drive, "org.freedesktop.UDisks2.Drive")
        out["model"] = (d.get("Vendor", "") + " " + d.get("Model", "")).strip()
        for iface in ("org.freedesktop.UDisks2.NVMe.Controller", "org.freedesktop.UDisks2.Drive.Ata"):
            try:
                p = _props(drive, iface)
            except Exception:
                continue
            if not p.get("SmartUpdated"):
                continue
            if "SmartCriticalWarning" in p:  # NVMe
                out["health"] = "warn" if p["SmartCriticalWarning"] else "ok"
                out["hours"] = p.get("SmartPowerOnHours")
            else:  # ATA
                out["health"] = "fail" if p.get("SmartFailing") else "ok"
                out["hours"] = (p.get("SmartPowerOnSeconds") or 0) // 3600
            t = p.get("SmartTemperature")
            if t:
                out["temp_udisks"] = t - 273.15
    except Exception:
        pass
    return out


def disk_info(disk: str | None) -> dict:
    """{'temp': °C|None, 'health': 'ok'|'warn'|'fail'|None, 'hours': int|None, 'model': str|None}"""
    if not disk or Gio is None:
        return {}
    now = time.time()
    hit = _cache.get(disk)
    if hit and now - hit[0] < _TTL:
        return hit[1]
    u = _udisks(disk)
    temp = _hwmon_temp(disk)
    if temp is None:
        temp = u.get("temp_udisks")
    info = {"temp": temp, "health": u.get("health"), "hours": u.get("hours"),
            "model": u.get("model")}
    _cache[disk] = (now, info)
    return info
