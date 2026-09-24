"""Minimal progress reporting on stderr (no tqdm).

On a terminal: a redrawn bar. Otherwise (e.g. when Claude runs sem): at most
one line per quarter, so logs stay short. SEM_QUIET=1 silences it.
"""

from __future__ import annotations

import os
import sys
import time


class Progress:
    def __init__(self, total: int, label: str):
        self.total = max(total, 1)
        self.label = label
        self.n = 0
        self.t0 = time.time()
        self.quiet = os.environ.get("SEM_QUIET") == "1"
        self.tty = sys.stderr.isatty()
        self._last_quarter = 0
        self._last_draw = 0.0

    def update(self, k: int = 1) -> None:
        self.n += k
        if self.quiet:
            return
        if self.tty:
            now = time.time()
            if now - self._last_draw > 0.1 or self.n >= self.total:
                self._last_draw = now
                frac = min(self.n / self.total, 1.0)
                bar = "#" * int(frac * 30)
                sys.stderr.write(f"\r{self.label} [{bar:<30}] {self.n}/{self.total} {now - self.t0:5.1f}s")
                sys.stderr.flush()
        else:
            q = int(4 * self.n / self.total)
            # only report on long-running work, so short runs stay quiet in logs
            if q > self._last_quarter and q < 4 and self.total >= 100 and time.time() - self.t0 > 5:
                self._last_quarter = q
                print(f"{self.label}: {self.n}/{self.total}", file=sys.stderr, flush=True)

    def close(self) -> None:
        if self.quiet:
            return
        if self.tty:
            sys.stderr.write("\n")
        sys.stderr.flush()
