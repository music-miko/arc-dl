# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


import time


class UptimeTracker:
    def __init__(self):
        self.start_time = time.time()

    def elapsed_str(self) -> str:
        elapsed = int(time.time() - self.start_time)
        d, rem = divmod(elapsed, 86400)
        h, rem = divmod(rem, 3600)
        m, s = divmod(rem, 60)
        parts = [f"{d}d" for _ in [1] if d] + [f"{h}h" for _ in [1] if h] + [f"{m}m" for _ in [1] if m]
        parts.append(f"{s}s")
        return "".join(parts)


uptime = UptimeTracker()
