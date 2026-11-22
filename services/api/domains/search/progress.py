"""Sanitized, timestamped progress reporting for management commands."""

import logging
import sys
import time
from datetime import UTC, datetime
from pathlib import Path


class ProgressReporter:
    def __init__(self, phase, total, every=25, log_file=None):
        if every < 1:
            raise ValueError("progress interval must be positive")
        self.phase = phase
        self.total = total
        self.every = every
        self.started_at = None
        self.logger = logging.getLogger("datasoft.progress")
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stderr)
            handler.setFormatter(logging.Formatter("%(message)s"))
            self.logger.addHandler(handler)
        if log_file:
            path = Path(log_file)
            path.parent.mkdir(parents=True, exist_ok=True)
            self.file = path.open("a", encoding="utf-8")
        else:
            self.file = None

    def _log(self, message):
        line = f"{datetime.now(UTC).isoformat()} {message}"
        self.logger.info(line)
        if self.file:
            self.file.write(f"{line}\n")
            self.file.flush()

    def warning(self, message):
        line = f"{datetime.now(UTC).isoformat()} {message}"
        self.logger.warning(line)
        if self.file:
            self.file.write(f"{line}\n")
            self.file.flush()

    def start(self):
        self.started_at = time.perf_counter()
        self._log(f"{self.phase} started total={self.total}")

    def item(self, done):
        if done % self.every and done != self.total:
            return
        elapsed = max(time.perf_counter() - self.started_at, 0.001)
        rate = done / elapsed
        remaining = max(self.total - done, 0)
        eta = remaining / rate if rate else 0
        self._log(f"{self.phase} {done}/{self.total} rate={rate:.2f}/s eta={eta:.1f}s")

    def finish(self):
        elapsed = max(time.perf_counter() - self.started_at, 0)
        self._log(f"{self.phase} finished elapsed={elapsed:.2f}s")
        if self.file:
            self.file.close()
