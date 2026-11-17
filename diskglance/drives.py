"""Discover mounted drives and their space usage (no GUI imports)."""
import json
import os
import subprocess
from dataclasses import dataclass

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
    drives, seen = [], set()
    try:
        lines = open("/proc/self/mounts").read().splitlines()
    except OSError:
        return []
    for line in lines:
        parts = line.split()
        if len(parts) < 3:
            continue
        dev, mnt, fs = parts[0], _unescape(parts[1]), parts[2]
        if fs in PSEUDO_FS:
            continue
        is_snap = mnt.startswith("/snap/") or fs == "squashfs"
        is_net = fs in ("nfs", "nfs4", "cifs", "smb3", "sshfs", "fuse.sshfs")
        if not (dev.startswith("/dev/") or is_net):
            continue
        if is_snap and not include_system:
            continue
        if not include_system and mnt.startswith(("/boot/efi", "/var/snap", "/run/")) \
                and not mnt.startswith(("/run/media", "/run/user")):
            continue
        if dev in seen:  # bind mounts / btrfs subvolumes
            continue
        seen.add(dev)
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
        elif _truthy(b.get("rm")) or mnt.startswith(("/media", "/run/media")):
            kind = "removable"
        elif b.get("rota") is not None:
            kind = "hdd" if _truthy(b.get("rota")) else "ssd"
        else:
            kind = "other"
        label = b.get("label") or ("Root" if mnt == "/" else os.path.basename(mnt) or mnt)
        drives.append(Drive(dev, mnt, fs, label, total, used, free, kind, is_snap))
    drives.sort(key=lambda d: (d.mountpoint != "/", d.mountpoint))
    return drives


def human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB", "PB"):
        if abs(n) < 1000 or unit == "PB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1000
