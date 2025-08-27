# sim/rng.py
from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from zlib import crc32

import numpy as np


def _u32(x: int) -> int:
    return int(x & 0xFFFFFFFF)


def _crc32_u32(s: str) -> int:
    return _u32(crc32(s.encode("utf-8")))


@dataclass(frozen=True)
class RNGKey:
    """Hierarchical key: stream name + optional ints/strings for substreams."""

    stream: str
    parts: tuple[int, ...]  # already normalized to u32

    @classmethod
    def from_parts(cls, stream: str, *parts: object) -> RNGKey:
        norm: list[int] = [_crc32_u32(stream)]
        for p in parts:
            if isinstance(p, (int, np.integer)):
                norm.append(_u32(int(p)))
            elif isinstance(p, str):
                norm.append(_crc32_u32(p))
            else:
                # Stable, portable stringification then crc
                norm.append(_crc32_u32(repr(p)))
        return cls(stream=stream, parts=tuple(norm))


class RNGRegistry:
    """
    Deterministic registry of numpy.random.Generator streams.
    Derivation path: [master_seed, scenario, worker, *key.parts]
    """

    def __init__(self, master_seed: int, *, scenario: str | int = 0, worker: int = 0):
        self.master_seed = _u32(master_seed)
        self.scenario_tag = _crc32_u32(str(scenario))
        self.worker = _u32(worker)

        # master SeedSequence for this worker
        self._root_ss = np.random.SeedSequence([self.master_seed, self.scenario_tag, self.worker])

    @cache
    def generator(self, key: RNGKey, *, bitgen: str = "PCG64") -> np.random.Generator:
        """
        Get (and cache) a named generator, optionally sub-keyed.
        Example: gen = reg.generator(RNGKey.from_parts("speeds", driver_id))
        """
        # Derive a child SeedSequence deterministically from the key path
        ss = self._root_ss.spawn(1)[
            0
        ]  # avoid consuming root state with child-spawn? we can also use spawn(len=1) each time
        # Better: use SeedSequence with 'spawn_key' directly, no root consumption:
        ss = np.random.SeedSequence(
            entropy=[self.master_seed, self.scenario_tag, self.worker, *key.parts]
        )

        if bitgen == "PCG64":
            bg = np.random.PCG64(ss)
        elif bitgen == "Philox":
            bg = np.random.Philox(ss)
        else:
            raise ValueError("Unknown bitgen: " + bitgen)
        return np.random.Generator(bg)

    # Convenience shorthands
    def stream(self, name: str) -> np.random.Generator:
        return self.generator(RNGKey.from_parts(name))

    def substream(self, name: str, *parts: object) -> np.random.Generator:
        return self.generator(RNGKey.from_parts(name, *parts))
