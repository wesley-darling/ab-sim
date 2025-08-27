# tests/sim/test_rng_registry.py
import numpy as np

from ab_sim.sim.rng import RNGRegistry


def test_named_streams_are_deterministic():
    reg1 = RNGRegistry(123, scenario="A", worker=0)
    reg2 = RNGRegistry(123, scenario="A", worker=0)
    a1 = reg1.stream("demand").random(5)
    a2 = reg2.stream("demand").random(5)
    assert np.allclose(a1, a2)


def test_streams_are_independent():
    reg = RNGRegistry(123)
    a = reg.stream("demand").random(5)
    b = reg.stream("speeds").random(5)
    assert not np.allclose(a, b)


def test_substreams_by_entity_are_order_invariant():
    reg = RNGRegistry(123)
    g17 = reg.substream("speeds", 17)
    g42 = reg.substream("speeds", 42)
    # using 42 then 17 (reverse order) yields the same draws for each id
    reg2 = RNGRegistry(123)
    g42b = reg2.substream("speeds", 42)
    g17b = reg2.substream("speeds", 17)
    assert np.allclose(g17.random(3), g17b.random(3))
    assert np.allclose(g42.random(3), g42b.random(3))


def test_worker_shards_are_disjoint():
    reg0 = RNGRegistry(123, worker=0)
    reg1 = RNGRegistry(123, worker=1)
    a = reg0.stream("demand").random(10)
    b = reg1.stream("demand").random(10)
    assert not np.allclose(a, b)
