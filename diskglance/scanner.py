"""Threaded folder-size scanner (like `du`, one filesystem only, no GUI imports)."""
import os
import queue
import stat
import threading
from dataclasses import dataclass


@dataclass
class Entry:
    name: str
    path: str
    is_dir: bool
    size: int = 0          # bytes on disk (allocated blocks); grows while scanning
    done: bool = True
    skipped: int = 0       # unreadable directories inside


def dir_size(path: str, dev: int, cancel: threading.Event, entry: Entry | None = None) -> int:
    total, stack, seen = 0, [path], set()
    while stack and not cancel.is_set():
        d = stack.pop()
        try:
            it = os.scandir(d)
        except OSError:
            if entry:
                entry.skipped += 1
            continue
        with it:
            for e in it:
                try:
                    st = e.stat(follow_symlinks=False)
                except OSError:
                    continue
                if stat.S_ISDIR(st.st_mode):
                    if st.st_dev == dev:       # never cross into other mounts
                        stack.append(e.path)
                    continue
                if st.st_nlink > 1:            # count hard links once
                    key = (st.st_dev, st.st_ino)
                    if key in seen:
                        continue
                    seen.add(key)
                total += st.st_blocks * 512
                if entry:
                    entry.size = total
    return total


class Scan:
    """Lists `path`, sizes each sub-folder in parallel. Poll `.entries`/`.finished`."""

    def __init__(self, path: str, workers: int = 6):
        self.path, self.workers = path, workers
        self.cancel = threading.Event()
        self.ready = threading.Event()      # initial listing available
        self.finished = threading.Event()
        self.entries: list[Entry] = []
        self.error: str | None = None

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self):
        self.cancel.set()

    def _run(self):
        try:
            dev = os.stat(self.path).st_dev
            dirs = []
            with os.scandir(self.path) as it:
                for e in it:
                    try:
                        st = e.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    if stat.S_ISDIR(st.st_mode):
                        if st.st_dev != dev:
                            continue
                        ent = Entry(e.name, e.path, True, 0, done=False)
                        dirs.append(ent)
                    else:
                        ent = Entry(e.name, e.path, False, st.st_blocks * 512)
                    self.entries.append(ent)
        except OSError as ex:
            self.error = ex.strerror or str(ex)
            dirs = []
        self.ready.set()

        q: queue.Queue = queue.Queue()
        for d in dirs:
            q.put(d)

        def worker():
            while not self.cancel.is_set():
                try:
                    ent = q.get_nowait()
                except queue.Empty:
                    return
                ent.size = dir_size(ent.path, dev, self.cancel, ent)
                ent.done = True

        ts = [threading.Thread(target=worker, daemon=True) for _ in range(self.workers)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        self.finished.set()
