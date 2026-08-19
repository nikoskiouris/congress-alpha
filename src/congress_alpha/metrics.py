"""Walk-forward performance statistics. Numpy only. No pandas."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import date

import numpy as np


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_ppf(p: float) -> float:
    """Acklam's rational approximation of the normal quantile."""
    p = min(max(p, 1e-12), 1.0 - 1e-12)
    a = (
        -3.969683028665376e01,
        2.209460984245205e02,
        -2.759285104469687e02,
        1.383577459677449e02,
        -3.066479806614736e01,
        2.506628277459239e00,
    )
    b = (
        -5.447609879822406e01,
        1.615858368580409e02,
        -1.556989798598866e02,
        6.680131188771972e01,
        -1.328068155288572e01,
    )
    c = (
        -7.784894002430293e-03,
        -3.223964580411365e-01,
        -2.400758277161838e00,
        -2.549732539343734e00,
        4.374664141464858e00,
        2.938163982698783e00,
    )
    d = (
        7.784695709041462e-03,
        3.224671290700398e-01,
        2.445134137142996e00,
        3.754408661907416e00,
    )
    plow = 0.02425
    phigh = 1.0 - plow
    if p < plow:
        q = math.sqrt(-2.0 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0
        )
    if p > phigh:
        q = math.sqrt(-2.0 * math.log(1.0 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0
        )
    q = p - 0.5
    r = q * q
    return (
        (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5])
        * q
        / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0)
    )


def periods_per_year(dates: list[date]) -> float:
    if len(dates) < 2:
        return 52.0
    gaps = [(b - a).days for a, b in zip(dates, dates[1:])]
    med = sorted(gaps)[len(gaps) // 2]
    return 365.25 / max(float(med), 1.0)


def hac_mean_tstat(x: np.ndarray) -> tuple[float, float]:
    """Newey-West t-stat of the mean, two-sided normal p-value."""
    x = np.asarray(x, dtype=float)
    n = len(x)
    if n < 3:
        return 0.0, 1.0
    mu = float(x.mean())
    u = x - mu
    lags = int(np.floor(4.0 * (n / 100.0) ** (2.0 / 9.0)))
    gamma0 = float(np.dot(u, u) / n)
    var = gamma0
    for lag in range(1, lags + 1):
        gamma = float(np.dot(u[lag:], u[:-lag]) / n)
        w = 1.0 - lag / (lags + 1.0)
        var += 2.0 * w * gamma
    se = math.sqrt(max(var, 0.0) / n)
    if se < 1e-18:
        return 0.0, 1.0
    t = mu / se
    p = 2.0 * (1.0 - _norm_cdf(abs(t)))
    return float(t), float(min(max(p, 0.0), 1.0))


def bootstrap_sharpe_ci(
    excess: np.ndarray,
    ppy: float,
    n_boot: int = 1000,
    seed: int = 7,
    alpha: float = 0.05,
) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    n = len(excess)
    if n < 8:
        return float("nan"), float("nan")
    srs = np.empty(n_boot)
    k = 0
    for _ in range(n_boot):
        samp = rng.choice(excess, size=n, replace=True)
        sd = float(samp.std(ddof=1))
        if sd < 1e-18:
            continue
        srs[k] = (float(samp.mean()) / sd) * math.sqrt(ppy)
        k += 1
    if k < 50:
        return float("nan"), float("nan")
    lo, hi = np.quantile(srs[:k], [alpha / 2.0, 1.0 - alpha / 2.0])
    return float(lo), float(hi)


def deflated_sharpe(
    sharpe: float,
    n_obs: int,
    skew: float,
    kurt_pearson: float,
    n_trials: int,
) -> float:
    """Bailey & López de Prado deflated Sharpe (normality-adjusted, multiple tests)."""
    if n_obs < 8 or not math.isfinite(sharpe):
        return float("nan")
    n_trials = max(int(n_trials), 1)
    sr_var = (
        1.0 - skew * sharpe + ((kurt_pearson - 1.0) / 4.0) * sharpe * sharpe
    ) / max(n_obs - 1, 1)
    sigma = math.sqrt(max(sr_var, 1e-18))
    euler = 0.5772156649015329
    n = float(n_trials)
    emax = (1.0 - euler) * _norm_ppf(1.0 - 1.0 / n) + euler * _norm_ppf(
        1.0 - 1.0 / (n * math.e)
    )
    return float(_norm_cdf((sharpe - emax) / sigma))


def _moments(x: np.ndarray) -> tuple[float, float, float]:
    if len(x) < 3:
        return 0.0, 0.0, 3.0
    mu = float(x.mean())
    d = x - mu
    m2 = float(np.mean(d * d))
    if m2 < 1e-18:
        return 0.0, 0.0, 3.0
    m3 = float(np.mean(d * d * d))
    m4 = float(np.mean(d * d * d * d))
    skew = m3 / (m2**1.5)
    kurt = m4 / (m2 * m2)
    return skew, kurt, kurt


@dataclass
class Performance:
    n_periods: int = 0
    years: float = 0.0
    cagr: float = 0.0
    total_return: float = 0.0
    excess_cagr: float = 0.0
    arithmetic_excess: float = 0.0
    vol: float = 0.0
    excess_vol: float = 0.0
    sharpe: float = 0.0
    sortino: float = 0.0
    information_ratio: float = 0.0
    calmar: float = 0.0
    max_dd: float = 0.0
    max_dd_days: int = 0
    hit_rate: float = 0.0
    profit_factor: float = 0.0
    skew: float = 0.0
    kurtosis: float = 3.0
    var_5: float = 0.0
    cvar_5: float = 0.0
    beta: float = 0.0
    alpha_ann: float = 0.0
    tstat_excess: float = 0.0
    pvalue_excess: float = 1.0
    sharpe_ci_low: float = float("nan")
    sharpe_ci_high: float = float("nan")
    deflated_sharpe: float = float("nan")
    avg_holdings: float = 0.0
    avg_invested: float = 0.0
    turnover: float = 0.0
    turnover_ann: float = 0.0
    avg_cost: float = 0.0
    best_year: float = 0.0
    worst_year: float = 0.0
    yearly: dict[str, float] = field(default_factory=dict)
    monthly: dict[str, float] = field(default_factory=dict)

    def as_public_dict(self) -> dict:
        d = asdict(self)
        for k, v in list(d.items()):
            if isinstance(v, float) and not math.isfinite(v):
                d[k] = None
        return d


def _drawdown(nav: np.ndarray, dates: list[date]) -> tuple[float, int]:
    peak = nav[0]
    peak_date = dates[0]
    max_dd = 0.0
    max_days = 0
    for v, dt in zip(nav, dates):
        if v >= peak:
            peak = v
            peak_date = dt
        dd = float(v / peak - 1.0) if peak > 0 else 0.0
        if dd < max_dd:
            max_dd = dd
        underwater = (dt - peak_date).days
        if v < peak and underwater > max_days:
            max_days = underwater
    return float(max_dd), int(max_days)


def _calendar_returns(dates: list[date], nav: np.ndarray, kind: str) -> dict[str, float]:
    """kind='year' -> YYYY, kind='month' -> YYYY-MM. Close-to-close of last point in bucket."""
    out: dict[str, float] = {}
    last_key = None
    last_nav = 1.0
    start_nav = 1.0
    for dt, v in zip(dates, nav):
        key = f"{dt.year:04d}" if kind == "year" else f"{dt.year:04d}-{dt.month:02d}"
        if last_key is None:
            last_key = key
            start_nav = float(v)
            last_nav = float(v)
            continue
        if key != last_key:
            if start_nav > 0:
                out[last_key] = last_nav / start_nav - 1.0
            last_key = key
            start_nav = last_nav
        last_nav = float(v)
    if last_key is not None and start_nav > 0:
        out[last_key] = last_nav / start_nav - 1.0
    return out


def evaluate(
    net: np.ndarray,
    spy: np.ndarray,
    dates: list[date],
    *,
    avg_holdings: float = 0.0,
    avg_invested: float = 0.0,
    turnover: float = 0.0,
    avg_cost: float = 0.0,
    n_trials: int = 3,
    spy_nav_end: float | None = None,
) -> Performance:
    net = np.asarray(net, dtype=float)
    spy = np.asarray(spy, dtype=float)
    n = len(net)
    empty = Performance(
        avg_holdings=avg_holdings,
        avg_invested=avg_invested,
        turnover=turnover,
        avg_cost=avg_cost,
    )
    if n < 2 or len(dates) != n:
        return empty

    ppy = periods_per_year(dates)
    years = max((dates[-1] - dates[0]).days / 365.25, 1e-6)
    nav = np.cumprod(1.0 + net)
    total = float(nav[-1] - 1.0)
    cagr = float(nav[-1] ** (1.0 / years) - 1.0) if nav[-1] > 0 else -1.0

    if spy_nav_end is None:
        spy_nav_end = float(np.prod(1.0 + spy))
    spy_cagr = float(spy_nav_end ** (1.0 / years) - 1.0) if spy_nav_end > 0 else 0.0
    excess_cagr = (1.0 + cagr) / (1.0 + spy_cagr) - 1.0 if spy_cagr > -0.999 else cagr

    xs = net - spy
    vol = float(net.std(ddof=1) * math.sqrt(ppy)) if n > 2 else 0.0
    xs_vol = float(xs.std(ddof=1) * math.sqrt(ppy)) if n > 2 else 0.0
    mu_xs = float(xs.mean())
    arithmetic_excess = mu_xs * ppy
    xs_sd = float(xs.std(ddof=1)) if n > 2 else 0.0
    if xs_sd > 1e-18:
        sharpe = mu_xs / xs_sd * math.sqrt(ppy)
    elif abs(mu_xs) < 1e-18:
        sharpe = 0.0
    else:
        sharpe = 10.0 if mu_xs > 0 else -10.0
    ir = sharpe  # excess vs SPY with tracking-error vol

    downside = np.minimum(net, 0.0)
    dstd = float(np.sqrt(np.mean(downside * downside)))
    sortino = (float(net.mean()) / dstd * math.sqrt(ppy)) if dstd > 1e-18 else 0.0

    max_dd, max_dd_days = _drawdown(nav, dates)
    calmar = (cagr / abs(max_dd)) if max_dd < -1e-9 else 0.0

    hit = float((xs > 0).mean())
    gains = float(xs[xs > 0].sum())
    losses = float(-xs[xs < 0].sum())
    profit_factor = (gains / losses) if losses > 1e-12 else (10.0 if gains > 0 else 0.0)

    skew, kurt, _ = _moments(xs)
    var_5 = float(np.quantile(net, 0.05))
    tail = net[net <= var_5]
    cvar_5 = float(tail.mean()) if len(tail) else var_5

    # OLS net = alpha + beta * spy
    spy_c = spy - spy.mean()
    var_s = float(np.dot(spy_c, spy_c))
    if var_s > 1e-18:
        beta = float(np.dot(spy_c, net - net.mean()) / var_s)
        alpha = float(net.mean() - beta * spy.mean())
    else:
        beta, alpha = 0.0, float(net.mean())
    alpha_ann = alpha * ppy

    tstat, pval = hac_mean_tstat(xs)
    lo, hi = bootstrap_sharpe_ci(xs, ppy)
    dsr = deflated_sharpe(sharpe, n, skew, kurt, n_trials)

    yearly = _calendar_returns(dates, nav, "year")
    monthly = _calendar_returns(dates, nav, "month")
    yvals = list(yearly.values())

    return Performance(
        n_periods=n,
        years=years,
        cagr=cagr,
        total_return=total,
        excess_cagr=excess_cagr,
        arithmetic_excess=arithmetic_excess,
        vol=vol,
        excess_vol=xs_vol,
        sharpe=sharpe,
        sortino=sortino,
        information_ratio=ir,
        calmar=calmar,
        max_dd=max_dd,
        max_dd_days=max_dd_days,
        hit_rate=hit,
        profit_factor=profit_factor,
        skew=skew,
        kurtosis=kurt,
        var_5=var_5,
        cvar_5=cvar_5,
        beta=beta,
        alpha_ann=alpha_ann,
        tstat_excess=tstat,
        pvalue_excess=pval,
        sharpe_ci_low=lo,
        sharpe_ci_high=hi,
        deflated_sharpe=dsr,
        avg_holdings=avg_holdings,
        avg_invested=avg_invested,
        turnover=turnover,
        turnover_ann=turnover * ppy,
        avg_cost=avg_cost,
        best_year=max(yvals) if yvals else 0.0,
        worst_year=min(yvals) if yvals else 0.0,
        yearly=yearly,
        monthly=monthly,
    )
