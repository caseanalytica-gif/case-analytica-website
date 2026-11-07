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
- The workbooks compute Spread Total two ways (sum in algo_with_chart, sum / 6
  in Copy_of_VIX_Algo); the model follows algo_with_chart. Only the Difference
  row drives trades: Spread Total and Average did not predict next week's VIX
  or SPY.
- Dashboard page: every drawing goes through the `draw()` wrapper, which clears
  the loading shimmer (`dash-skeleton`). Keep it in any page edit; without it
  the tables stay blank.
- The Mac folder "Portfolio model ai" sits in iCloud (under ~/Library), which
  cloud sessions cannot attach. Send Mac updates as a zip of that folder.

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
3. **3:37 PM ET weekdays, "VIX daily alert (QQQ / GLD)"**
   (`trig_01Ry8NEzqzshedkS81C8zQse`): runs `daily_alert.py` (rules in
   config.json under "daily"). VIX close minus open +3 or more: buy QQQ at
   the close, sell next close. -3 or less: buy GLD at the close, sell 5
   trading days later. Also sends SELL reminders. Does not touch the dashboard.

Both run `main.py --refresh`, upload the new `vix_model_data.json` to the
dashboard, repoint every dataset at it in one batch, and delete the old file.

If a Friday run fails or a refresh is done by hand, do the same steps: run
`main.py --refresh`, check `alert_now[0].week` is this Friday, then upload and
repoint as above. A Friday market holiday means the week ends Thursday; the
model handles that from the data.

Deleting the old data file is a permanent delete: in Auto mode it can be
refused. That is harmless (the old file is unused); the user can approve it
in another mode.

## The alert rules (`config.json`, `alerts.rules`)

The signal is the weekly Difference: VIX Friday close minus VIX Monday open, in
points. Every trade is entered at the Friday close and exited at the next
Friday close. The user is long-only (buy only) and has decided against
Monday-open entries: do not reintroduce them.

| Difference | Rule | Status |
|---|---|---|
| +5 or more | Buy SCO (-2x daily crude). Take profit at +5% from entry, else sell next Friday close. Optional -8% stop. | trade |
| +5 or more | Buy XLU (utilities). Hold the week. Since 2010 won 68% (normal week 56%), avg +0.87%. Optional take profit +2.5% (won 70%, avg +0.74%). | trade |
| -5 or less | Buy SPY. Hold the week. Since 2010 won 67% (normal week 58%), avg +0.85%. Optional take profit +1% (won 78%, avg +0.72%). | trade |
| -5 or less | Buy SSO (2x S&P 500) in place of SPY, about half the size. Since 2010 won 67%, avg +1.70%, worst week -13.2%. Optional take profit +1% (won 83%, avg +1.25%). | trade |
| Negative, VIX close 20+ | Buy SVOL. Since 2021 won 71%, avg +1.11%, walk-forward 73%, worst week -6.1%. Size small, never on margin. | trade |
| +5 or more | Long GLD; short natural gas | watch |
| +5 or more | Oil lower next week | signal |
| +3 or more | VIX lower next week (risk read, not a trade) | signal |

- A rule fires on `min_difference` (at or above) or `max_difference` (at or below).
- A rule can also require `min_vix` (minimum VIX close) and carry its own `trigger_text`.
- Cash account only, no margin (user, 2026-11-07). Margin alerts are off
  (alerts.margin.enabled = false); the margin study still runs for the
  dashboard. Lower margin bars were tested: at 0.30%/week only QQQ on
  Difference -0.5 or less passed walk-forward, and that is mostly normal
  drift. Watch for cash-account settlement: reusing unsettled sale money
  for a trade that is sold before settlement is a good faith violation.
- The alert's Orders block gives each trade's entry price, take-profit price and exit date (`take_profit` in each rule).
- Margin alert: only for a rule that clears 0.5% a week net and a 55% win rate,
  both in-sample and walk-forward. As of 2026-11-07 none qualify.
- Live record starts 2026-11-06 (first live alert: Difference +6.59; SCO bought
  at $18.77, take profit $19.71; XLU at $43.13; exit at the Nov 13 close).
  Earlier weeks are a backtest of rules chosen on the same data.
- About 80% of -5 weeks come within 4 weeks of a +3 spike.
- Daily rules (since 2010): QQQ next day after a +3 VIX day won 64% of 117
  (normal 54%), avg +0.58%, walk-forward 64%, worst day -6.3%. GLD over 5 days
  after a -3 day won 63% of 86, avg +1.05%, walk-forward 66%. SVXY after +3 won
  69% of 70 (avg +0.87%) but was not chosen (crash risk). Daily moves of +1 or
  +2 have little or no edge.
- Tested 2026-11-07 and not adopted (do not re-test without a new reason):
  - Rotation: hold SPY (or GLD), switch to SCO on a +5 alert, back after the
    take-profit. 3 years: +109% vs +75% SPY alone; +156% vs +104% GLD alone.
  - After the SCO take-profit, buy GLD for the rest of the week: added +1.05%
    on average (16 of 24 alerts hit the take-profit early).
  - Rejected: KOLD on +5 (worst week -38%); SVXY on positive weeks (+0.58%
    since 2018, worst -20%); GLD as a trade (44% won since 2021); SPY on +5
    (t-stat 0.95); any rule on Difference between 0 and -5 (no edge).
  - $5,000 per SCO alert, last 3 years: 5 trades, +$1,225.
- VIX ETFs, tested 2026-11-07 (not yet alerts):
  - Never buy long-VIX ETFs (VIXY, VXX, UVXY, UVIX, VIXM): they lose in every
    Difference bucket and decay 18% to 82% a year.
  - Inverse VIX ETFs work only after fear starts easing, never after a spike.
    Signal "Difference negative and VIX 20 or above", Friday close to Friday close:
    SVIX (since 2022) won 81% of 43, avg +4.35%, worst week -12%;
    SVXY (since Mar 2018) won 72% of 88, avg +1.27%, worst week -18.4%;
    SVOL (since 2021) won 71% of 51, avg +1.11%, walk-forward 73%, worst week -6.1%.
  - The same signal does not work for stock ETFs since 2010 (SSO, UPRO, SPY won
    55-56% vs 58% normal; walk-forward fails). SVIX's 81% is partly a 2022-2026
    effect. SVOL is the preferred way to take it; SVIX is watch-only.
  - Crash risk: SVIX fell 39% and SVXY 21% in one day (2024-08-05). Size small,
    never on margin.
  - On Difference -5 or less (since 2010, 46 trades): SSO (2x S&P 500) won 67%,
    avg +1.70%, walk-forward 67%, worst week -13.2%; with a +1% take profit it
    won 83%, avg +1.25%. Same odds as SPY at about twice the payoff.
  - JEPI after +5 weeks won 11 of 13, avg +1.53%, worst week -0.6%: watch only,
    too few trades.
  - SVOL and SSO added as trade alerts on 2026-11-07.

## Standards for any new signal or rule

- Test against the normal week, not against zero, and check both halves of the
  sample. Say how many variants were tried: a 2026-11-07 scan of 574 tests found
  about as many "significant" results as chance would.
- Pick thresholds walk-forward before calling anything an edge.
- Use tradable ETFs for results, not continuous futures series (roll jumps).
- Yahoo VIX opens are unreliable in 2008 and 2009: start Difference studies in 2010.
- SVXY changed from -1x to -0.5x in Feb 2018: use only data after that.
- Say plainly when a result is weak. Never present in-sample results as a forecast.

## Keeping this memory current

At the end of a session that changed rules, ran new tests or opened or closed a
live trade, run the `reflect` skill (`.claude/skills/reflect/`). It reviews the
session, shows the exact edits to this file and any new skills, and saves only
what the user approves.

## Writing rules for anything the user reads

No em dashes and no exclamation points. Plain, direct sentences. Lead with the
answer and the numbers.

## Running it

    python3 -m venv venv
    venv/bin/pip install pandas numpy yfinance scipy openpyxl
    venv/bin/python main.py --refresh

`--refresh` downloads fresh prices and updates the cache.
