"""Multi-tab Excel export with formatting and native Excel charts."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from openpyxl.chart import LineChart, Reference, ScatterChart, Series
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

HEADER_FILL = PatternFill("solid", fgColor="1F3864")
HEADER_FONT = Font(bold=True, color="FFFFFF")
TITLE_FONT = Font(bold=True, size=14, color="1F3864")
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

PCT, MONEY, NUM, RATIO = "0.00%", '"$"#,##0', "#,##0", "0.000"


def _fmt_for(label: str, value) -> str | None:
    if not isinstance(value, (int, float)):
        return None
    l = label.lower()
    if "sharpe" in l:
        return RATIO
    if "$" in l:
        return MONEY
    if any(s in l for s in ("probability", "cagr", "return", "drawdown", "(%", "drag",
                            "volatility", "weight")):
        return PCT
    if any(s in l for s in ("wealth", "capital", "paid", "leakage")):
        return MONEY
    return None


def _style_table(ws, n_rows: int, n_cols: int, start_row: int = 1,
                 col_formats: dict[int, str] | None = None, freeze: str | None = "B2"):
    for c in range(1, n_cols + 1):
        cell = ws.cell(row=start_row, column=c)
        cell.fill, cell.font, cell.border = HEADER_FILL, HEADER_FONT, BORDER
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for r in range(start_row + 1, start_row + n_rows + 1):
        for c in range(1, n_cols + 1):
            cell = ws.cell(row=r, column=c)
            cell.border = BORDER
            if col_formats and c in col_formats:
                cell.number_format = col_formats[c]
    for c in range(1, n_cols + 1):
        letter = get_column_letter(c)
        width = max(len(str(ws.cell(row=r, column=c).value or ""))
                    for r in range(start_row, start_row + min(n_rows, 200) + 1))
        ws.column_dimensions[letter].width = min(max(12, width + 2), 48)
    ws.row_dimensions[start_row].height = 32
    if freeze:
        ws.freeze_panes = freeze


def _write_kv(ws, rows: list[tuple[str, object]], start_row: int, title: str | None = None):
    r = start_row
    if title:
        ws.cell(row=r, column=1, value=title).font = Font(bold=True, size=12, color="1F3864")
        r += 1
    for k, v in rows:
        ws.cell(row=r, column=1, value=k).border = BORDER
        c = ws.cell(row=r, column=2, value=v)
        c.border = BORDER
        fmt = _fmt_for(k, v)
        if fmt:
            c.number_format = fmt
        r += 1
    return r + 1


def export(path: Path, *, cfg: dict, data_report: dict, asset_stats: pd.DataFrame,
           corr: pd.DataFrame, cov: pd.DataFrame, shrinkage: float, portfolios: list,
           frontier: pd.DataFrame, mc_metrics: dict, bands: dict, rep_paths: dict) -> Path:
    tickers = list(asset_stats.index)
    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        wb = xw.book

        # ---------------- Summary ----------------
        ws = wb.create_sheet("Summary")
        ws["A1"] = "Quantitative Portfolio Optimization & Risk Model"
        ws["A1"].font = TITLE_FONT
        ws["A2"] = (f"Data {data_report['start']} to {data_report['end']} | "
                    f"{data_report['clean_rows']} daily observations | "
                    f"assets: {', '.join(data_report['tickers'])}")
        r = 4
        hdr = ["Metric"] + [p.name for p in portfolios]
        for j, h in enumerate(hdr, 1):
            ws.cell(row=r, column=j, value=h)
        rows = [
            ("Expected Return (gross)", "gross_return", PCT),
            ("Expense Ratio Drag", "expense_drag", PCT),
            ("Rebalancing Tax Drag (est.)", "tax_drag", PCT),
            ("Expected Return (net)", "net_return", PCT),
            ("Volatility", "volatility", PCT),
            ("Sharpe Ratio (gross)", "sharpe_gross", RATIO),
            ("Sharpe Ratio (net)", "sharpe_net", RATIO),
        ]
        for i, (label, attr, fmt) in enumerate(rows, 1):
            ws.cell(row=r + i, column=1, value=label)
            for j, p in enumerate(portfolios, 2):
                ws.cell(row=r + i, column=j, value=float(getattr(p, attr))).number_format = fmt
        base = r + len(rows) + 1
        ws.cell(row=base, column=1, value="Weights").font = Font(bold=True)
        for i, t in enumerate(tickers, 1):
            ws.cell(row=base + i, column=1, value=f"  {t}")
            for j, p in enumerate(portfolios, 2):
                ws.cell(row=base + i, column=j, value=float(p.weights[t])).number_format = PCT
        _style_table(ws, base + len(tickers) - r, len(hdr), start_row=r, freeze=None)
        ws.column_dimensions["A"].width = 34

        mc_keys = ["P50 Terminal Wealth", "P10 Terminal Wealth", "P90 Terminal Wealth",
                   "P50 CAGR", "Probability of Loss (Terminal < Initial)",
                   "Median Max Drawdown", "Median Friction Leakage ($)"]
        r2 = base + len(tickers) + 3
        ws.cell(row=r2, column=1,
                value=f"Monte Carlo ({cfg['monte_carlo']['n_trials']:,} trials, "
                      f"{cfg['monte_carlo']['horizon_years']} years, "
                      f"${cfg['monte_carlo']['initial_capital']:,.0f} initial)").font = Font(bold=True, size=12, color="1F3864")
        r2 += 1
        for j, h in enumerate(hdr, 1):
            ws.cell(row=r2, column=j, value=h)
        for i, k in enumerate(mc_keys, 1):
            ws.cell(row=r2 + i, column=1, value=k)
            for j, p in enumerate(portfolios, 2):
                v = mc_metrics[p.name][k]
                c = ws.cell(row=r2 + i, column=j, value=float(v))
                c.number_format = _fmt_for(k, v) or NUM
        _style_table(ws, len(mc_keys), len(hdr), start_row=r2, freeze=None)
        ws.column_dimensions["A"].width = 42
        for j in range(2, len(hdr) + 1):
            ws.column_dimensions[get_column_letter(j)].width = 24

        # ---------------- Optimal Weights ----------------
        w = pd.DataFrame({p.name: p.weights for p in portfolios})
        w.index.name = "Ticker"
        w.to_excel(xw, sheet_name="Optimal Weights")
        ws = xw.sheets["Optimal Weights"]
        _style_table(ws, len(w), w.shape[1] + 1,
                     col_formats={c: PCT for c in range(2, w.shape[1] + 2)})

        # ---------------- Efficient Frontier ----------------
        fr = frontier.copy()
        fr.to_excel(xw, sheet_name="Efficient Frontier", index=False)
        ws = xw.sheets["Efficient Frontier"]
        fmts = {i + 1: (RATIO if col == "Net Sharpe" else NUM if col == "Point" else PCT)
                for i, col in enumerate(fr.columns)}
        _style_table(ws, len(fr), fr.shape[1], col_formats=fmts)
        ws.column_dimensions["A"].width = 24
        # Optimal points below the table, then the chart.
        r = len(fr) + 3
        ws.cell(row=r, column=1, value="Optimal portfolios").font = Font(bold=True)
        ws.cell(row=r + 1, column=1, value="Portfolio")
        ws.cell(row=r + 1, column=2, value="Volatility")
        ws.cell(row=r + 1, column=3, value="Net Return")
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
        xs = Reference(ws, min_col=vol_col, min_row=2, max_row=len(fr) + 1)
        ys = Reference(ws, min_col=ret_col, min_row=2, max_row=len(fr) + 1)
        s = Series(ys, xs, title="Frontier")
        s.marker.symbol = "none"
        ch.series.append(s)
        for i, p in enumerate(portfolios):
            rr = r + 2 + i
            sp = Series(Reference(ws, min_col=3, min_row=rr), Reference(ws, min_col=2, min_row=rr),
                        title=p.name)
            color = ("C00000", "2E75B6")[i % 2]
            sp.marker.symbol, sp.marker.size = ("diamond", "circle")[i % 2], 11
            sp.marker.graphicalProperties.solidFill = color
            sp.marker.graphicalProperties.line.solidFill = color
            sp.graphicalProperties.line.noFill = True
            ch.series.append(sp)
        ch.height, ch.width = 10, 18
        ws.add_chart(ch, f"{get_column_letter(fr.shape[1] + 2)}2")

        # ---------------- Monte Carlo Metrics ----------------
        ws = wb.create_sheet("Monte Carlo Metrics")
        names = [p.name for p in portfolios]
        keys = list(mc_metrics[names[0]].keys())
        ws.cell(row=1, column=1, value="Metric")
        for j, n in enumerate(names, 2):
            ws.cell(row=1, column=j, value=n)
        for i, k in enumerate(keys, 2):
            ws.cell(row=i, column=1, value=k)
            for j, n in enumerate(names, 2):
                v = float(mc_metrics[n][k])
                c = ws.cell(row=i, column=j, value=v)
                c.number_format = _fmt_for(k, v) or NUM
        _style_table(ws, len(keys), len(names) + 1)
        ws.column_dimensions["A"].width = 46

        # ---------------- Wealth Paths (per portfolio) ----------------
        for p in portfolios:
            short = "MaxSharpe" if "Sharpe" in p.name else "MinVar"
            sheet = f"Wealth Paths {short}"
            b = bands[p.name]
            rp = rep_paths[p.name]
            combined = b.merge(rp, on="Year")
            combined.to_excel(xw, sheet_name=sheet, index=False)
            ws = xw.sheets[sheet]
            _style_table(ws, len(combined), combined.shape[1],
                         col_formats={c: MONEY for c in range(2, combined.shape[1] + 1)})
            lc = LineChart()
            lc.title = f"{p.name}: 10th / 50th / 90th percentile wealth"
            lc.y_axis.title, lc.x_axis.title = "Portfolio Value", "Year"
            lc.y_axis.number_format = '"$"#,##0'
            lc.x_axis.delete = lc.y_axis.delete = False
            data = Reference(ws, min_col=2, max_col=b.shape[1], min_row=1, max_row=len(b) + 1)
            lc.add_data(data, titles_from_data=True)
            lc.set_categories(Reference(ws, min_col=1, min_row=2, max_row=len(b) + 1))
            lc.height, lc.width = 10, 18
            ws.add_chart(lc, f"{get_column_letter(combined.shape[1] + 2)}2")

        # ---------------- Asset Statistics ----------------
        a = asset_stats.copy()
        a.index.name = "Ticker"
        a.to_excel(xw, sheet_name="Asset Statistics")
        ws = xw.sheets["Asset Statistics"]
        fm = {}
        for i, col in enumerate(a.columns, 2):
            fm[i] = (PCT if any(s in col for s in ("Return", "CAGR", "Volatility", "Drawdown"))
                     else '"$"#,##0.00' if "Price" in col else NUM if col == "Observations" else RATIO)
        _style_table(ws, len(a), a.shape[1] + 1, col_formats=fm)

        # ---------------- Correlation / Covariance ----------------
        corr.index.name = "Correlation"
        corr.to_excel(xw, sheet_name="Correlation & Covariance")
        ws = xw.sheets["Correlation & Covariance"]
        n = len(corr)
        _style_table(ws, n, n + 1, col_formats={c: "0.00" for c in range(2, n + 2)})
        start = n + 4
        ws.cell(row=start - 1, column=1,
                value=f"Annualised covariance (Ledoit-Wolf correlation shrinkage = {shrinkage:.3f})"
                ).font = Font(bold=True)
        cov.index.name = "Covariance"
        cov.to_excel(xw, sheet_name="Correlation & Covariance", startrow=start - 1)
        _style_table(ws, n, n + 1, start_row=start,
                     col_formats={c: "0.0000" for c in range(2, n + 2)}, freeze=None)

        # ---------------- Assumptions ----------------
        ws = wb.create_sheet("Assumptions")
        ws["A1"] = "Model assumptions (from config.json)"
        ws["A1"].font = TITLE_FONT
        def _cell(v):
            return ", ".join(map(str, v)) if isinstance(v, list) else v

        flat = []
        for section, vals in cfg.items():
            if isinstance(vals, dict):
                flat += [(f"{section}.{k}", _cell(v)) for k, v in vals.items()]
            else:
                flat.append((section, _cell(vals)))
        r = 3
        for k, v in flat:
            ws.cell(row=r, column=1, value=k).border = BORDER
            ws.cell(row=r, column=2, value=v).border = BORDER
            r += 1
        r += 1
        ws.cell(row=r, column=1, value="Data cleaning report").font = Font(bold=True, size=12, color="1F3864")
        r += 1
        for k, v in data_report.items():
            if isinstance(v, (list, dict)):
                v = ", ".join(f"{a}: {b}" for a, b in v.items()) if isinstance(v, dict) else ", ".join(v)
                v = v or "none"
            ws.cell(row=r, column=1, value=k).border = BORDER
            ws.cell(row=r, column=2, value=v).border = BORDER
            r += 1
        ws.column_dimensions["A"].width = 40
        ws.column_dimensions["B"].width = 60

        # Drop the default empty sheet and order tabs.
        if "Sheet" in wb.sheetnames:
            del wb["Sheet"]
        order = ["Summary", "Optimal Weights", "Efficient Frontier", "Monte Carlo Metrics"] + \
                [s for s in wb.sheetnames if s.startswith("Wealth Paths")] + \
                ["Asset Statistics", "Correlation & Covariance", "Assumptions"]
        wb._sheets = [wb[s] for s in order]
        wb.active = 0
        for ws in wb.worksheets:  # print each tab landscape, one page wide
            ws.page_setup.orientation = "landscape"
            ws.sheet_properties.pageSetUpPr.fitToPage = True
            ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 0
    return path
