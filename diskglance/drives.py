"""Discover mounted drives and their space usage (no GUI imports)."""
import json
import os
import subprocess
from dataclasses import dataclass

from . import hw

IN_FLATPAK = os.path.exists("/.flatpak-info")
# Inside a Flatpak sandbox the host root drive only appears as bind mounts of these:
SANDBOX_ROOT_MARKERS = ("/usr", "/app")

# Pseudo / virtual filesystems that are never "drives".
PSEUDO_FS = {
    "proc", "sysfs", "devtmpfs", "devpts", "tmpfs", "cgroup", "cgroup2",
    "securityfs", "debugfs", "tracefs", "configfs", "fusectl", "pstore",
    "bpf", "autofs", "mqueue", "hugetlbfs", "binfmt_misc", "efivarfs",
    "ramfs", "overlay", "nsfs", "rpc_pipefs", "fuse.portal", "fuse.gvfsd-fuse",
    "fuse.gvfs-fuse-daemon",
}


@dataclass
class Drive:
    device: str
    mountpoint: str
    fstype: str
    label: str
    total: int
    used: int
    free: int          # available to the user
    kind: str          # "ssd" | "hdd" | "removable" | "network" | "other"
    is_snap: bool = False
    disk: str | None = None      # parent physical disk, e.g. nvme0n1
    model: str | None = None
    temp: float | None = None    # °C
    health: str | None = None    # ok | warn | fail
    hours: int | None = None     # power-on hours
    host_root: bool = False      # Flatpak only: the host's / (partly visible)

    @property
    def percent(self) -> float:
        return (self.used / self.total * 100) if self.total else 0.0


def _unescape(s: str) -> str:
    return s.replace("\\040", " ").replace("\\011", "\t").replace("\\134", "\\")


def _lsblk() -> dict:
    """Map device path -> {label, rota, rm, model} using lsblk."""
    try:
        out = subprocess.run(
            ["lsblk", "-J", "-o", "PATH,LABEL,ROTA,RM,MODEL,PKNAME"],
            capture_output=True, text=True, timeout=5, check=True,
        ).stdout
        rows = json.loads(out)["blockdevices"]
    except Exception:
        return {}
    info = {r["path"]: r for r in rows}
    # inherit ROTA/RM/MODEL from parent disk for partitions
    for r in rows:
        parent = info.get("/dev/" + r["pkname"]) if r.get("pkname") else None
        if parent:
            for k in ("rota", "rm", "model"):
                if r.get(k) in (None, "") and parent.get(k) is not None:
                    r[k] = parent[k]
    return info


def _truthy(v) -> bool:
    return v in (True, 1, "1", "true")


def scan(include_system: bool = False) -> list[Drive]:
    blk = _lsblk()
    drives = []
    try:
        lines = open("/proc/self/mounts").read().splitlines()
    except OSError:
        return []
    # group every mount by device first (bind mounts / sandbox mounts share a device)
    groups: dict[str, list[tuple[str, str]]] = {}
    for line in lines:
        parts = line.split()
        if len(parts) < 3 or parts[2] in PSEUDO_FS:
            continue
        groups.setdefault(parts[0], []).append((_unescape(parts[1]), parts[2]))

    for dev, mounts in groups.items():
        fs = mounts[0][1]
        is_net = fs in ("nfs", "nfs4", "cifs", "smb3", "sshfs", "fuse.sshfs")
        if not (dev.startswith("/dev/") or is_net):
            continue
        host_root = IN_FLATPAK and any(m in SANDBOX_ROOT_MARKERS for m, _ in mounts)
        if host_root:
            mnt = next(m for m, _ in mounts if m in SANDBOX_ROOT_MARKERS)   # statvfs works here
            shown = "/"
        else:
            mnt = shown = mounts[0][0]
        is_snap = mnt.startswith("/snap/") or fs == "squashfs"
        if is_snap and not include_system:
            continue
        if not include_system and not host_root and mnt.startswith(("/boot/efi", "/var/snap", "/run/")) \
                and not mnt.startswith(("/run/media", "/run/user")):
            continue
        try:
            st = os.statvfs(mnt)
        except OSError:
            continue
        total = st.f_blocks * st.f_frsize
        if total == 0:
            continue
        free = st.f_bavail * st.f_frsize
        used = total - st.f_bfree * st.f_frsize
        b = blk.get(dev, {})
        if is_net:
            kind = "network"
        elif _truthy(b.get("rm")) or shown.startswith(("/media", "/run/media")):
            kind = "removable"
        elif b.get("rota") is not None:
            kind = "hdd" if _truthy(b.get("rota")) else "ssd"
        else:
            kind = "other"
        label = b.get("label") or ("Root" if shown == "/" else os.path.basename(shown) or shown)
        disk = (b.get("pkname") or os.path.basename(dev)) if dev.startswith("/dev/") else None
        info = hw.disk_info(disk) if kind != "network" else {}
        drives.append(Drive(dev, shown, fs, label, total, used, free, kind, is_snap, disk,
                            info.get("model"), info.get("temp"), info.get("health"),
                            info.get("hours"), host_root))
    drives.sort(key=lambda d: (d.mountpoint != "/", d.mountpoint))
    return drives


def human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB", "PB"):
        if abs(n) < 1000 or unit == "PB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1000
