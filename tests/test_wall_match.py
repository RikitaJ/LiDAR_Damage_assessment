from pipeline.benchmark.wall_match import wall_pass_rate


def test_cyclic_beats_sorted_mismatch():
    pred = [350.0, 420.0, 350.0, 420.0]
    truth = [420.0, 350.0, 420.0, 350.0]
    rate, _ = wall_pass_rate(pred, truth, tol_cm=2.0, tol_rel=0.02)
    assert rate >= 0.99


def test_cyclic_partial_rotation():
    pred = [200.0, 120.0, 200.0, 120.0]
    truth = [120.0, 200.0, 120.0, 200.0]
    rate, _ = wall_pass_rate(pred, truth, tol_cm=2.0, tol_rel=0.02)
    assert rate >= 0.99
