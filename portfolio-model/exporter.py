"""Multi-tab Excel export with formatting and native Excel charts.

Tab order puts the VIX analysis first: Dashboard, regimes, stress test,
regime Monte Carlo, rule backtests, hedge sizing, weekly coefficients, signal
tests; then the base mean-variance model and reference tabs.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl.chart import LineChart, Reference, ScatterChart, Series
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

HEADER_FILL = PatternFill("solid", fgColor="1F3864")
HEADER_FONT = Font(bold=True, color="FFFFFF")
TITLE_FONT = Font(bold=True, size=14, color="1F3864")
SUB_FONT = Font(bold=True, size=12, color="1F3864")
ALERT_FILL = PatternFill("solid", fgColor="FCE4D6")
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

PCT, MONEY, NUM, RATIO, PTS = "0.00%", '"$"#,##0', "#,##0", "0.000", "0.00"
SHORT = {"Maximum Sharpe Ratio": "MaxSharpe", "Minimum Variance": "MinVar",
         "VIX Crisis-Constrained": "VIXCrisis"}


def _short(name: str) -> str:
    return SHORT.get(name, "".join(ch for ch in name if ch.isalnum())[:14])


def _fmt_for(label: str, value) -> str | None:
    """Number format from a row/column label."""
    if not isinstance(value, (int, float, np.integer, np.floating)) or isinstance(value, bool):
        return None
    l = str(label).lower()
    if "$" in l:
        return MONEY
    if any(s in l for s in ("sharpe", "t-stat", "calmar", "beta", "corr", "shrinkage", "ratio",
                            "slope", "stationary")):
        return RATIO
    if "(pts)" in l:
        return PTS
    if any(s in l for s in ("probability", "p(", "percentile", "share", "hit rate", "cagr", "return",
                            "drawdown", "(%", "drag", "volatility", "vol ", " vol", "weight",
                            "month", "exposure", "de-risked", "turnover", "var ", "var 9",
                            "cvar", "spread", "excess", "change", "move", "time in market")):
        return PCT
    if any(s in l for s in ("wealth", "capital", "paid", "leakage")):
        return MONEY
    if l.startswith("vix"):
        return PTS                                # VIX levels are in index points
    if any(s in l for s in ("days", "weeks", "months", "tested", "point")):
        return NUM
    return PTS if isinstance(value, float) else None


def _style_header(ws, row, c1, c2):
    for c in range(c1, c2 + 1):
        cell = ws.cell(row=row, column=c)
        cell.fill, cell.font, cell.border = HEADER_FILL, HEADER_FONT, BORDER
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[row].height = 32


def _autowidth(ws, min_w=10, max_w=46):
    widths = {}
    for row in ws.iter_rows(min_row=1, max_row=min(ws.max_row, 120)):
        for c in row:
            if c.value is not None:
                n = len(f"{c.value:,.2f}") if isinstance(c.value, float) else len(str(c.value))
                widths[c.column_letter] = max(widths.get(c.column_letter, 0), n)
    for col, w in widths.items():
        ws.column_dimensions[col].width = min(max(min_w, w + 2), max_w)


def _write_df(ws, df: pd.DataFrame, r0: int, c0: int = 1, formats: dict | None = None,
              index: bool = False) -> int:
    """Write a styled table; column formats inferred from header names unless
    given. Returns the next free row."""
    if index:
        df = df.reset_index()
    cols = list(df.columns)
    for j, h in enumerate(cols):
        ws.cell(row=r0, column=c0 + j, value=str(h))
    _style_header(ws, r0, c0, c0 + len(cols) - 1)
    for i, row in enumerate(df.itertuples(index=False), 1):
        for j, v in enumerate(row):
            if isinstance(v, (np.floating, np.integer)):
                v = v.item()
            if isinstance(v, pd.Timestamp):
                v = v.to_pydatetime()
            if isinstance(v, float) and not np.isfinite(v):
                v = None
            cell = ws.cell(row=r0 + i, column=c0 + j, value=v)
            cell.border = BORDER
            fmt = (formats or {}).get(cols[j]) or _fmt_for(cols[j], v)
            if hasattr(v, "year") and not isinstance(v, (int, float)):
                fmt = "yyyy-mm-dd"
            if fmt:
                cell.number_format = fmt
    return r0 + len(df) + 2


def _write_kv(ws, items, r0: int, title: str | None = None, c0: int = 1,
              highlight: set | None = None) -> int:
    r = r0
    if title:
        ws.cell(row=r, column=c0, value=title).font = SUB_FONT
        r += 1
    for k, v in items:
        if isinstance(v, (np.floating, np.integer)):
            v = v.item()
        kc = ws.cell(row=r, column=c0, value=k)
        vc = ws.cell(row=r, column=c0 + 1, value=v)
        kc.border = vc.border = BORDER
        fmt = _fmt_for(k, v)
        if fmt:
            vc.number_format = fmt
        if highlight and k in highlight:
            kc.fill = vc.fill = ALERT_FILL
        r += 1
    return r + 1


def _line_chart(ws, title, y_title, data_ref, cats_ref, anchor, fmt='"$"#,##0', h=9, w=18):
    lc = LineChart()
    lc.title, lc.y_axis.title = title, y_title
    lc.y_axis.number_format = fmt
    lc.x_axis.delete = lc.y_axis.delete = False
    lc.add_data(data_ref, titles_from_data=True)
    lc.set_categories(cats_ref)
    lc.height, lc.width = h, w
    for s in lc.series:
        s.smooth = False
        s.graphicalProperties.line.width = 15000
    ws.add_chart(lc, anchor)
    return lc


# --------------------------------------------------------------------------
# VIX tabs
# --------------------------------------------------------------------------
def _vix_dashboard(wb, cfg, portfolios, vix, mc_regime):
    ws = wb.create_sheet("VIX Dashboard")
    st = vix["state"]
    ws["A1"] = "VIX Dashboard"
    ws["A1"].font = TITLE_FONT
    ws["A2"] = (f"As of {st['As of']}. Regimes by VIX close: "
                + ", ".join(f"{l}" + (f" < {t}" if i < len(vix['thresholds']) else f" >= {vix['thresholds'][-1]}")
                            for i, (l, t) in enumerate(zip(vix["labels"], vix["thresholds"] + [None]))))
    r = 4
    ws.cell(row=r, column=1, value="Key findings (generated from the numbers below)").font = SUB_FONT
    for i, line in enumerate(vix["findings"], 1):
        c = ws.cell(row=r + i, column=1, value=f"{i}. {line}")
        c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.merge_cells(start_row=r + i, start_column=1, end_row=r + i, end_column=6)
        ws.row_dimensions[r + i].height = 30
    r += len(vix["findings"]) + 2

    first = [(k, v) for k, v in st.items() if not k.startswith("P(")]
    probs = [(k, v) for k, v in st.items() if k.startswith("P(")]
    alert = {"Term structure", "Current regime"} if st["VIX / VIX3M ratio"] > 1 or \
        st["Current regime"] in vix["labels"][-2:] else set()
    r_left = _write_kv(ws, first, r, "Current VIX state", highlight=alert)
    _write_kv(ws, probs, r, "Regime odds from today", c0=4)
    r = max(r_left, r + len(probs) + 2)

    ws.cell(row=r, column=1, value="Portfolio risk under the current regime").font = SUB_FONT
    st_df = vix["stress"]
    rows = []
    for p in portfolios:
        cur = st_df[(st_df["Portfolio"] == p.name) & st_df["Regime"].str.endswith("(current)")].iloc[0]
        rows.append({"Portfolio": p.name, "Base-model volatility": p.volatility,
                     "Current-regime volatility": cur["Ann. volatility in regime"],
                     "Crisis-regime volatility": p.extra["crisis_vol"],
                     "1-month VaR 95% now ($)": cur["1-month VaR 95% ($)"],
                     "P10 20y wealth, VIX regime MC ($)": mc_regime[p.name][0]["P10 Terminal Wealth"],
                     "P50 20y wealth, VIX regime MC ($)": mc_regime[p.name][0]["P50 Terminal Wealth"]})
    r = _write_df(ws, pd.DataFrame(rows), r + 1)

    # VIX history chart (weekly), data in a side block.
    hist = pd.DataFrame({"VIX": vix["vix"], "VIX3M": vix["vix3m"]}).resample("W-FRI").last().dropna()
    for t in vix["thresholds"]:
        hist[f"{t} line"] = float(t)
    hist.index.name = "Week"
    hs = wb.create_sheet("VIX History")
    hs["A1"] = "Weekly VIX and VIX3M closes (data for the dashboard chart)"
    hs["A1"].font = SUB_FONT
    _write_df(hs, hist.reset_index(), 3, formats={"Week": "yyyy-mm-dd"})
    _autowidth(hs, min_w=12)
    n = len(hist)
    _line_chart(ws, "VIX and VIX3M, weekly closes, with regime thresholds", "Index level",
                Reference(hs, min_col=2, max_col=1 + hist.shape[1], min_row=3, max_row=n + 3),
                Reference(hs, min_col=1, min_row=4, max_row=n + 3), f"A{r + 1}", fmt="0", h=10, w=26)
    ws.column_dimensions["A"].width = 48
    ws.column_dimensions["B"].width = 30
    ws.column_dimensions["D"].width = 52
    ws.column_dimensions["E"].width = 14
    for c in "CFG":
        ws.column_dimensions[c].width = 22


def _vix_tabs(wb, xw, cfg, portfolios, vix, mc, mc_regime):
    # Regimes
    ws = wb.create_sheet("VIX Regimes")
    ws["A1"] = "VIX regimes: frequency, persistence and asset behaviour"
    ws["A1"].font = TITLE_FONT
    ws["A2"] = (f"{cfg['vix']['regime_lookback_years']}-year window. Returns and covariances are measured "
                "on days when the VIX close sat in each band (contemporaneous).")
    r = _write_df(ws, vix["regimes"], 4)
    ws.cell(row=r, column=1, value="Daily transition matrix").font = SUB_FONT
    r = _write_df(ws, vix["trans_1d"], r + 1, index=True, formats={c: PCT for c in vix["trans_1d"].columns})
    ws.cell(row=r, column=1, value="One-month transition matrix, observed 21-day-ahead pairs (used by the Monte Carlo)").font = SUB_FONT
    r = _write_df(ws, vix["trans_1m"], r + 1, index=True, formats={c: PCT for c in vix["trans_1m"].columns})
    ws.cell(row=r, column=1, value=("For comparison: daily matrix compounded 21 times. It forgets regimes too fast "
                                    "(memoryless), which is why the Monte Carlo does not use it.")).font = SUB_FONT
    _write_df(ws, vix["trans_1m_markov"], r + 1, index=True, formats={c: PCT for c in vix["trans_1m_markov"].columns})
    _autowidth(ws)
    ws.column_dimensions["A"].width = 18
    ws.freeze_panes = "B5"

    # Stress test
    ws = wb.create_sheet("Regime Stress Test")
    ws["A1"] = "Portfolio behaviour in each VIX regime"
    ws["A1"].font = TITLE_FONT
    ws["A2"] = ("Regime returns are what these weights earned while VIX was in that band; they are noisy "
                "(see Signal Tests). Volatility and VaR are the reliable part.")
    _write_df(ws, vix["stress"], 4)
    _autowidth(ws)

    # Regime Monte Carlo
    ws = wb.create_sheet("Regime Monte Carlo")
    ws["A1"] = "Monte Carlo: VIX regime-switching vs static covariance"
    ws["A1"].font = TITLE_FONT
    ws["A2"] = (f"{cfg['monte_carlo']['n_trials']:,} trials, {cfg['monte_carlo']['horizon_years']} years, "
                f"starting in today's regime ({vix['state']['Current regime']}). Each month the regime "
                "switches by the fitted Markov chain and draws from that regime's covariance. "
                f"regime_mean_shrinkage = {cfg['vix']['regime_mean_shrinkage']}.")
    keys = list(mc_regime[portfolios[0].name][0].keys())
    rows = []
    for k in keys:
        row = {"Metric": k}
        for p in portfolios:
            row[f"{p.name} | VIX regime"] = mc_regime[p.name][0].get(k)
            row[f"{p.name} | static"] = mc[p.name][0].get(k)
        rows.append(row)
    met = pd.DataFrame(rows)
    r = 4
    for i, k in enumerate(keys):
        pass
    # write with row-label based formatting
    cols = list(met.columns)
    for j, h in enumerate(cols, 1):
        ws.cell(row=r, column=j, value=h)
    _style_header(ws, r, 1, len(cols))
    for i, row in enumerate(met.itertuples(index=False), 1):
        for j, v in enumerate(row, 1):
            v = None if isinstance(v, float) and not np.isfinite(v) else v
            c = ws.cell(row=r + i, column=j, value=v)
            c.border = BORDER
            if j > 1:
                c.number_format = _fmt_for(row[0], v) or NUM
    r = r + len(met) + 3
    ws.column_dimensions["A"].width = 46
    for j in range(2, len(cols) + 1):
        ws.column_dimensions[get_column_letter(j)].width = 22
    for p in portfolios:
        b = mc_regime[p.name][1]
        sb = mc[p.name][1].rename(columns=lambda c: c if c == "Year" else f"{c} (static)")
        comb = b.rename(columns=lambda c: c if c == "Year" else f"{c} (VIX regime)").merge(sb, on="Year")
        ws.cell(row=r, column=1, value=p.name).font = SUB_FONT
        top = r + 1
        nxt = _write_df(ws, comb, top, formats={c: MONEY for c in comb.columns if c != "Year"} | {"Year": NUM})
        _line_chart(ws, f"{p.name}: wealth percentiles, VIX regime vs static", "Portfolio value",
                    Reference(ws, min_col=2, max_col=comb.shape[1], min_row=top, max_row=top + len(comb)),
                    Reference(ws, min_col=1, min_row=top + 1, max_row=top + len(comb)),
                    f"{get_column_letter(comb.shape[1] + 2)}{top}", h=8, w=20)
        r = max(nxt, top + 18)

    # Overlay backtest
    ws = wb.create_sheet("VIX Rule Backtest")
    ws["A1"] = "Do VIX-based exposure rules improve the portfolios?"
    ws["A1"].font = TITLE_FONT
    oc = cfg["vix"]["overlay"]
    ws["A2"] = ("Signals use the previous day's close (no look-ahead). Unused capital earns 13-week T-bills. "
                f"Costs {oc['cost_bps']} bps per unit of exposure change and of rebalancing turnover. "
                "Portfolio weights come from the base optimisation, so both arms share the same in-sample weights; "
                "the comparison isolates the VIX rule.")
    ws["A3"] = ("Rules: VIX vol-target = exposure trailing-1y median VIX / VIX (capped at "
                f"{oc['max_exposure']}); Term-structure switch = {oc['backwardation_exposure']} when VIX > VIX3M; "
                "Regime map = " + ", ".join(f"{k} {v}" for k, v in oc["regime_exposure"].items()) + ".")
    r = _write_df(ws, vix["backtest"], 5)
    cur = vix["curves"].resample("W-FRI").last()
    cols = [c for c in cur.columns if c.startswith(portfolios[0].name) or c.startswith("SPY only | Static")]
    sub = cur[cols].reset_index().rename(columns={"index": "Week"})
    sub.columns = ["Week"] + [c.replace(portfolios[0].name + " | ", "") for c in cols]
    top = r + 1
    ws.cell(row=r, column=1, value=f"Growth of $1: {portfolios[0].name} under each rule (weekly)").font = SUB_FONT
    _write_df(ws, sub, top, formats={c: "0.000" for c in sub.columns if c != "Week"} | {"Week": "yyyy-mm-dd"})
    _line_chart(ws, f"Growth of $1: {portfolios[0].name}, static vs VIX rules", "Growth of $1",
                Reference(ws, min_col=2, max_col=sub.shape[1], min_row=top, max_row=top + len(sub)),
                Reference(ws, min_col=1, min_row=top + 1, max_row=top + len(sub)),
                f"{get_column_letter(sub.shape[1] + 2)}{top}", fmt="0.00", h=10, w=24)
    _autowidth(ws)
    ws.column_dimensions["A"].width = 26
    ws.column_dimensions["B"].width = 26

    # Hedge sizing
    ws = wb.create_sheet("VIX Hedge Sizing")
    ws["A1"] = f"Cost and benefit of a {cfg['vix']['hedge_asset']} (long VIX futures) sleeve on {portfolios[0].name}"
    ws["A1"].font = TITLE_FONT
    ws["A2"] = ("Model columns use the base 5-year moments with frictions; Crisis volatility uses the Crisis-regime "
                "covariance; Backtest columns are the regime window, monthly rebalanced.")
    if len(vix["hedge"]):
        _write_df(ws, vix["hedge"], 4)
    _autowidth(ws)

    # Weekly coefficients (automates the VIX Algo workbook)
    wk = vix["weekly"]
    ws = wb.create_sheet("VIX Weekly Coefficients")
    ws["A1"] = "Weekly cross-asset coefficient table (automated from the VIX Algo workbook)"
    ws["A1"].font = TITLE_FONT
    ws["A2"] = ("Weekly % change, Friday close to Friday close. Spread Total = average of the six changes "
                "(the workbook's formula). STD = STDEV(open, close) of the week, as in the workbook. "
                "10 Yr Bond is the % change in the 10-year yield (^TNX); DOW Jones Commodity uses DJP "
                "(Bloomberg Commodity Index, formerly Dow Jones-UBS).")
    tbl = wk["table"]
    blocks = [("Coefficient Table", dt, row) for dt, row in tbl.iloc[-2:].iterrows()]
    blocks.append(("Coefficient Table   DAILY", wk["daily"].index[-1], wk["daily"].iloc[-1]))
    r = 4
    for j, (title, dt, row) in enumerate(blocks):
        c0 = 1 + j * 3
        ws.cell(row=r, column=c0, value=title).font = SUB_FONT
        items = [("Date", dt.to_pydatetime())] + [(k, row[k]) for k in tbl.columns]
        for i, (k, v) in enumerate(items, 1):
            kc = ws.cell(row=r + i, column=c0, value=k)
            vc = ws.cell(row=r + i, column=c0 + 1, value=None if isinstance(v, float) and not np.isfinite(v) else v)
            kc.border = vc.border = BORDER
            vc.number_format = ("yyyy-mm-dd" if k == "Date" else PTS if k in
                                ("VIX Open", "VIX Close", "Difference", "STD (open, close)") else PCT)
    r += len(tbl.columns) + 3
    ws.cell(row=r, column=1, value="Correlation matrix, weekly % changes (winsorised 1%/99%)").font = SUB_FONT
    r = _write_df(ws, wk["corr_weekly"], r + 1, index=True, formats={c: "0.00" for c in wk["corr_weekly"].columns})
    ws.cell(row=r, column=1, value="Correlation matrix, daily % changes (winsorised 1%/99%)").font = SUB_FONT
    r = _write_df(ws, wk["corr_daily"], r + 1, index=True, formats={c: "0.00" for c in wk["corr_daily"].columns})
    ws.cell(row=r, column=1, value="Coefficients: how each series moves with the VIX (winsorised 1%/99%)").font = SUB_FONT
    r = _write_df(ws, wk["coefficients"], r + 1)
    ws.cell(row=r, column=1, value="Does the Spread Total predict next week?").font = SUB_FONT
    r = _write_kv(ws, list(wk["predictive"].items()), r + 1)
    n_hist = int(cfg["vix"]["weekly"]["history_weeks"])
    ws.cell(row=r, column=1, value=f"Last {n_hist} weeks").font = SUB_FONT
    tbl2 = tbl.copy()
    tbl2["VIX direction (Difference)"] = np.where(tbl2["Difference"] > 0, "rose", "fell")
    tbl2["Next-week VIX change"] = tbl2[wk["vix_name"]].shift(-1)
    h = tbl2.iloc[-n_hist:].iloc[::-1].reset_index().rename(columns={"index": "Week", "Date": "Week"})
    fm = {c: PCT for c in h.columns} | {"Week": "yyyy-mm-dd"} | \
        {c: PTS for c in ("VIX Open", "VIX Close", "Difference", "STD (open, close)")}
    _write_df(ws, h, r + 1, formats=fm)
    _autowidth(ws, min_w=12)
    for c in "ADG":
        ws.column_dimensions[c].width = 30

    # Difference study
    dsr = vix["difference"]
    ws = wb.create_sheet("VIX Difference Study")
    ws["A1"] = "When the Difference (VIX close minus VIX open) is positive vs negative"
    ws["A1"].font = TITLE_FONT
    ws["A2"] = (f"Since {dsr['start']} (2008-2009 excluded: Yahoo VIX opens copy the prior close on ~30% of those days). "
                "Daily = open to close of one day; Weekly = Monday open to Friday close. 'Next period' starts at that close, "
                "so every signal is known before the outcome.")
    ws["A3"] = ("Excess = average next-period return after the bucket minus the average after all other periods; t-stat is "
                f"Welch two-sample. Backtests set the 'big rise' bar from trailing data only. {len(dsr['instruments'])} "
                "instrument/bucket tests are shown, so expect a few |t| > 2 by chance; the both-halves check guards against that.")
    ws.cell(row=5, column=1, value="1. What the VIX did next").font = SUB_FONT
    r = _write_df(ws, dsr["vix"], 6)
    ws.cell(row=r, column=1, value="2. Backtests: trading a non-VIX instrument after a big VIX rise").font = SUB_FONT
    r = _write_df(ws, dsr["strategies"], r + 1)
    ws.cell(row=r, column=1, value="3. Every instrument's next-period response, by bucket").font = SUB_FONT
    ins = dsr["instruments"].copy()
    ins["Same sign both halves"] = ins["Same sign both halves"].map({True: "yes", False: "no"})
    _write_df(ws, ins, r + 1)
    _autowidth(ws, min_w=12)
    ws.column_dimensions["A"].width = 12
    ws.column_dimensions["B"].width = 28
    ws.column_dimensions["E"].width = 22
    ws.freeze_panes = "A7"

    # Trade alerts
    al = vix["alerts"]
    n = al["now"]
    ws = wb.create_sheet("Trade Alerts")
    ws["A1"] = "Weekly Difference trade alerts"
    ws["A1"].font = TITLE_FONT
    ws["A2"] = (f"Rules fixed on {n['live_from']}. Weeks before that are a backtest of rules chosen on the same data, "
                "so their win rates flatter the rules; weeks from then on are the live record.")
    r = _write_kv(ws, [("Week", n["week"]), ("Difference (pts)", n["difference"]), ("Alert", n["headline"]),
                       ("Last week", n["last_week_result"])], 4, "This week", highlight={"Alert"} if n["fired"] else None)
    ws.cell(row=r, column=1, value="Rules").font = SUB_FONT
    r = _write_df(ws, al["rules"].drop(columns=["min_difference"]), r + 1,
                  formats={"backtest_win_rate": PCT, "backtest_avg_result": PCT})
    ws.cell(row=r, column=1, value="Alert log, newest first").font = SUB_FONT
    if len(al["log"]):
        _write_df(ws, al["log"].drop(columns=["key"]), r + 1, formats={"result": PCT, "difference": PTS})
    _autowidth(ws, min_w=12)
    ws.column_dimensions["A"].width = 24

    # Margin alert
    mg = vix["margin"]
    mn = mg["now"]
    ws = wb.create_sheet("Margin Alert")
    ws["A1"] = "Margin alert: does this week's Difference sit where the next week has cleared the margin?"
    ws["A1"].font = TITLE_FONT
    ws["A2"] = (f"Margin {mn['margin']:.1%} a week net of costs, win rate at least {mn['min_win']:.0%}. A rule must clear it on all "
                "weeks AND walk-forward (rule chosen from earlier weeks only) before it can fire.")
    r = _write_kv(ws, [("Week", mn["week"]), ("Difference (pts)", mn["difference"]), ("Margin alert", mn["headline"]),
                       ("Triggered, not confirmed", mn["unconfirmed"])], 4, "This week",
                  highlight={"Margin alert"} if mn["fired"] else None)
    ws.cell(row=r, column=1, value="Each instrument's best rule and its walk-forward record").font = SUB_FONT
    r = _write_df(ws, mg["summary"], r + 1, formats={"win_rate": PCT, "avg_result": PCT, "t_stat": RATIO, "normal_win": PCT,
                                                      "normal_avg": PCT, "wf_win_rate": PCT, "wf_avg_result": PCT})
    ws.cell(row=r, column=1, value="Every threshold for every instrument").font = SUB_FONT
    cur = mg["curve"].drop(columns=["key"]).copy()
    cur["clears_margin"] = cur["clears_margin"].map({True: "yes", False: "no"})
    _write_df(ws, cur, r + 1, formats={"win_rate": PCT, "avg_result": PCT, "t_stat": RATIO, "threshold": PTS})
    _autowidth(ws, min_w=12)
    ws.column_dimensions["A"].width = 26

    # Difference signal on the workbook's series
    ds = vix["diff_signal"]
    cur = ds["current"]
    ws = wb.create_sheet("Difference Signal")
    ws["A1"] = "Next-week outcome by weekly Difference (VIX close minus VIX open, points)"
    ws["A1"].font = TITLE_FONT
    ws["A2"] = (f"The weekly table's own series, {cur['first_week']} to {cur['week']} ({cur['weeks_total']} weeks). "
                "'Won' = the trade made money the following Friday-to-Friday week. 'Normal week' = the same trade's win "
                f"rate over all weeks. Halves split at {cur['split_week']}. p-value: one-sided binomial test against the normal week.")
    r = _write_kv(ws, [("Latest week", cur["week"]), ("Difference (pts)", cur["difference"]),
                       ("Bucket", cur["bucket"]), ("Also an extreme week", "yes" if cur["extreme"] else "no")], 4, "This week")
    ws.cell(row=r, column=1, value="Trades for this week's bucket, best first").font = SUB_FONT
    now = ds["now"].drop(columns=["order", "key"]).rename(columns={
        "scope": "Bucket", "series": "Series", "symbol": "Symbol", "side": "Side", "weeks": "Weeks", "win": "Won next week",
        "normal_win": "Normal week win rate", "edge": "Edge vs normal", "mean_next": "Avg next-week change",
        "p_value": "p-value", "win_first_half": "Won, first half", "win_second_half": "Won, second half",
        "holds_both_halves": "Above normal in both halves"})
    now["Above normal in both halves"] = now["Above normal in both halves"].map({True: "yes", False: "no"})
    r = _write_df(ws, now, r + 1, formats={"p-value": RATIO})
    ws.cell(row=r, column=1, value="Chance each series rose the next week, by Difference bucket").font = SUB_FONT
    piv = ds["buckets"].pivot_table(index=["order", "bucket"], columns="series", values="p_up_next").reset_index(level=0, drop=True)
    piv = piv.reset_index().rename(columns={"bucket": "Difference bucket"})
    r = _write_df(ws, piv, r + 1, formats={c: PCT for c in piv.columns if c != "Difference bucket"})
    ws.cell(row=r, column=1, value="All trades in all buckets").font = SUB_FONT
    allt = ds["trades"].drop(columns=["order", "key"]).copy()
    allt["holds_both_halves"] = allt["holds_both_halves"].map({True: "yes", False: "no"})
    _write_df(ws, allt, r + 1, formats={"p_value": RATIO, "win": PCT, "normal_win": PCT, "edge": PCT, "mean_next": PCT,
                                         "win_first_half": PCT, "win_second_half": PCT})
    _autowidth(ws, min_w=12)
    ws.column_dimensions["A"].width = 26

    # Implied vs historical volatility (the workbook's Sheet2)
    ivhv = vix["iv_hv"]
    ws = wb.create_sheet("Implied vs Historical Vol")
    ws["A1"] = "Implied volatility (VIX) vs historical volatility (SPY, 21-day realized)"
    ws["A1"].font = TITLE_FONT
    ws["A2"] = ("IV Rank / HV Rank = where today's value sits in its trailing 52-week range, 0 (low) to 100 (high). "
                "IV above HV is the normal state: option buyers pay a premium for protection.")
    last = ivhv.iloc[-1]
    avg = ivhv.iloc[-252:].mean()
    r = _write_kv(ws, [("As of", ivhv.index[-1].date().isoformat()),
                       ("Implied Volatility", last["Implied Volatility"]), ("IV Rank (pts)", last["IV Rank"]),
                       ("Historical Volatility", last["Historical Volatility"]), ("HV Rank (pts)", last["HV Rank"]),
                       ("Implied minus historical volatility", last["IV minus HV"]),
                       ("1-year average implied volatility", avg["Implied Volatility"]),
                       ("1-year average historical volatility", avg["Historical Volatility"]),
                       ("Share of days IV > HV, full window", float((ivhv["IV minus HV"] > 0).mean()))],
                  4, "Today")
    yr = ivhv.iloc[-252:].iloc[::-1].reset_index()
    top = r
    _write_df(ws, yr, top, formats={"Date": "yyyy-mm-dd", "Implied Volatility": PCT, "Historical Volatility": PCT,
                                    "IV minus HV": PCT, "IV Rank": "0.0", "HV Rank": "0.0"})
    chart_src = ivhv.iloc[-252:].reset_index()
    cc = 9
    _write_df(ws, chart_src[["Date", "Implied Volatility", "Historical Volatility"]], 4, c0=cc,
              formats={"Date": "yyyy-mm-dd", "Implied Volatility": PCT, "Historical Volatility": PCT})
    n = len(chart_src)
    _line_chart(ws, "Implied Volatility and Historical Volatility, last 12 months", "Annualised volatility",
                Reference(ws, min_col=cc + 1, max_col=cc + 2, min_row=4, max_row=4 + n),
                Reference(ws, min_col=cc, min_row=5, max_row=4 + n), "M4", fmt="0%", h=10, w=22)
    _autowidth(ws)
    ws.column_dimensions["A"].width = 36

    # Signal tests
    sig = vix["signals"]
    ws = wb.create_sheet("Signal Tests")
    ws["A1"] = "What the VIX does and does not predict"
    ws["A1"].font = TITLE_FONT
    ws["A2"] = ("Forward 21-trading-day SPY outcomes after each signal state. t-stats use non-overlapping months; "
                "|t| above about 2 is the usual bar, and states with few months are unreliable.")
    r = _write_kv(ws, list(sig["forecast"].items()), 4, "VIX as a volatility forecaster")
    ws.cell(row=r, column=1, value="VIX as a return signal").font = SUB_FONT
    _write_df(ws, sig["by_state"], r + 1)
    _autowidth(ws)
    ws.column_dimensions["A"].width = 46


# --------------------------------------------------------------------------
# Base model tabs
# --------------------------------------------------------------------------
def _summary(wb, cfg, data_report, portfolios, mc, mc_regime):
    ws = wb.create_sheet("Summary")
    ws["A1"] = "Quantitative Portfolio Optimization & Risk Model"
    ws["A1"].font = TITLE_FONT
    ws["A2"] = (f"Base data {data_report['start']} to {data_report['end']} | "
                f"{data_report['clean_rows']} daily observations | assets: {', '.join(data_report['tickers'])}")
    rows = [("Expected Return (gross)", "gross_return"), ("Expense Ratio Drag", "expense_drag"),
            ("Rebalancing Tax Drag (est.)", "tax_drag"), ("Expected Return (net)", "net_return"),
            ("Volatility (base)", "volatility"), ("Sharpe Ratio (gross)", "sharpe_gross"),
            ("Sharpe Ratio (net)", "sharpe_net")]
    data = {"Metric": [r[0] for r in rows] + ["Volatility in Crisis regime", "Volatility, regime mixture"]}
    for p in portfolios:
        data[p.name] = [float(getattr(p, a)) for _, a in rows] + [p.extra["crisis_vol"], p.extra["regime_mix_vol"]]
    for t in portfolios[0].weights.index:
        data["Metric"].append(f"Weight {t}")
        for p in portfolios:
            data[p.name].append(float(p.weights[t]))
    mc_keys = ["P10 Terminal Wealth", "P50 Terminal Wealth", "P90 Terminal Wealth", "P50 CAGR",
               "Probability of Loss (Terminal < Initial)", "Median Max Drawdown", "Median Friction Leakage ($)"]
    for k in mc_keys:
        for lab, src in (("static", mc), ("VIX regime", mc_regime)):
            data["Metric"].append(f"MC {lab}: {k}")
            for p in portfolios:
                data[p.name].append(float(src[p.name][0][k]))
    df = pd.DataFrame(data)
    cols = list(df.columns)
    r0 = 4
    for j, h in enumerate(cols, 1):
        ws.cell(row=r0, column=j, value=h)
    _style_header(ws, r0, 1, len(cols))
    for i, row in enumerate(df.itertuples(index=False), 1):
        for j, v in enumerate(row, 1):
            c = ws.cell(row=r0 + i, column=j, value=v)
            c.border = BORDER
            if j > 1:
                label = row[0]
                c.number_format = (RATIO if "Sharpe" in label else MONEY if "Wealth" in label or "$" in label
                                   else PCT)
    ws.column_dimensions["A"].width = 52
    for j in range(2, len(cols) + 1):
        ws.column_dimensions[get_column_letter(j)].width = 24
    ws.freeze_panes = "B5"


def _frontier(xw, frontier, portfolios):
    fr = frontier.copy()
    fr.to_excel(xw, sheet_name="Efficient Frontier", index=False)
    ws = xw.sheets["Efficient Frontier"]
    _style_header(ws, 1, 1, fr.shape[1])
    for i in range(2, len(fr) + 2):
        for j, col in enumerate(fr.columns, 1):
            c = ws.cell(row=i, column=j)
            c.border = BORDER
            c.number_format = RATIO if col == "Net Sharpe" else NUM if col == "Point" else PCT
    ws.freeze_panes = "B2"
    r = len(fr) + 3
    ws.cell(row=r, column=1, value="Optimal portfolios").font = Font(bold=True)
    for j, h in enumerate(("Portfolio", "Volatility", "Net Return"), 1):
        ws.cell(row=r + 1, column=j, value=h)
    for i, p in enumerate(portfolios):
        ws.cell(row=r + 2 + i, column=1, value=p.name)
        ws.cell(row=r + 2 + i, column=2, value=p.volatility).number_format = PCT
        ws.cell(row=r + 2 + i, column=3, value=p.net_return).number_format = PCT
    vol_col = list(fr.columns).index("Volatility") + 1
    ret_col = list(fr.columns).index("Net Return") + 1
    ch = ScatterChart()
    ch.title = "Efficient Frontier (net of frictions)"
    ch.style = 13
    ch.x_axis.title, ch.y_axis.title = "Annual Volatility", "Expected Net Return"
    ch.x_axis.number_format = ch.y_axis.number_format = "0%"
    ch.x_axis.delete = ch.y_axis.delete = False
    s = Series(Reference(ws, min_col=ret_col, min_row=2, max_row=len(fr) + 1),
               Reference(ws, min_col=vol_col, min_row=2, max_row=len(fr) + 1), title="Frontier")
    s.marker.symbol = "none"
    ch.series.append(s)
    colors = ("C00000", "2E75B6", "548235")
    for i, p in enumerate(portfolios):
        rr = r + 2 + i
        sp = Series(Reference(ws, min_col=3, min_row=rr), Reference(ws, min_col=2, min_row=rr), title=p.name)
        sp.marker.symbol, sp.marker.size = ("diamond", "circle", "triangle")[i % 3], 11
        sp.marker.graphicalProperties.solidFill = colors[i % 3]
        sp.marker.graphicalProperties.line.solidFill = colors[i % 3]
        sp.graphicalProperties.line.noFill = True
        ch.series.append(sp)
    ch.height, ch.width = 10, 18
    ws.add_chart(ch, f"{get_column_letter(fr.shape[1] + 2)}2")
    _autowidth(ws)
    ws.column_dimensions["A"].width = 24


def export(path: Path, *, cfg: dict, data_report: dict, asset_stats: pd.DataFrame,
           corr: pd.DataFrame, cov: pd.DataFrame, shrinkage: float, portfolios: list,
           frontier: pd.DataFrame, mc: dict, mc_regime: dict, vix: dict) -> Path:
    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        wb = xw.book
        _vix_dashboard(wb, cfg, portfolios, vix, mc_regime)
        _summary(wb, cfg, data_report, portfolios, mc, mc_regime)
        _vix_tabs(wb, xw, cfg, portfolios, vix, mc, mc_regime)

        w = pd.DataFrame({p.name: p.weights for p in portfolios})
        w.index.name = "Ticker"
        ws = wb.create_sheet("Optimal Weights")
        _write_df(ws, w, 1, index=True, formats={p.name: PCT for p in portfolios})
        _autowidth(ws)

        _frontier(xw, frontier, portfolios)

        ws = wb.create_sheet("Monte Carlo Metrics")
        ws["A1"] = "Monte Carlo risk metrics, static covariance (see Regime Monte Carlo for the VIX version)"
        ws["A1"].font = SUB_FONT
        keys = list(mc[portfolios[0].name][0].keys())
        cols = ["Metric"] + [p.name for p in portfolios]
        for j, h in enumerate(cols, 1):
            ws.cell(row=3, column=j, value=h)
        _style_header(ws, 3, 1, len(cols))
        for i, k in enumerate(keys, 4):
            ws.cell(row=i, column=1, value=k).border = BORDER
            for j, p in enumerate(portfolios, 2):
                v = float(mc[p.name][0][k])
                c = ws.cell(row=i, column=j, value=v)
                c.border = BORDER
                c.number_format = _fmt_for(k, v) or NUM
        ws.column_dimensions["A"].width = 46
        for j in range(2, len(cols) + 1):
            ws.column_dimensions[get_column_letter(j)].width = 24

        for p in portfolios:
            ws = wb.create_sheet(f"Wealth Paths {_short(p.name)}")
            b, rp = mc[p.name][1], mc[p.name][2]
            comb = b.merge(rp, on="Year")
            _write_df(ws, comb, 1, formats={c: MONEY for c in comb.columns if c != "Year"} | {"Year": NUM})
            _line_chart(ws, f"{p.name}: 10th / 50th / 90th percentile wealth (static)", "Portfolio Value",
                        Reference(ws, min_col=2, max_col=b.shape[1], min_row=1, max_row=len(b) + 1),
                        Reference(ws, min_col=1, min_row=2, max_row=len(b) + 1),
                        f"{get_column_letter(comb.shape[1] + 2)}2")
            _autowidth(ws, min_w=14)
            ws.freeze_panes = "B2"

        a = asset_stats.copy()
        a.index.name = "Ticker"
        ws = wb.create_sheet("Asset Statistics")
        fm = {c: (PCT if any(s in c for s in ("Return", "CAGR", "Volatility", "Drawdown"))
                  else '"$"#,##0.00' if "Price" in c else NUM if c == "Observations" else RATIO)
              for c in a.columns}
        _write_df(ws, a, 1, index=True, formats=fm)
        _autowidth(ws)

        ws = wb.create_sheet("Correlation & Covariance")
        n = len(corr)
        c2 = corr.copy()
        c2.index.name = "Correlation"
        r = _write_df(ws, c2, 1, index=True, formats={c: "0.00" for c in c2.columns})
        ws.cell(row=r, column=1,
                value=f"Annualised covariance, base window (Ledoit-Wolf correlation shrinkage = {shrinkage:.3f})"
                ).font = Font(bold=True)
        cv = cov.copy()
        cv.index.name = "Covariance"
        _write_df(ws, cv, r + 1, index=True, formats={c: "0.0000" for c in cv.columns})
        _autowidth(ws)

        ws = wb.create_sheet("Assumptions")
        ws["A1"] = "Model assumptions (from config.json)"
        ws["A1"].font = TITLE_FONT

        def _flat(prefix, obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    yield from _flat(f"{prefix}.{k}" if prefix else k, v)
            elif isinstance(obj, list):
                yield prefix, ", ".join(map(str, obj))
            else:
                yield prefix, obj

        r = 3
        for k, v in _flat("", cfg):
            ws.cell(row=r, column=1, value=k).border = BORDER
            ws.cell(row=r, column=2, value=v).border = BORDER
            r += 1
        r += 1
        ws.cell(row=r, column=1, value="Data cleaning report (base window)").font = SUB_FONT
        r += 1
        for k, v in data_report.items():
            if isinstance(v, dict):
                v = ", ".join(f"{a}: {b}" for a, b in v.items()) or "none"
            elif isinstance(v, list):
                v = ", ".join(v)
            ws.cell(row=r, column=1, value=k).border = BORDER
            ws.cell(row=r, column=2, value=v).border = BORDER
            r += 1
        ws.column_dimensions["A"].width = 46
        ws.column_dimensions["B"].width = 60

        if "Sheet" in wb.sheetnames:
            del wb["Sheet"]
        first = ["VIX Dashboard", "Trade Alerts", "Margin Alert", "Summary", "VIX Regimes", "Regime Stress Test", "Regime Monte Carlo",
                 "VIX Rule Backtest", "VIX Hedge Sizing", "VIX Weekly Coefficients", "Difference Signal", "VIX Difference Study",
                 "Implied vs Historical Vol",
                 "Signal Tests",
                 "Optimal Weights", "Efficient Frontier", "Monte Carlo Metrics"]
        rest = [s for s in wb.sheetnames if s not in first]
        wb._sheets = [wb[s] for s in first + rest]
        wb.active = 0
        for ws in wb.worksheets:
            ws.page_setup.orientation = "landscape"
            ws.sheet_properties.pageSetUpPr.fitToPage = True
            ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 0
    return path
