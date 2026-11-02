"""Things that outlive one stream: the depth record and the clip log.

Both swallow disk errors on purpose. A full disk or a locked file should cost
a saved number, never a running stream.
"""
import csv
import json
import os
import time


class DepthRecord:
    def __init__(self, path):
        self.path = path
        self.best = self._load()
        # The number this stream is trying to beat. Zero means there is no
        # record yet, so the first block of a first-ever run is not news.
        self._to_beat = self.best
        self._announced = False

    def _load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return int(json.load(f)["depth"])
        except (OSError, ValueError, KeyError, TypeError) as e:
            if not isinstance(e, FileNotFoundError):
                print(f"Ignoring unreadable record file: {e}")
            return 0

    def update(self, depth):
        """Track the deepest point. True once, on the frame the record falls."""
        self.best = max(self.best, depth)
        if self._to_beat and not self._announced and depth > self._to_beat:
            self._announced = True
            return True
        return False

    def save(self):
        # Written to a temp file first, so a crash mid-write cannot corrupt
        # the record it was meant to protect.
        temp = f"{self.path}.tmp"
        try:
            with open(temp, "w", encoding="utf-8") as f:
                json.dump({"depth": self.best}, f)
            os.replace(temp, self.path)
        except OSError as e:
            print(f"Could not save record: {e}")


class ClipLog:
    """A timestamped list of moments worth cutting into Shorts."""

    def __init__(self, path, clock=time.time):
        self.path = path
        self.clock = clock
        self.started_at = clock()

    def log(self, kind, detail=""):
        now = self.clock()
        elapsed = int(now - self.started_at)
        session_time = f"{elapsed // 3600:02}:{elapsed % 3600 // 60:02}:{elapsed % 60:02}"
        local_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now))
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            is_new = not os.path.exists(self.path)
            with open(self.path, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if is_new:
                    writer.writerow(["local_time", "session_time", "kind", "detail"])
                writer.writerow([local_time, session_time, kind, detail])
        except OSError as e:
            print(f"Could not write clip log: {e}")
