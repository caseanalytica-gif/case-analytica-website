# VIX-Centred Portfolio Optimization and Risk Model

A modular Python pipeline built around the VIX. It classifies every day of the
last ten years into a VIX regime, estimates how each asset behaves in each
regime, and uses that to:

* report today's VIX state and the odds of reaching a Crisis regime,
* build a portfolio whose Crisis-regime volatility is capped,
* run a regime-switching Monte Carlo that starts from today's regime,
* stress-test every portfolio regime by regime,
* backtest VIX-based exposure rules and a VIXY hedge sleeve,
* automate the weekly and daily coefficient tables from the VIX Algo
  workbooks and test whether they predict anything,
* study what happens after the VIX rises versus falls within a day or week,
  and which non-VIX instruments respond.

Underneath sits the original long-only mean-variance model (Max Sharpe and
Min Variance on returns net of a 0.07% expense ratio and 15% rebalancing tax,
an efficient frontier, and a 10,000-trial 20-year Monte Carlo).

```
portfolio-model/
├── config.json        every parameter; the "vix" section drives the VIX model
├── data_loader.py     cached multi-field downloads, cleaning, quality screen
├── optimizer.py       moments, frictions, MVO, constrained Sharpe, Monte Carlo
├── vix_model.py       regimes, dashboard, stress test, backtests, signal tests,
│                      weekly tables, Difference study
├── exporter.py        Excel workbook, VIX tabs first, native charts
├── main.py            orchestration and console summary
└── portfolio_model_output.xlsx   generated output (21 tabs)
```

## How to run

```bash
cd portfolio-model
python3 -m venv venv
venv/bin/pip install pandas numpy yfinance scipy openpyxl
venv/bin/python main.py
```

| Flag | Effect |
|---|---|
| `--config path.json` | use another config file |
| `--refresh` | ignore the 24-hour price cache |

Exit code 0 on success, 1 on failure with a full stack trace. A run takes about
20 seconds. yfinance needs `query1.finance.yahoo.com`,
`query2.finance.yahoo.com` and `fc.yahoo.com` to be reachable.

## Why the VIX is used this way

The VIX is the 30-day implied volatility of the S&P 500, computed from SPX
option prices. It cannot be bought. The tradable products (VIXY, VXX, UVXY)
hold VIX futures, and rolling those futures costs most of their value over
time: VIXY returned -99.8% over the last ten years. So the model treats the VIX
as information first and as an asset second.

The data then decides where that information is useful. VIX is a strong *risk*
forecaster: its correlation with next-month realized SPY volatility is 0.60,
and it overstates that volatility on 84% of days (the volatility risk premium).
It is a weak *direction* forecaster: after Crisis-regime closes, SPY's next
month averaged +3.9%, the opposite of what a "sell when VIX spikes" rule needs.
That is why the VIX drives the risk side of the model (covariance, stress,
Monte Carlo) and why every timing rule is backtested instead of assumed.

## Changing assets and parameters

Edit `tickers` in `config.json`. Any Yahoo symbol works. Each ticker needs
`vix.regime_lookback_years` (default 10) of clean history, or the run stops
with a message telling you to shorten the window. VIXY is in the default list
as the investable VIX exposure. Remove it to optimise without a VIX product.

Main `vix` settings:

| Key | Default | Meaning |
|---|---|---|
| `regime_thresholds` / `regime_labels` | 15, 20, 30 / Calm, Normal, Elevated, Crisis | VIX bands |
| `regime_lookback_years` | 10 | window for regimes (covers 2018, 2020, 2022, 2025 stress) |
| `regime_mean_shrinkage` | 1.0 | 1 = regimes change risk only; 0 = use raw regime means |
| `regime_calibrate_to_base` | true | rescale regime covariances to the base model's volatilities |
| `crisis_vol_cap` | 0.20 | Crisis-regime volatility ceiling for the constrained portfolio |
| `hedge_asset` / `hedge_sizes` | VIXY / 0 to 20% | hedge sizing grid |
| `overlay` | see file | exposure rules and costs for the backtest |
| `stress_windows` | COVID, 2022, Aug 2024, Apr 2025 | dated windows reported in backtests |
| `weekly.series` | VIX, NG=F, ^TNX, GC=F, CL=F, DJP | coefficient-table series |
| `difference_study` | since 2010, 12 instruments | Difference event study |

The base model's settings (lookback, risk-free rate, frictions, Monte Carlo
size) are unchanged and documented in the table at the end.

## Methodology: VIX model (`vix_model.py`)

### Regimes

Each day is labelled by its VIX close: Calm (< 15), Normal (15 to 20),
Elevated (20 to 30), Crisis (>= 30). Over the ten-year window that gives 832,
897, 630 and 154 days. For each regime the model estimates annualised mean
returns and a Ledoit-Wolf shrunk covariance from the days in that regime.
SPY's volatility runs from about 8% in Calm to 46% in Crisis, which is the
point of the exercise: one covariance matrix cannot represent both.

**Calibration.** The regime window is ten years and the base model five, and
the two disagree on some volatilities (GLD: 16.6% vs 19.1%). Without a fix,
any difference between the regime and static Monte Carlo would come partly
from the window. Each regime covariance is therefore rescaled by
D = diag(sigma_base / sigma_mix), where sigma_mix is the volatility of the
stationary regime mixture. The mixture then matches the base model asset by
asset, while regime correlations and the ratios between regimes are kept.

### Transitions

Two matrices are estimated:

* **Daily chain** P from consecutive days. Used for first-passage odds ("a
  Crisis day within N days") by making Crisis absorbing and raising P to N.
* **One-month matrix** from observed pairs (state_t, state_t+21) over all
  overlapping days. The Monte Carlo uses this one.

The daily chain is memoryless, so compounding it 21 times forgets regimes far
too quickly. It puts Calm-to-Calm after one month at 42%, against 70%
observed, and Crisis-to-Crisis at 10% against 29%. Using it would erase the
volatility clustering the regime model exists to capture. The dashboard prints
every Markov first-passage probability next to the historical frequency from
the same starting regime, as a check (34% vs 37% at one month, 93% vs 84% at
twelve).

### Current state (VIX Dashboard)

VIX and VIX3M levels, the term structure (VIX / VIX3M above 1 means
backwardation, a stress signal), the current regime and its run length, the
VIX percentile, implied minus realized volatility, regime odds at 1, 3 and 12
months, and each portfolio's volatility and one-month 95% VaR under today's
regime. The key findings at the top are generated from the computed numbers,
so they update on every run.

### VIX Crisis-Constrained portfolio

Maximise net Sharpe on the base model's moments subject to
sqrt(w' Sigma_crisis w) <= `crisis_vol_cap`. With a 20% cap it holds Crisis
volatility at exactly 20.0% (Max Sharpe: 26.1%) with a 6.5% VIXY sleeve, for
11.7% expected net return against Max Sharpe's 15.2%. If the cap cannot be
met, the minimum Crisis-volatility portfolio is used and a warning logged.

### Regime-switching Monte Carlo

Same engine as the base simulation (monthly steps, annual rebalancing,
average-cost tax, expense drag, common random numbers) with one addition:
every trial carries a regime that switches each month by the one-month matrix,
starting from today's regime, and that month's returns come from that regime's
covariance. With `regime_mean_shrinkage` = 1 every regime earns the base
expected return, because regime return differences are not statistically
reliable (see Signal Tests).

Over 20 years the two simulations end in nearly the same place, as they
should: regime swings average out across 240 months. The regime model shows
up in near-term tail risk. For Max Sharpe, 1-year CVaR is 15.5% vs 14.5%
static, and the worst-decile drawdown is -33.8% vs -32.3%.

### Stress test

Each portfolio's return, volatility and parametric one-month 95% VaR in every
regime and in the stationary mixture.

### VIX rule backtest

Three exposure rules, each using the previous day's close: a VIX vol target
(exposure = trailing one-year median VIX / VIX, capped at 1), a term-structure
switch (50% exposure in backwardation), and a regime map (100/100/75/50%).
The risky sleeve rebalances monthly, unused capital earns 13-week T-bills, and
costs are 5 bps per unit of exposure change and of rebalancing turnover. On the
base portfolios no rule reliably beat static holding. On SPY alone the
term-structure switch lifted Sharpe from 0.73 to 0.79 and cut the maximum
drawdown from -33.7% to -27.0%.

### VIXY hedge sizing

Blends 0 to 20% VIXY into Max Sharpe and reports the expected-return cost
against the reduction in Crisis volatility and in historical stress windows.
A 5% sleeve cuts Crisis volatility from 26.1% to 21.3% and costs 2.5% a year.

### Signal tests

Forward 21-day SPY returns and realized volatility after each regime and
term-structure state, with t-stats on non-overlapping months.

### Weekly and daily coefficient tables (from the VIX Algo workbooks)

Rebuilt from live data with the workbooks' formulas: weekly and daily % change
of VIX, natural gas (NG=F), the 10-year yield (^TNX), gold (GC=F), oil (CL=F)
and DJP (the Bloomberg Commodity Index, formerly Dow Jones-UBS, standing in
for the Dow Jones Commodity index, which Yahoo does not carry); Spread Total =
sum of the six; Average = Spread Total / 6; Difference = VIX close - VIX open;
STD = STDEV(open, close). Also produced: 6x6 correlation matrices (weekly and
daily, winsorised 1%/99%), each series' correlation and beta to the VIX, and a
predictive test of the Average.

The workbooks' hand-entered values do not line up with the dates they carry.
The "4/29/24" daily block holds the VIX open, close and % change of 5/1/24.
The "1/3/24" block shows oil -2.96% on a day oil rose 3.3%. The automated
tables use fixed definitions (Friday-to-Friday weekly, close-to-close daily)
and will not match those cells.

Spread Total result: correlation with next-week SPY return -0.096 (t = -2.18,
519 weeks), with the same sign in both halves of the sample. The VIX change
alone has no such link (+0.006), so what little signal exists comes from the
commodity and yield legs. It explains under 1% of next-week variance.

### Implied vs historical volatility

IV = VIX / 100; HV = SPY 21-day realized volatility, annualised. IV Rank and
HV Rank place today's value in its trailing 52-week range (0 to 100). The
"Sheet2" sample in the workbook steps in exact increments and includes weekend
dates, so it looks like placeholder data. This tab computes the real series.

### Difference study

The question: when the Difference (VIX close minus open) is positive versus
negative, what does the VIX do next, and which non-VIX instrument can use it?
The study runs from 2010, because Yahoo's VIX open copies the prior close on
about 30% of days in 2008 and 2009. Each period is bucketed (big rise = top
10% of intraday VIX moves, rose, fell, big fall) and every instrument's
next-period return is compared with all other periods (Welch t-stat) and
checked for the same sign in both halves of the sample. Backtests set the
"big rise" bar from a trailing window, so there is no look-ahead.

Findings:

* **Rises revert, falls do not.** After an up week the VIX was lower the
  following week 64% of the time (75% after big rises, median -8.1%). After a
  down week, 50%. Daily: 57% and 64% after rises, 53% after falls.
* **Equities bounce the next day after big VIX rises.** IWM +0.21% vs other
  days (t = 2.5), QQQ +0.17% (t = 2.0), SPY +0.14% (t = 1.9), stable in both
  halves. As standalone trades they beat an average day but sit in cash 90%
  of the time, so their Sharpe trails buy-and-hold (SPY 0.59 vs 0.81). Their
  practical use is timing: add equity exposure or rebalance into equities on
  big VIX-rise days, rather than trading in and out.
* **The dollar firms the week after big VIX rises.** UUP +0.31% vs other
  weeks (t = 2.7), stable in both halves but weaker since 2018. The rule
  "long UUP for a week after a big VIX rise" had Sharpe 0.49 against 0.17 for
  holding UUP. Commodities (DJP, USO) lean negative the same week but are not
  significant.
* **The direct non-VIX expression** of "VIX falls after it spikes" is selling
  SPX or SPY option premium (puts, put spreads, strangles) after a spike, since
  the VIX is computed from those options. Yahoo carries no historical option
  prices, so that trade is not tested here, and short premium carries large
  tail losses (February 2018, March 2020).
* About 24 instrument tests were run on big rises, so one |t| > 2 is expected
  by chance alone. Treat the results as candidates to monitor, not proven
  edges.

## Methodology: base model

### Data cleaning (`data_loader.py`)

Adjusted closes from yfinance with exponential-backoff retries and a 24-hour
disk cache. Non-positive and infinite prices become NaN. Tickers below
`min_coverage` are dropped. A quality screen drops tickers with more than 25%
unchanged days (untraded shells) or any one-day move above 75% (bad split
adjustments). BIOM, in the original spec, fails it: a 1-for-20,000 reverse
split and 68% stale days. ARKK replaces it. Gaps of up to 5 days are
forward-filled, then rows are trimmed to dates where every asset has a price.

### Moments

mu = 252 x mean daily return. Covariance uses Ledoit-Wolf shrinkage of the
correlation matrix toward the identity, so each asset's own variance stays
exact.

### Frictions

mu_net(w) = w' mu - 0.07% - TaxDrag(w). TaxDrag is the expected 15% tax on
the gains realised when rebalancing overweight positions back to target,
estimated from 4,000 fixed lognormal draws so the optimiser sees a smooth
function. The Monte Carlo tracks the true average-cost basis.

### Optimisation

SLSQP under sum(w) = 1 and 0 <= w_i <= 1. Min Variance is a convex QP. Max
Sharpe and the Crisis-Constrained portfolio use about 27 starting points,
because the tax term is non-convex. The efficient frontier holds 40 points in
net-return space.

### Monte Carlo

10,000 trials of 240 monthly steps of correlated GBM (optional Student-t),
with expense accrual, annual rebalancing, average-cost capital gains tax with
loss carryforward, and common random numbers across gross and net runs. Output
includes P10, P50 and P90 bands, the actual P10, P50 and P90 trial paths,
VaR, CVaR, drawdowns and friction leakage. With monthly rebalancing and no
frictions the simulated median matches the closed-form value to within 0.3%.

| Base key | Default |
|---|---|
| `data.lookback_years` | 5 |
| `model.risk_free_rate` | 0.04 |
| `model.covariance_method` | ledoit_wolf |
| `frictions.expense_ratio` / `capital_gains_tax_rate` | 0.0007 / 0.15 |
| `frictions.rebalance_frequency` | annual |
| `monte_carlo.n_trials` / `horizon_years` | 10000 / 20 |
| `monte_carlo.initial_capital` | 1000000 |

## Workbook tabs

| Tab | Contents |
|---|---|
| VIX Dashboard | findings, current VIX state, regime odds, portfolio risk now, VIX history chart |
| Summary | all three portfolios: returns, drags, base and Crisis volatility, weights, MC results |
| VIX Regimes | regime frequency, persistence, per-regime asset returns, volatility, correlation; transition matrices |
| Regime Stress Test | each portfolio in each regime |
| Regime Monte Carlo | regime-switching vs static metrics and percentile charts |
| VIX Rule Backtest | static vs three VIX rules, stress windows, growth-of-$1 chart |
| VIX Hedge Sizing | 0 to 20% VIXY sleeve trade-off |
| VIX Weekly Coefficients | workbook tables (two weekly, one daily), correlation matrices, betas, predictive test, last 52 weeks with direction and next-week VIX change |
| VIX Difference Study | positive vs negative Difference: VIX behaviour, instrument responses, backtests |
| Implied vs Historical Vol | IV, HV, ranks, 12-month chart |
| Signal Tests | VIX as a volatility forecaster and as a return signal |
| Optimal Weights, Efficient Frontier, Monte Carlo Metrics, Wealth Paths (x3) | base model |
| Asset Statistics, Correlation & Covariance, VIX History, Assumptions | reference |

## Limitations

* Expected returns are five-year trailing means. GLD's strong run drives the
  Max Sharpe weights, and both optimised portfolios inherit that in-sample
  bias. The backtests use the same weights, so they isolate the VIX rules, not
  the weights.
* Regime-conditional returns rest on few observations (154 Crisis days, 8
  non-overlapping Crisis months) and are not used for forecasting by default.
* The Difference study and coefficient tests involve many comparisons. A
  result needs |t| of about 3 to survive a strict multiple-testing correction,
  and none reach it.
* Option-based volatility trades cannot be tested without option price
  history.
