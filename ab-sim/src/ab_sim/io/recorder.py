# telemetry/recorder.py
import json
import queue
import sys
import threading
from dataclasses import asdict
from typing import Protocol


class Sink(Protocol):
    def write(self, ev) -> None: ...


class JsonlSink:
    def __init__(self, fp=sys.stdout):
        self.fp = fp

    def write(self, ev) -> None:
        self.fp.write(json.dumps(asdict(ev)) + "\n")


class MemorySink:
    def __init__(self):
        self.events: list = []

    def write(self, ev) -> None:
        self.events.append(ev)


# Async sink (non-blocking, drops on overflow)
class AsyncSink:
    def __init__(self, sink: Sink, maxsize: int = 10000):
        self.sink, self.q = sink, queue.Queue(maxsize=maxsize)
        self._stop = False
        self._t = threading.Thread(target=self._run, daemon=True)
        self._t.start()
        self.dropped = 0

    def write(self, ev) -> None:
        try:
            self.q.put_nowait(ev)
        except queue.Full:
            self.dropped += 1  # never block the sim

    def _run(self):
        while not self._stop:
            ev = self.q.get()
            try:
                self.sink.write(ev)
            except Exception:
                pass

    def stop(self):
        self._stop = True
        self._t.join(timeout=1.0)


class Recorder:
    def __init__(self, *sinks: Sink):
        self.sinks = sinks or (JsonlSink(),)

    def emit(self, ev):
        for s in self.sinks:
            try:
                s.write(ev)
            except Exception:
                pass  # never break the sim
