# Portfolio model: VIX Risk Model

This folder holds the VIX-centred portfolio and risk model, its weekly trade
alert and the data behind the online dashboard. Read this file before changing
anything here.

## Where things live

- `main.py`: entry point. `config.json`: settings and alert rules.
  `README.md` explains the method in full.
- `portfolio_model_output.xlsx`: the Excel workbook.
- `dashboard_data/vix_model_data.json`: the one data file the online dashboard reads.
- `dashboard_data/alert.txt`: the latest alert text.
- Online dashboard: https://claude.ai/artifact/GF3qDARTNu88NeCm8aAPxk
  Every dataset on it is a file source pointing at one uploaded copy of
  `vix_model_data.json`; the page (`files/index.html`) is not touched by refreshes.
- This folder lives on branch `claude/trusting-curie-8rxokh`. That branch is the
  copy the scheduled tasks run. The repo's `main` branch deploys the
  caseanalytica.com website: never push model work to `main`.
- The user's original workbooks (`Copy_of_VIX_Algo.xlsx`, `algo_with_chart.xlsx`)
  are kept outside the repo. Their hand-entered values do not match the dates
  they carry; do not treat them as data.

## Weekly dashboard update: every Friday

The dashboard is updated twice every Friday by scheduled tasks, so it always ends
the week on the correct, official closing numbers:

1. **3:07 PM ET, "VIX Difference Friday alert"** (`trig_01PvLcwztJwLPk72Pw9dXFHU`):
   runs the model on live prices, refreshes the dashboard, and sends the trade
   alert by phone and email. Numbers are preliminary: VIX is the 3:07 PM price,
   not the close. Keep this time; it lets the user trade before the close.
2. **4:47 PM ET, "VIX dashboard Friday final-close refresh"**
   (`trig_01FKwGtYteGAK4p9Lzb5dgzX`): reruns the model after the close and
   replaces the dashboard data with the official Friday closes. Reports the final
   Difference and says plainly if the final close changed which alerts fired.

Both run `main.py --refresh`, upload the new `vix_model_data.json` to the
dashboard, repoint every dataset at it in one batch, and delete the old file.

If a Friday run fails or a refresh is done by hand, do the same steps: run
`main.py --refresh`, check `alert_now[0].week` is this Friday, then upload and
repoint as above. A Friday market holiday means the week ends Thursday; the
model handles that from the data.

## The alert rules (`config.json`, `alerts.rules`)

The signal is the weekly Difference: VIX Friday close minus VIX Monday open, in
points. Every trade is entered at the Friday close and exited at the next
Friday close. The user is long-only (buy only) and has decided against
Monday-open entries: do not reintroduce them.

| Difference | Rule | Status |
|---|---|---|
| +5 or more | Buy SCO (-2x daily crude). Take profit at +5% from entry, else sell next Friday close. Optional -8% stop. | trade |
| +5 or more | Buy XLU (utilities). Hold the week. Since 2010 won 68% (normal week 56%), avg +0.87%. | trade |
| -5 or less | Buy SPY. Hold the week. Since 2010 won 67% (normal week 58%), avg +0.85%. | trade |
| +5 or more | Long GLD; short natural gas | watch |
| +5 or more | Oil lower next week | signal |
| +3 or more | VIX lower next week (risk read, not a trade) | signal |

- A rule fires on `min_difference` (at or above) or `max_difference` (at or below).
- Margin alert: only for a rule that clears 0.5% a week net and a 55% win rate,
  both in-sample and walk-forward. As of 2026-11-07 none qualify.
- Live record starts 2026-11-06 (first live alert: Difference +6.59; SCO bought
  at $18.77, take profit $19.71; XLU at $43.13; exit at the Nov 13 close).
  Earlier weeks are a backtest of rules chosen on the same data.
- About 80% of -5 weeks come within 4 weeks of a +3 spike.

## Standards for any new signal or rule

- Test against the normal week, not against zero, and check both halves of the
  sample. Say how many variants were tried: a 2026-11-07 scan of 574 tests found
  about as many "significant" results as chance would.
- Pick thresholds walk-forward before calling anything an edge.
- Use tradable ETFs for results, not continuous futures series (roll jumps).
- Yahoo VIX opens are unreliable in 2008 and 2009: start Difference studies in 2010.
- SVXY changed from -1x to -0.5x in Feb 2018: use only data after that.
- Say plainly when a result is weak. Never present in-sample results as a forecast.

## Writing rules for anything the user reads

No em dashes and no exclamation points. Plain, direct sentences. Lead with the
answer and the numbers.

## Running it

    python3 -m venv venv
    venv/bin/pip install pandas numpy yfinance scipy openpyxl
    venv/bin/python main.py --refresh

`--refresh` downloads fresh prices and updates the cache.
