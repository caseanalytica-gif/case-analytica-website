# XSP ATM call and put check (10:00 and 11:00 ET)

A separate model from the VIX model. It has its own settings (`config.json`),
its own output (`output/`) and its own scheduled task. It does not read or
change the VIX model, its config or the dashboard. It sits inside
`portfolio-model/` only so it is not published on the website and can share
the Python setup.

## The method

From the "Option Price Cheat Code" video (on-screen formulas):

1. Expected move, one standard deviation: M = S x IV x sqrt(DTE / 365)
2. ATM straddle: C + P ~ 0.8 x M (also the break-even move)
3. ATM call: C ~ 0.4 x M
4. ATM put: P ~ 0.4 x M

For same-day XSP, days to expiry becomes hours left to the 4:00 PM close over
1,638 trading hours a year (6.5 x 252), and IV is live VIX1D. The model also
prices the nearest $1 strike with Black-Scholes and gives delta, gamma, vega
and time decay per hour.

Real quotes (2026-11-26): the alert takes the bid and ask for today's XSP
expiry at that strike from Yahoo's option chain and judges the ask (what you
pay). Yahoo option quotes run about 15 minutes behind, so XSP, VIX1D and the
fair price are taken as of that moment. If the chain is unavailable (Yahoo
rate-limits it), the price falls back to the VIX1D estimate and the alert says
so. If a quote's implied volatility is under 0.6x or over 1.8x VIX1D, an
UPSIDE becomes CHECK QUOTE, since the quote is likely stale.

"Fair" price is what the option would have paid on average on past days like
today: the move to the close divided by the VIX1D-implied move, from two years
of hourly S&P 500 and VIX1D data (10:30 and 11:30 entries), in the same bucket
(VIX above or below 20, market up or down since the open), scaled to today.
The verdict is UPSIDE only if fair is at least 10% above the ask plus $0.65
fees.

## Test results (2026-11-26)

- Real moves to the close averaged about 80% of what VIX1D implied.
- Walk-forward, July 2024 to November 2026, 2,380 entries: buying the ATM call
  at the model price lost 28% on average (won 29%), the put lost 22% (won 27%).
- Fair price as a share of market price: calls 71% to 97%, average 78%; puts
  62% to 99%, average 81%. It never reached 110%, so the model never flagged
  UPSIDE. "NO UPSIDE" is the expected daily answer.
- The test priced options from VIX1D, since past XSP quotes are not available
  free. The live alert uses real quotes. Always confirm the broker's live ask
  is at or below "pay at most" before buying.
- Half days (1:00 PM close) are listed in config.json under early_close_hour.

## Running it

    ../venv/bin/python atm_model.py             # live, at 10:00 or 11:00 ET
    ../venv/bin/python atm_model.py --backtest  # walk-forward test

Scheduled task "XSP ATM call and put check" runs it at 10:02 and 11:02 ET on
weekdays and sends the result by phone and email.
