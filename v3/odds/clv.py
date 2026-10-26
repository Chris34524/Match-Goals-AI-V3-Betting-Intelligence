"""Price CLV is blocked without explicit comparable accredited closing evidence."""
from .movement import comparable
from .snapshots import accredited


def clv(taken, close=None):
    if taken is None:
        return dict(clv_status='not_applicable',reason='no_decision_observation',clv_price=None)
    if close is None or not accredited(close.get('record',{}),'closing') or not close.get('closing_accredited'):
        return dict(clv_status='blocked',reason='no_accredited_closing',clv_price=None)
    if not comparable(taken,close):
        return dict(clv_status='blocked',reason='not_comparable',clv_price=None)
    return dict(clv_status='computable',reason=None,
                clv_price=taken['record']['decimal_odds']/close['record']['decimal_odds']-1,
                convention='odds_taken / odds_close - 1',
                taken_run_id=taken['run_id'],closing_run_id=close['run_id'])
