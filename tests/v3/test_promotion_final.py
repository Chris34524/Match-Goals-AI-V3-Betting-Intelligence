import pytest
from v3.validation.promotion import evaluate,CHAMPION


def evidence():
    from v3.calibration.reliability import metrics
    rows=[dict(target_id=str(i),event=dict(home='A',away='B'),kickoff_at='2026-01-01T12:00:00Z',cutoff='2026-01-01T10:00:00Z',label_version='regulation',
               predicted_at='2026-01-01T09:00:00Z',label_available_at='2026-01-01T15:00:00Z',partition='OOS',synthetic_test_only=False,temporal_accredited=True,temporal_lineage='contract-fixture',p=.98 if i%2 else .02,y=i%2) for i in range(200)]
    for i,r in enumerate(rows):
        if i>=100:
            for key in ('kickoff_at','cutoff','predicted_at','label_available_at'):r[key]=r[key].replace('2026-01-01','2026-01-02')
    champions=[dict(r,model='J_BT_sin_temporada',market='BTTS',source_hash='contract-fixture',lineage='contract-fixture',generated_at=r['predicted_at'],probability=.8 if r['y'] else .2) for r in rows]
    cm=metrics([r['y'] for r in rows],[r['p'] for r in rows],'BTTS');bm=metrics([r['y'] for r in rows],[r['probability'] for r in champions],'BTTS')
    return dict(rows=rows,champion_predictions=champions,market='BTTS',real_oos_accredited=True,champion_accredited=True,same_rows=True,same_label_definition=True,
                same_temporal_cutoff=True,integrity_pass=True,temporal_lineage_accredited=True,
                synthetic_test_only=False,challenger_brier=cm['brier'],champion_brier=bm['brier'],
                challenger_logloss=cm['logloss'],champion_logloss=bm['logloss'],ece=.02,
                windows=[dict(fold_id=str(i),ids=[r['target_id'] for r in rows[i*100:(i+1)*100]],brier_delta=-.1,logloss_delta=-.1) for i in range(2)],oos_count=200,temporal_divergence=False)


def test_promotion_recommendation_never_mutates_champion():
    r=evaluate(evidence());assert r['gate_status']=='PROMOTE_ELIGIBLE'
    assert r['champion']==CHAMPION and r['champion_changed'] is False


@pytest.mark.parametrize('field,value',[('real_oos_accredited',False),('champion_accredited',False),('same_rows',False),('same_label_definition',False),('same_temporal_cutoff',False),('synthetic_test_only',True),('integrity_pass',False),('ece',None)])
def test_promotion_blocked(field,value):
    e=evidence();e[field]=value;assert evaluate(e)['gate_status']=='BLOCKED'


@pytest.mark.parametrize('field,value',[('ece',.2),('temporal_divergence',True)])
def test_promotion_rejects_insufficient_or_worse(field,value):
    e=evidence();e[field]=value;assert evaluate(e)['gate_status']=='DO_NOT_PROMOTE'


def test_current_promotion_blocked():assert evaluate({})['gate_status']=='BLOCKED'


def test_promotion_exact_comparator_mismatches_block():
    for field,value in [('cutoff','2026-01-01T11:00:00Z'),('label_version','different'),('target_id','missing')]:
        e=evidence();e['champion_predictions'][0][field]=value
        assert evaluate(e)['gate_status']=='BLOCKED'
    e=evidence();e['challenger_logloss']=0
    assert evaluate(e)['gate_status']=='BLOCKED'
    e=evidence();e['rows']=e['rows'][:-1];e['champion_predictions']=e['champion_predictions'][:-1];e['oos_count']=199;e['windows'][1]['ids']=e['windows'][1]['ids'][:-1]
    assert evaluate(e)['gate_status']=='DO_NOT_PROMOTE'


def test_promotion_single_window_and_overlap():
    e=evidence();e['windows']=[dict(e['windows'][0],ids=[r['target_id'] for r in e['rows']])]
    assert evaluate(e)['gate_status']=='DO_NOT_PROMOTE'
    e=evidence();e['windows'][1]=e['windows'][0]
    assert evaluate(e)['gate_status']=='BLOCKED'
