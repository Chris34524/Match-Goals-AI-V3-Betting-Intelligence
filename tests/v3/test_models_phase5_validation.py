"""Fail-closed protections beyond the happy path; no runtime artifact mutation."""
from copy import deepcopy
import pytest
from v3.models.dataset import model_matrix, feature_specs
from v3.models.contract import immutable
from v3.models.split import temporal_split
from v3.models.metrics import binary_metrics, multiclass_metrics
from v3.models.champion import compare
from test_models_protocol import canonical_fixture, rows


def test_artifact_blocked_feature_not_silently_filtered():
    c = canonical_fixture()
    features = {s.name:(1 if s.dtype == 'int' else 1.) for s in feature_specs('BTTS')}
    features['closing_odds'] = 2.1
    with pytest.raises(ValueError,match='blocked'):
        model_matrix([c],{'a':dict(features=features)},'BTTS')


def test_invalid_label_excluded_not_feature():
    c = canonical_fixture()
    c['labels']['label_over_2_5'] = False
    out,audit = model_matrix([c],{},'BTTS')
    assert not out and audit['exclusion_reasons']['conflicting_or_invalid_labels'] == 1


def test_immutable_artifact_conflict_and_symlink(tmp_path):
    path = tmp_path/'run.json'
    immutable(path,{'a':1})
    immutable(path,{'a':1})
    with pytest.raises(ValueError,match='conflict'):
        immutable(path,{'a':2})
    alias = tmp_path/'alias'
    alias.symlink_to(path)
    with pytest.raises(ValueError,match='unsafe'):
        immutable(alias,{'a':1})


def test_split_timezone_ties_use_utc_dates():
    rs = rows(5)
    rs[0]['kickoff_at'] = '2026-01-01T23:30:00-02:00'
    rs[1]['kickoff_at'] = '2026-01-02T02:30:00+00:00'
    g,_ = temporal_split(rs)
    memberships = {r['target_id']:k for k,values in g.items() for r in values}
    assert memberships['0'] == memberships['1']


@pytest.mark.parametrize('metric,ys,ps',[(binary_metrics,[0,1],[.2]),(multiclass_metrics,[3],[[.2,.3,.5]]),
                                        (multiclass_metrics,[0],[[.2,.3,float('nan')]])])
def test_metrics_reject_bad_lengths_labels_and_probabilities(metric,ys,ps):
    with pytest.raises(ValueError):
        metric(ys,ps)


def test_champion_rejects_different_event_cutoff_and_lineage():
    rs = rows(1)
    evidence = [dict(rs[0],model='J_BT_sin_temporada',market='BTTS',source_hash='synthetic',lineage='synthetic',
                     generated_at='2026-01-01T11:00:00+00:00',probability=.5)]
    for key,value,reason in [('event',{'home':'wrong','away':'B'},'cutoff_not_accredited'),
                             ('cutoff','2026-01-01T11:30:00+00:00','cutoff_not_accredited'),
                             ('label_version','wrong','cutoff_not_accredited'),
                             ('lineage',None,'prediction_lineage_missing')]:
        e = deepcopy(evidence)
        e[0][key] = value
        assert compare(rs,e,'BTTS')['reason'] == reason


def test_divergence_requires_earlier_evidence_and_checks_both_losses():
    from v3.models.evaluation import divergence
    b = {s:dict(brier=.2,logloss=.4) for s in ('TRAIN','VALIDATION','TEST')}
    m = {s:dict(brier=.1,logloss=.3) for s in b}
    m['TEST']['logloss'] = .41
    assert divergence(m,b)
    m['TRAIN']['logloss'] = .5
    assert not divergence(m,b)


def test_selection_tie_break_and_exact_champion_oos():
    from v3.models.evaluation import evaluate
    rs = rows()
    # Constant features/labels make all L2 candidates equivalent; index wins.
    for r in rs:
        r['features']['x'] = 0.
        r['label'] = 0
    evidence = [dict(r,model='J_BT_sin_temporada',market='BTTS',source_hash='synthetic',lineage='synthetic',
                     generated_at=r['kickoff_at'].replace('12:00','11:00'),probability=.5) for r in rs[24:]]
    result = evaluate(rs,['x'],'BTTS',evidence)
    assert result['validation_selection']['selected_index'] == 0
    assert result['champion']['champion_comparison_status'] == 'ACCREDITED'
    assert all('champion' in w for w in result['oos_windows'])
    # Perfect TRAIN base-rate (0) is stronger than the fitted intercept.
    assert result['decision'] == 'DOES_NOT_BEAT_CHAMPION'
    assert result['promotion'] is False


def test_integrity_detects_mutation_addition_deletion_and_mtime(tmp_path,monkeypatch):
    from v3.models.integrity import capture,summarize,verify
    monkeypatch.chdir(tmp_path)
    folder = tmp_path/'evidence'
    folder.mkdir()
    p = folder/'a'
    p.write_text('original')
    before = summarize(capture(['evidence']))
    verify(before,before,['evidence'],True)
    p.write_text('changed')
    with pytest.raises(ValueError,match='changed'):
        verify(before,summarize(capture(['evidence'])),['evidence'])
    p.write_text('original')
    q = folder/'b'
    q.write_text('added')
    with pytest.raises(ValueError):
        verify(before,summarize(capture(['evidence'])),['evidence'])
    q.unlink()
    changed_mtime = deepcopy(before)
    changed_mtime['evidence']['mtime_hash'] = 'changed'
    with pytest.raises(ValueError):
        verify(before,changed_mtime,['evidence'],True)
    p.unlink()
    with pytest.raises(ValueError):
        verify(before,summarize(capture(['evidence'])),['evidence'])
