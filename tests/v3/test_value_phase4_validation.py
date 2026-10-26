"""Validator arithmetic checks operate offline and detect regressions."""
from v3.value import phase4_validation as validator


def test_validation_math_checks_and_fingerprints_are_deterministic():
    checks, hashes = validator.math_checks()
    assert all(checks.values())
    assert (checks, hashes) == validator.math_checks()
    assert all(len(value)==64 for value in hashes.values())


def test_validator_detects_wrong_fair_odds(monkeypatch):
    original=validator.evaluate_fixture
    def corrupted(*args,**kwargs):
        result=original(*args,**kwargs)
        if result['fair_odds'] is not None:result['fair_odds']=99.
        return result
    monkeypatch.setattr(validator,'evaluate_fixture',corrupted)
    checks,_=validator.math_checks()
    assert checks['05_fair_odds'] is False
