"""Initial equity/peak=0; max drawdown=max(previous peak-current equity), in units."""
from v3.calibration.contract import time


def drawdown(positions):
    equity=peak=maximum=0.0;curve=[]
    for r in sorted(positions,key=lambda r:(time(r['settled_at']),r['paper_bet_id'])):
        equity+=r['profit_units'];peak=max(peak,equity);maximum=max(maximum,peak-equity)
        curve.append(dict(settled_at=r['settled_at'],paper_bet_id=r['paper_bet_id'],equity_units=equity,drawdown_units=peak-equity))
    return dict(equity_curve=curve,max_drawdown_units=maximum,convention='peak minus equity; initial peak 0; settlement chronology')
