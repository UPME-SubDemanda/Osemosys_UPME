from app.simulation.benchmark import compare_with_tolerance


def test_compare_with_tolerance_ok():
    ref = {"objective_value": 100.0, "coverage_ratio": 0.8}
    actual = {"objective_value": 100.00001, "coverage_ratio": 0.80001}
    is_ok, errors = compare_with_tolerance(reference=ref, actual=actual, tolerance=1e-3)
    assert is_ok
    assert all(v <= 1e-3 for v in errors.values())


def test_compare_with_tolerance_fail():
    ref = {"objective_value": 100.0}
    actual = {"objective_value": 150.0}
    is_ok, errors = compare_with_tolerance(reference=ref, actual=actual, tolerance=1e-4)
    assert not is_ok
    assert errors["objective_value"] > 1e-4
