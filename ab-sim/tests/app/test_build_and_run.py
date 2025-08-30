# tests/app/test_build_and_run.py
from ab_sim.app.build import build


def test_build_runs():
    cfg = {
        "name": "test",
        "run_id": "t-1",
        "sim": {"epoch": [2025, 1, 1, 0, 0, 0], "seed": 1, "duration": 3600},
        "mechanics": {
            "od_sampler": {"kind": "idealized", "zones": [(0.0, 0.0, 10_000.0, 10_000.0)]},
            "route_planner": {"kind": "euclidean"},
            "speed_sampler": {"kind": "global", "v_mps": 10.0},
            "path_traverser": {"kind": "piecewise_const"},
        },
    }
    app = build(cfg, use_logging=False)
    app.kernel.run(until=1800)  # 30 minutes
