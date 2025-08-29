def test_od_sampling_is_deterministic_with_registry():
    from ab_sim.domain.mechanics.mechanics_factory import build_mechanics
    from ab_sim.io.config import ScenarioConfig
    from ab_sim.sim.rng import RNGRegistry

    cfg = ScenarioConfig.model_validate({"mechanics": {"mode": "idealized", "metric": "euclidean"}})

    reg1 = RNGRegistry(master_seed=123, scenario="west_sac", worker=0)
    reg2 = RNGRegistry(master_seed=123, scenario="west_sac", worker=0)

    m1 = build_mechanics(cfg.mechanics, rng_registry=reg1)
    m2 = build_mechanics(cfg.mechanics, rng_registry=reg2)

    # Draw 5 ODs from each; they should match exactly
    pts1 = [m1.space.sample_origin(None) for _ in range(5)]
    pts2 = [m2.space.sample_origin(None) for _ in range(5)]
    assert [(p.x, p.y) for p in pts1] == [(p.x, p.y) for p in pts2]
