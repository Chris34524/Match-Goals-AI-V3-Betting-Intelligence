from v3.features.strength import assessment


def test_strength_remains_blocked_without_lineage():
    rows = assessment()
    assert len(rows) == 14
    assert all(r['value'] is None and r['status'] == 'blocked' for r in rows.values())
    assert all(r['formula'] and r['reason'] and r['provenance_requirement'] for r in rows.values())
    assert assessment() == rows


def test_no_own_form_mislabeled_as_strength():
    assert not any('rolling_points' in name for name in assessment())
