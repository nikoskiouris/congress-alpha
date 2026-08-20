from datetime import date, timedelta

import numpy as np

from congress_alpha.metrics import evaluate, hac_mean_tstat, periods_per_year


def test_periods_per_year_weekly():
    dates = [date(2024, 1, 3) + timedelta(days=7 * i) for i in range(10)]
    assert abs(periods_per_year(dates) - 365.25 / 7) < 0.01


def test_evaluate_known_path():
    dates = [date(2020, 1, 8) + timedelta(days=7 * i) for i in range(52)]
    net = np.full(52, 0.01)
    spy = np.zeros(52)
    s = evaluate(net, spy, dates)
    assert s.n_periods == 52
    assert s.total_return > 0.6
    assert s.cagr > 0.5
    assert s.max_dd == 0.0
    assert s.sharpe > 0
    assert s.hit_rate == 1.0


def test_evaluate_drawdown():
    dates = [date(2020, 1, 8) + timedelta(days=7 * i) for i in range(4)]
    net = np.array([0.10, -0.50, 0.0, 0.0])
    spy = np.zeros(4)
    s = evaluate(net, spy, dates)
    # 1.10 -> 0.55 is -50%
    assert s.max_dd < -0.49
    assert s.max_dd > -0.51


def test_hac_positive_mean():
    rng = np.random.default_rng(0)
    x = rng.normal(0.02, 0.01, 200)
    t, p = hac_mean_tstat(x)
    assert t > 5
    assert p < 0.01
