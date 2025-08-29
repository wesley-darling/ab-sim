# tests/app/test_build_and_run.py
from ab_sim.app.build import build
from ab_sim.io.config import ScenarioConfig


def test_build_runs():
    cfg = ScenarioConfig.model_validate(
        {
            "name": "test",
            "run_id": "t-1",
            "sim": {"epoch": [2025, 1, 1, 0, 0, 0], "seed": 1, "duration": 3600},
            "mechanics": {
                "mode": "idealized",
                "metric": "euclidean",
                "speed_kind": "constant",
                "base_mps": 10.0,
            },
        }
    )
    app = build(cfg, use_logging=False)
    app.kernel.run(until=1800)  # 30 minutes
