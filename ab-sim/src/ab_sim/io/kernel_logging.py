# io/kernel_loggingpy
import json
import logging
import sys
from dataclasses import asdict, is_dataclass

from ab_sim.io.recorder import Recorder
from ab_sim.sim.hooks import NoopHooks


def _default_json_logger(name="ab_sim", level="INFO"):
    logger = logging.getLogger(name)
    if not logger.handlers:
        h = logging.StreamHandler(sys.stdout)

        class _JsonFormatter(logging.Formatter):
            def format(self, record: logging.LogRecord) -> str:
                payload = {
                    "level": record.levelname,
                    "msg": record.getMessage(),
                    "logger": record.name,
                }
                extra = getattr(record, "extra", None)
                if isinstance(extra, dict):
                    payload.update(extra)
                return json.dumps(payload)

        h.setFormatter(_JsonFormatter())
        logger.addHandler(h)
        logger.setLevel(level)
    return logger


class KernelLogging(NoopHooks):
    """
    One place to shape and emit structured logs for both engine and business events.
    """

    BUSINESS = {
        "RiderRequestPlaced",
        "TripAssigned",
        "RiderCancel",
        "DriverCancel",
        "DriverAvailable",
        "RiderRequeue",
        "BoardingStarted",
        "BoardingComplete",
        "TripBoarded",
        "DriverLegArrive",
        "AlightingStarted",
        "AlightingComplete",
        "TripCompleted",
    }

    def __init__(
        self,
        run_id: str = "local",
        clock=None,
        level: str = "INFO",
        debug: bool = False,
        sample_every: int = 1000,
        logger: logging.Logger | None = None,
        recorder: Recorder | None = None,
    ):
        self.run_id, self.clock, self.debug, self.sample_every = (
            run_id,
            clock,
            debug,
            max(1, sample_every),
        )
        self.recorder = recorder
        self.log = logger or _default_json_logger(level=level)
        self._processed = 0

    # --------------- Helpers -----------------------------

    def _emit(self, level: str, msg: str, **extra):
        wall = self.clock.to_wall(extra.get("t")) if (self.clock and "t" in extra) else None
        payload = {"run_id": self.run_id}
        if wall:
            payload["wall"] = wall.isoformat()
        self.log.log(getattr(logging, level), msg, extra={"extra": {**payload, **extra}})

    def _shape_event(self, ev, want_name: bool = False):
        # Normalize a few common fields to keep logs compact & consistent
        name = type(ev).__name__
        base = {"t": getattr(ev, "t", None)}
        for f in ("rider_id", "driver_id", "task_id", "kind", "reason"):
            if hasattr(ev, f):
                base[f] = getattr(ev, f)
        # For DriverLegArrive, keep only essential fields
        # For anything else, optionally attach dataclass payload (careful with size)
        if is_dataclass(ev):
            # add any custom fields you defined on that event
            evd = asdict(ev)
            # remove already copied keys to avoid duplication
            for k in list(base.keys()) + ["t"]:
                evd.pop(k, None)
            # include only if small
            if evd:
                base["data"] = evd
        return (name, base) if want_name else base

    # --------------------------------------------------------

    # engine lifecycle

    def run_start(self, *, until: float, max_events: int | None, qsize: int | None):
        self._emit("INFO", "run_start", until=until, max_events=max_events, qsize=qsize)

    def run_end(self, *, processed: int, **extra):
        self._emit("INFO", "run_end", processed=processed, **extra)

    def schedule(self, ev, *, now: float, qsize: int):
        if self.debug and (qsize % self.sample_every) == 0:
            self._emit("DEBUG", "schedule", **self._shape_event(ev), now=now, qsize=qsize)

    def dispatch_start(self, ev, *, seq: int, qsize: int, handlers: int):
        self._processed += 1
        name, extra = self._shape_event(ev, want_name=True)
        level = "INFO" if name in self.BUSINESS else ("DEBUG" if self.debug else None)
        if level:
            self._emit(level, name, **extra, seq=seq, qsize=qsize, handlers=handlers)

    def dispatch_end(self, ev, *, produced: int, qsize: int, **extra):
        if self.debug and (qsize % self.sample_every) == 0:
            self._emit("DEBUG", "dispatch_done", produced=produced, qsize=qsize, **extra)

    def error(self, ev, *, exc: BaseException, **extra):
        name, extra = self._shape_event(ev, want_name=True)
        self._emit("ERROR", "kernel_error", event=name, error=str(exc), **extra)

    # ------------- Business Event Reporting --------------------------

    def biz(self, ev):
        if self.recorder:
            self.recorder.emit(ev)
