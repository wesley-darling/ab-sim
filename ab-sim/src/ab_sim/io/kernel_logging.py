# io/kernel_loggingpy
import logging, json, sys
from typing import Any
from ab_sim.sim.hooks import KernelHooks

log = logging.getLogger("kernel")


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {"level": record.levelname, "msg": record.getMessage(), "logger": record.name}
        extra = getattr(record, "extra", None)
        if isinstance(extra, dict):
            payload.update(extra)
        return json.dumps(payload)


class KernelLogging(KernelHooks):
    def __init__(
        self,
        run_id: str = "local",
        level: str = "INFO",
        debug: bool = False,
        sample_every: int = 1000,
    ):
        self.run_id, self.debug, self.sample_every = run_id, debug, max(1, sample_every)
        h = logging.StreamHandler(sys.stdout)
        h.setFormatter(_JsonFormatter())
        root = logging.getLogger()
        root.handlers[:] = [h]
        root.setLevel(getattr(logging, level.upper(), logging.INFO))
        self._log = logging.getLogger("kernel")

    def _emit(self, lvl: str, msg: str, **extra):
        if lvl == "DEBUG" and not self.debug:
            return
        getattr(self._log, lvl.lower())(msg, extra={"extra": {"run_id": self.run_id, **extra}})

    def run_start(self, **kw):
        self._emit("INFO", "run_start", **kw)

    def run_end(self, **kw):
        self._emit("INFO", "run_end", **kw)

    def schedule(self, ev, **kw):
        if self.debug and (kw.get("qsize", 0) % self.sample_every) == 0:
            self._emit(
                "DEBUG",
                "schedule",
                etype=type(ev).__name__,
                event_id=getattr(ev, "_eid", None),
                **kw,
            )

    def dispatch_start(self, ev, **kw):
        if self.debug and (kw.get("seq", 0) % self.sample_every) == 0:
            self._emit(
                "DEBUG",
                "dispatch",
                etype=type(ev).__name__,
                event_id=getattr(ev, "_eid", None),
                **kw,
            )

    def dispatch_end(self, ev, **kw):
        if self.debug and (kw.get("qsize", 0) % self.sample_every) == 0:
            self._emit(
                "DEBUG",
                "dispatch_done",
                etype=type(ev).__name__,
                event_id=getattr(ev, "_eid", None),
                **kw,
            )

    def error(self, ev, **kw):
        self._emit(
            "ERROR",
            "kernel_error",
            etype=type(ev).__name__,
            event_id=getattr(ev, "_eid", None),
            **kw,
        )
