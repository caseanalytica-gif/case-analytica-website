"""Core mathematical engine.

Contents
--------
* Moment estimation: annualised expected returns and (shrunk) covariance.
* FrictionModel: expense-ratio drag plus an expected rebalancing-tax drag.
* Mean-variance optimisation (long-only, fully invested):
    - Maximum Sharpe ratio on friction-adjusted (net) returns
    - Minimum variance
    - Efficient frontier traced in net-return / volatility space
* Monte Carlo forward simulator with monthly steps, periodic rebalancing,
  per-asset average-cost basis tracking, realised-gain taxation and
  expense-ratio drag.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.optimize import minimize

log = logging.getLogger(__name__)

REBALANCES_PER_YEAR = {"monthly": 12, "quarterly": 4, "semiannual": 2, "annual": 1}


# --------------------------------------------------------------------------
# Moment estimation
# --------------------------------------------------------------------------
def expected_returns(returns: pd.DataFrame, periods: int, method: str = "arithmetic") -> pd.Series:
    """Annualised expected simple returns."""
    if method == "arithmetic":
        mu = returns.mean() * periods
    elif method == "geometric":
        mu = (1 + returns).prod() ** (periods / len(returns)) - 1
    else:
        raise ValueError(f"Unknown expected_return_method '{method}'")
    return mu.rename("expected_return")


def ledoit_wolf_correlation(returns: pd.DataFrame) -> tuple[np.ndarray, float]:
    """Ledoit-Wolf (2004) shrinkage applied to standardised returns.

    Shrinking the correlation matrix toward the identity (instead of the raw
    covariance toward a scaled identity) keeps every asset's own variance
    exact, which matters when one asset (a micro-cap) is far more volatile
    than the rest.
    """
    X = returns.values
    X = (X - X.mean(0)) / X.std(0, ddof=0)
    T, N = X.shape
    S = X.T @ X / T                                   # sample correlation
    F = np.eye(N)                                     # target (trace(S)/N == 1)
    d2 = np.sum((S - F) ** 2) / N
    row_norm4 = np.sum(X ** 2, axis=1) ** 2
    b2_bar = (row_norm4.sum() - T * np.sum(S ** 2)) / (T ** 2 * N)
    b2 = min(b2_bar, d2)
    delta = 0.0 if d2 == 0 else b2 / d2
    R = delta * F + (1 - delta) * S
    np.fill_diagonal(R, 1.0)
    return R, float(delta)


def covariance_matrix(returns: pd.DataFrame, periods: int,
                      method: str = "ledoit_wolf") -> tuple[pd.DataFrame, float]:
    """Annualised covariance. Returns (cov, shrinkage_intensity)."""
    cols = returns.columns
    if method == "sample":
        cov, delta = returns.cov().values * periods, 0.0
    elif method == "ledoit_wolf":
        R, delta = ledoit_wolf_correlation(returns)
        sd = returns.std(ddof=1).values * np.sqrt(periods)
        cov = R * np.outer(sd, sd)
    else:
        raise ValueError(f"Unknown covariance_method '{method}'")
    cov = 0.5 * (cov + cov.T)
    eig_min = np.linalg.eigvalsh(cov).min()
    if eig_min <= 1e-12:
        cov += np.eye(len(cols)) * (abs(eig_min) + 1e-10)
        log.warning("Covariance not positive definite; added diagonal jitter")
    return pd.DataFrame(cov, index=cols, columns=cols), delta


def asset_statistics(prices: pd.DataFrame, returns: pd.DataFrame, mu: pd.Series,
                     cov: pd.DataFrame, rf: float, periods: int) -> pd.DataFrame:
    years = len(returns) / periods
    vol = np.sqrt(np.diag(cov.values))
    cagr = (prices.iloc[-1] / prices.iloc[0]) ** (1 / years) - 1
    dd = (prices / prices.cummax() - 1).min()
    return pd.DataFrame({
        "Annual Return (arith.)": mu,
        "CAGR": cagr,
        "Annual Volatility": vol,
        "Sharpe Ratio": (mu - rf) / vol,
        "Max Drawdown": dd,
        "Skewness (daily)": returns.skew(),
        "Excess Kurtosis (daily)": returns.kurt(),
        "Start Price": prices.iloc[0],
        "End Price": prices.iloc[-1],
        "Observations": len(returns),
    })


# --------------------------------------------------------------------------
# Friction model
# --------------------------------------------------------------------------
class FrictionModel:
    """Expected annual return leakage from fees and rebalancing taxes.

    Expense drag is a flat ``expense_ratio`` per year.

    Tax drag is estimated by drawing ``n_draws`` joint one-period lognormal
    asset returns (fixed draws, so the function is deterministic and smooth
    enough for SLSQP). Within each period the portfolio drifts away from its
    target weights; the overweight assets are sold back to target, the gain
    embedded in the sold value is realised (basis = start-of-period value),
    losses net against gains, and ``tax_rate`` applies to the positive net.
    """

    def __init__(self, mu: np.ndarray, cov: np.ndarray, expense_ratio: float,
                 tax_rate: float, rebalance_frequency: str = "annual",
                 n_draws: int = 4000, seed: int = 7):
        if rebalance_frequency not in REBALANCES_PER_YEAR:
            raise ValueError(f"rebalance_frequency must be one of {list(REBALANCES_PER_YEAR)}")
        self.expense_ratio = float(expense_ratio)
        self.tax_rate = float(tax_rate)
        self.f = REBALANCES_PER_YEAR[rebalance_frequency]
        dt = 1.0 / self.f
        rng = np.random.default_rng(seed)
        L = np.linalg.cholesky(cov * dt)
        drift = (mu - 0.5 * np.diag(cov)) * dt
        z = rng.standard_normal((n_draws, len(mu)))
        self.R = np.expm1(drift + z @ L.T)            # one-period simple returns

    def tax_drag(self, w: np.ndarray) -> float:
        if self.tax_rate == 0:
            return 0.0
        R = self.R
        Rp = R @ w
        drifted = w * (1 + R)                         # $ per $1 start, per asset
        target = np.outer(1 + Rp, w)
        sell = np.maximum(drifted - target, 0.0)
        # Gain share of sold value = 1 - basis/value. Where the asset went to
        # zero nothing is sold (sell == 0), so define the fraction as 0 there.
        gain_frac = np.divide(R, 1 + R, out=np.zeros_like(R), where=(1 + R) > 1e-12)
        net_gain = np.maximum((sell * gain_frac).sum(axis=1), 0.0)
        return float(self.tax_rate * net_gain.mean() * self.f)

    def total_drag(self, w: np.ndarray) -> float:
        return self.expense_ratio + self.tax_drag(w)


# --------------------------------------------------------------------------
# Portfolio math
# --------------------------------------------------------------------------
@dataclass
class PortfolioResult:
    name: str
    weights: pd.Series
    gross_return: float
    net_return: float
    volatility: float
    sharpe_gross: float
    sharpe_net: float
    expense_drag: float
    tax_drag: float
    converged: bool
    message: str = ""
    extra: dict = field(default_factory=dict)


class MeanVarianceOptimizer:
    def __init__(self, mu: pd.Series, cov: pd.DataFrame, rf: float,
                 friction: FrictionModel, bounds=(0.0, 1.0),
                 n_random_starts: int = 20, seed: int = 42):
        self.tickers = list(mu.index)
        self.mu = mu.values.astype(float)
        self.cov = cov.loc[self.tickers, self.tickers].values.astype(float)
        self.rf = float(rf)
        self.fr = friction
        self.n = len(self.tickers)
        lo, hi = float(bounds[0]), float(bounds[1])
        if lo < 0 or hi > 1 or lo * self.n > 1 or hi * self.n < 1:
            raise ValueError(f"Infeasible weight bounds {bounds} for {self.n} assets")
        self.bounds = [(lo, hi)] * self.n
        self.n_random_starts = n_random_starts
        self.rng = np.random.default_rng(seed)
        self.sum_to_one = {"type": "eq", "fun": lambda w: w.sum() - 1.0,
                           "jac": lambda w: np.ones_like(w)}

    # metrics -------------------------------------------------------------
    def vol(self, w):
        return float(np.sqrt(max(w @ self.cov @ w, 0.0)))

    def gross(self, w):
        return float(w @ self.mu)

    def net(self, w):
        return self.gross(w) - self.fr.total_drag(w)

    def _clean(self, w):
        w = np.clip(w, 0.0, None)
        w[w < 1e-6] = 0.0
        return w / w.sum()

    def evaluate(self, name, w, converged=True, message=""):
        w = self._clean(np.asarray(w, float))
        v = self.vol(w)
        return PortfolioResult(
            name=name, weights=pd.Series(w, index=self.tickers, name=name),
            gross_return=self.gross(w), net_return=self.net(w), volatility=v,
            sharpe_gross=(self.gross(w) - self.rf) / v,
            sharpe_net=(self.net(w) - self.rf) / v,
            expense_drag=self.fr.expense_ratio, tax_drag=self.fr.tax_drag(w),
            converged=converged, message=message)

    # starts --------------------------------------------------------------
    def _starts(self):
        starts = [np.full(self.n, 1.0 / self.n)]
        starts += [np.eye(self.n)[i] * 0.9 + 0.1 / self.n for i in range(self.n)]
        starts += list(self.rng.dirichlet(np.ones(self.n), self.n_random_starts))
        lo, hi = self.bounds[0]
        return [self._project(s, lo, hi) for s in starts]

    @staticmethod
    def _project(w, lo, hi):
        for _ in range(100):
            w = np.clip(w, lo, hi)
            w = w + (1 - w.sum()) / len(w)
            if np.all(w >= lo - 1e-12) and np.all(w <= hi + 1e-12):
                break
        return np.clip(w, lo, hi)

    # optimisers ----------------------------------------------------------
    def min_variance(self) -> PortfolioResult:
        res = minimize(lambda w: w @ self.cov @ w, np.full(self.n, 1 / self.n),
                       jac=lambda w: 2 * self.cov @ w, method="SLSQP",
                       bounds=self.bounds, constraints=[self.sum_to_one],
                       options={"ftol": 1e-14, "maxiter": 1000})
        return self.evaluate("Minimum Variance", res.x, res.success, res.message)

    def max_sharpe(self) -> PortfolioResult:
        """Maximise net Sharpe; multi-start because the tax term is non-convex."""
        def neg_sharpe(w):
            v = self.vol(w)
            return -(self.net(w) - self.rf) / v if v > 0 else 1e6

        best, fallback = None, None
        for w0 in self._starts():
            res = minimize(neg_sharpe, w0, method="SLSQP", bounds=self.bounds,
                           constraints=[self.sum_to_one],
                           options={"ftol": 1e-12, "maxiter": 1000})
            if not np.isfinite(res.fun) or abs(res.x.sum() - 1) > 1e-6:
                continue
            if res.success and (best is None or res.fun < best.fun):
                best = res
            if fallback is None or res.fun < fallback.fun:
                fallback = res
        if best is None:
            if fallback is None:
                raise RuntimeError("Max Sharpe optimisation failed from every start")
            log.warning("No start converged cleanly; using best feasible solution")
            best = fallback
        out = self.evaluate("Maximum Sharpe Ratio", best.x, best.success, best.message)
        if out.sharpe_net <= 0:
            log.warning("Best achievable net Sharpe is %.3f (<= 0): no asset mix "
                        "beats the risk-free rate after frictions", out.sharpe_net)
        return out

    def max_sharpe_constrained(self, name: str, risk_cov: np.ndarray,
                               cap_cov: np.ndarray, cap: float) -> PortfolioResult:
        """Maximise net return / risk under ``risk_cov`` subject to
        sqrt(w' cap_cov w) <= cap (e.g. a ceiling on Crisis-regime volatility).
        Falls back to the minimum-``cap_cov`` portfolio if the cap is infeasible."""
        risk_cov, cap_cov = np.asarray(risk_cov, float), np.asarray(cap_cov, float)

        def neg(w):
            v = np.sqrt(max(w @ risk_cov @ w, 1e-16))
            return -(self.net(w) - self.rf) / v

        cons = [self.sum_to_one,
                {"type": "ineq", "fun": lambda w: cap ** 2 - w @ cap_cov @ w}]
        best = None
        for w0 in self._starts():
            r = minimize(neg, w0, method="SLSQP", bounds=self.bounds, constraints=cons,
                         options={"ftol": 1e-12, "maxiter": 1000})
            feasible = np.sqrt(r.x @ cap_cov @ r.x) <= cap + 1e-6 and abs(r.x.sum() - 1) < 1e-6
            if feasible and np.isfinite(r.fun) and (best is None or r.fun < best.fun):
                best = r
        note = ""
        if best is None:
            log.warning("%s: cap %.1f%% infeasible; using minimum constrained-risk portfolio",
                        name, cap * 100)
            best = minimize(lambda w: w @ cap_cov @ w, np.full(self.n, 1 / self.n),
                            jac=lambda w: 2 * cap_cov @ w, method="SLSQP",
                            bounds=self.bounds, constraints=[self.sum_to_one])
            note = "cap infeasible: minimum constrained-risk portfolio"
        out = self.evaluate(name, best.x, best.success, note or str(best.message))
        w = out.weights.values
        out.extra.update({"capped_vol": float(np.sqrt(w @ cap_cov @ w)),
                          "risk_model_vol": float(np.sqrt(w @ risk_cov @ w)), "cap": cap})
        return out

    def efficient_frontier(self, n_points: int, w_minvar: np.ndarray) -> pd.DataFrame:
        """Minimum volatility for each net-return target on the upper branch."""
        r_lo = self.net(w_minvar)
        lo, hi = self.bounds[0]
        # Highest achievable net return: best single asset at its upper bound
        # (with hi < 1 this is a linear-ish program; solve it numerically).
        res = minimize(lambda w: -self.net(w), np.full(self.n, 1 / self.n),
                       method="SLSQP", bounds=self.bounds, constraints=[self.sum_to_one])
        r_hi = max(-res.fun, r_lo)
        targets = np.linspace(r_lo, r_hi, n_points)

        rows, w_prev = [], w_minvar.copy()
        for k, tgt in enumerate(targets):
            cons = [self.sum_to_one,
                    {"type": "eq", "fun": lambda w, t=tgt: self.net(w) - t}]
            best = None
            for w0 in (w_prev, res.x, np.full(self.n, 1 / self.n)):
                r = minimize(lambda w: w @ self.cov @ w, w0,
                             jac=lambda w: 2 * self.cov @ w, method="SLSQP",
                             bounds=self.bounds, constraints=cons,
                             options={"ftol": 1e-12, "maxiter": 1000})
                if r.success and abs(self.net(r.x) - tgt) < 1e-6 and (best is None or r.fun < best.fun):
                    best = r
            if best is None:
                log.debug("Frontier point %d (target %.4f) did not converge; skipped", k, tgt)
                continue
            w = self._clean(best.x)
            w_prev = w
            v = self.vol(w)
            row = {"Point": k + 1, "Net Return": self.net(w), "Gross Return": self.gross(w),
                   "Volatility": v, "Net Sharpe": (self.net(w) - self.rf) / v}
            row.update({t: wi for t, wi in zip(self.tickers, w)})
            rows.append(row)
        if not rows:
            raise RuntimeError("Efficient frontier: no points converged")
        df = pd.DataFrame(rows)
        log.info("Efficient frontier: %d/%d points converged", len(df), n_points)
        return df


# --------------------------------------------------------------------------
# Monte Carlo forward simulation
# --------------------------------------------------------------------------
@dataclass
class RegimeProcess:
    """Markov regime-switching market for ``simulate``. Arrays are per step."""
    drift: np.ndarray       # (K, N) log drift per step
    chol: np.ndarray        # (K, N, N) Cholesky factor of per-step covariance
    P: np.ndarray           # (K, K) per-step transition matrix
    start: int              # starting regime index
    labels: list


@dataclass
class SimulationResult:
    wealth: np.ndarray          # (n_trials, years+1), end-of-year wealth
    max_drawdown: np.ndarray    # (n_trials,) on the monthly path
    fees_paid: np.ndarray       # (n_trials,)
    taxes_paid: np.ndarray      # (n_trials,)
    regime_share: np.ndarray | None = None   # (n_trials, K) share of steps per regime


def simulate(weights: np.ndarray, mu: np.ndarray, cov: np.ndarray, mc_cfg: dict,
             fr_cfg: dict, apply_frictions: bool = True,
             regime: RegimeProcess | None = None) -> SimulationResult:
    """Simulate wealth paths for a rebalanced portfolio.

    Asset prices follow correlated geometric Brownian motion (or a
    multivariate Student-t with unit variance shocks). Each step:
      1. holdings grow by exp(log-return)
      2. expense ratio accrues: holdings *= (1 - ER) ** dt
      3. on rebalance dates: sell overweights (realising gains under the
         average-cost method), net gains against losses (with optional
         carry-forward), pay tax, and reset to target weights.

    With ``regime`` set, each trial carries a Markov state that switches every
    step according to ``regime.P``; the drift and covariance of that step come
    from the current state, which produces volatility clustering and
    crisis-time correlation shifts that a single covariance matrix cannot.

    The RNG is re-seeded on every call, so gross and net runs, and different
    portfolios, see identical market scenarios (common random numbers).
    """
    n_trials = int(mc_cfg["n_trials"])
    years = int(mc_cfg["horizon_years"])
    spy = int(mc_cfg.get("steps_per_year", 12))
    W0 = float(mc_cfg["initial_capital"])
    dist = mc_cfg.get("distribution", "normal")
    df_t = float(mc_cfg.get("student_t_df", 6))
    reb_every = spy // REBALANCES_PER_YEAR[fr_cfg.get("rebalance_frequency", "annual")]
    if reb_every < 1 or spy % REBALANCES_PER_YEAR[fr_cfg.get("rebalance_frequency", "annual")]:
        raise ValueError("steps_per_year must be a multiple of the rebalance frequency")

    er = float(fr_cfg["expense_ratio"]) if apply_frictions else 0.0
    tax = float(fr_cfg["capital_gains_tax_rate"]) if apply_frictions else 0.0
    carry_fwd = bool(fr_cfg.get("tax_loss_carryforward", True))

    dt = 1.0 / spy
    w = np.asarray(weights, float)
    N = len(w)
    L = np.linalg.cholesky(cov * dt)
    drift = (mu - 0.5 * np.diag(cov)) * dt
    fee_keep = (1 - er) ** dt
    rng = np.random.default_rng(int(mc_cfg.get("seed", 2026)))

    holdings = np.tile(W0 * w, (n_trials, 1))
    basis = holdings.copy()
    carry = np.zeros(n_trials)
    peak = np.full(n_trials, W0)
    max_dd = np.zeros(n_trials)
    fees = np.zeros(n_trials)
    taxes = np.zeros(n_trials)
    wealth = np.empty((n_trials, years + 1))
    wealth[:, 0] = W0
    if regime is not None:
        K = regime.P.shape[0]
        cumP = np.cumsum(regime.P, axis=1)
        cumP[:, -1] = 1.0
        state = np.full(n_trials, int(regime.start))
        occupancy = np.zeros((n_trials, K))

    for step in range(1, years * spy + 1):
        if regime is not None:
            u = rng.random(n_trials)
            state = np.minimum((u[:, None] > cumP[state]).sum(axis=1), K - 1)
            occupancy[np.arange(n_trials), state] += 1
        z = rng.standard_normal((n_trials, N))
        if dist == "student_t":
            g = rng.chisquare(df_t, n_trials) / df_t
            z = z / np.sqrt(g)[:, None] * np.sqrt((df_t - 2) / df_t)
        if regime is None:
            holdings *= np.exp(drift + z @ L.T)
        else:
            logret = np.empty_like(z)
            for k in range(K):
                m = state == k
                if m.any():
                    logret[m] = regime.drift[k] + z[m] @ regime.chol[k].T
            holdings *= np.exp(logret)

        if er > 0:
            fees += holdings.sum(1) * (1 - fee_keep)
            holdings *= fee_keep

        if step % reb_every == 0:
            V = holdings.sum(1)
            target = V[:, None] * w
            sell = np.maximum(holdings - target, 0.0)
            buy = np.maximum(target - holdings, 0.0)
            with np.errstate(divide="ignore", invalid="ignore"):
                frac = np.where(holdings > 0, sell / holdings, 0.0)
            realised = (frac * (holdings - basis)).sum(1)
            basis = basis * (1 - frac) + buy
            holdings = target
            if tax > 0:
                net = realised + carry
                taxable = np.maximum(net, 0.0)
                carry = np.minimum(net, 0.0) if carry_fwd else np.zeros(n_trials)
                t_due = tax * taxable
                taxes += t_due
                # Pay tax pro rata, keeping weights at target. Basis scales with
                # holdings (the gain on this small funding sale is ignored).
                scale = np.where(V > 0, (V - t_due) / V, 0.0)
                holdings *= scale[:, None]
                basis *= scale[:, None]

        V = holdings.sum(1)
        peak = np.maximum(peak, V)
        max_dd = np.minimum(max_dd, V / peak - 1)
        if step % spy == 0:
            wealth[:, step // spy] = V

    if not np.isfinite(wealth).all():
        raise FloatingPointError("Non-finite wealth values in simulation")
    share = occupancy / (years * spy) if regime is not None else None
    return SimulationResult(wealth, max_dd, fees, taxes, share)


def risk_metrics(net: SimulationResult, gross: SimulationResult, mc_cfg: dict,
                 confidence: float = 0.95) -> dict:
    W0 = float(mc_cfg["initial_capital"])
    years = int(mc_cfg["horizon_years"])
    T = net.wealth[:, -1]
    Tg = gross.wealth[:, -1]
    cagr = (T / W0) ** (1 / years) - 1
    r1 = net.wealth[:, 1] / W0 - 1
    q = 1 - confidence
    var1 = -np.quantile(r1, q)
    cvar1 = -r1[r1 <= np.quantile(r1, q)].mean()
    loss_T = W0 - T
    varT = np.quantile(loss_T, confidence)
    cvarT = loss_T[loss_T >= varT].mean()
    leak = Tg - T
    m = {
        "Initial Capital": W0,
        "Mean Terminal Wealth": T.mean(),
        "Std Dev Terminal Wealth": T.std(),
    }
    for p in (5, 10, 25, 50, 75, 90, 95):
        m[f"P{p} Terminal Wealth"] = np.percentile(T, p)
    for p in (10, 50, 90):
        m[f"P{p} CAGR"] = np.percentile(cagr, p)
    m.update({
        "Probability of Loss (Terminal < Initial)": float((T < W0).mean()),
        "Probability of Doubling": float((T >= 2 * W0).mean()),
        f"1-Year VaR {confidence:.0%} (return)": var1,
        f"1-Year CVaR {confidence:.0%} (return)": cvar1,
        f"{years}-Year VaR {confidence:.0%} ($ loss vs initial)": varT,
        f"{years}-Year CVaR {confidence:.0%} ($ loss vs initial)": cvarT,
        "Median Max Drawdown": np.median(net.max_drawdown),
        "P90 Max Drawdown (worst 10%)": np.percentile(net.max_drawdown, 10),
        "Median Terminal Wealth (no frictions)": np.median(Tg),
        "Median Fees Paid": np.median(net.fees_paid),
        "Median Taxes Paid": np.median(net.taxes_paid),
        "Median Friction Leakage ($)": np.median(leak),
        "Median Friction Leakage (% of gross wealth)": np.median(leak / Tg),
    })
    return m


def percentile_paths(sim: SimulationResult, percentiles) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(a) Cross-sectional percentile bands per year and (b) the actual
    simulated trial whose terminal wealth sits at each percentile."""
    years = np.arange(sim.wealth.shape[1])
    bands = pd.DataFrame({"Year": years})
    reps = pd.DataFrame({"Year": years})
    T = sim.wealth[:, -1]
    order = np.argsort(T)
    for p in percentiles:
        bands[f"P{p} Band"] = np.percentile(sim.wealth, p, axis=0)
        idx = order[int(round(p / 100 * (len(T) - 1)))]
        reps[f"P{p} Path (trial {idx})"] = sim.wealth[idx]
    return bands, reps
