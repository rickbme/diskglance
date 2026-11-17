# DiskGlance

At-a-glance disk usage for Linux. A GTK4 / libadwaita window that scans mounted
drives and shows used vs. free space as a ring chart plus a bar per drive.

- Blue under 80% full, amber from 80%, red from 90%
- Auto-refreshes every 5 s; refresh button for an instant rescan
- Hides snap/system mounts by default (toggle in the header bar)

## Run
    ./diskglance.py

Needs system Python with `python3-gi` and `gir1.2-adw-1` (already on Ubuntu GNOME).
