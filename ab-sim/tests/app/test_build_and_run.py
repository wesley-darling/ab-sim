# tests/app/test_build_and_run.py
from types import SimpleNamespace as NS

from ab_sim.app.build import build


def cfg():
    return NS(
        name="test",
        run_id="t-1",
        sim=NS(epoch=[2025, 1, 1, 0, 0, 0], seed=1, duration=3600),
        log=NS(level="INFO", debug=False, sample_every=1000),
        world=NS(capacity=10, geo=None),
        speeds=NS(pickup_mps=8.0, drop_mps=10.0),
        idle=NS(timeout_s=300),
    )


def test_build_runs():
    app = build(cfg(), use_logging=False)
    app.kernel.run(until=1800)  # 30 minutes
