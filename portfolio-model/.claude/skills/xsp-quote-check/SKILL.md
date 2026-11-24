---
name: xsp-quote-check
description: Use when the user pastes live XSP option quotes (bid, ask, mid, delta) for a same-day put spread and asks whether to sell it.
---

# XSP quote check

1. Read dashboard_data/xsp_alert.json for today. If its date is not today,
   run `venv/bin/python xsp_alert.py` first.
2. If status is SKIP, say so first and repeat the reasons. Do not price it.
3. From the user's quotes, take the spread credit at the mid:
   (short put bid+ask)/2 minus (long put bid+ask)/2, times 100.
   Check that the short put delta is between 0.45 and 0.55; if not, name the
   strike nearer 50 delta.
4. Compare the credit with min_credit for that width. Answer in one line:
   "SELL at $X or better" or "SKIP: credit $X is below the $Y minimum".
5. Add the max loss (width x 100 minus credit) and the keep rate from the
   alert. Remind once that spreads need spread approval in a cash account.
6. No em dashes, no exclamation points. Statistical pattern, not advice.
