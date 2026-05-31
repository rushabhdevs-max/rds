# What only you can do (can't be automated)

Phase 1 (prices + returns dashboard) is already live with no keys.

To enable the rest:
- **Holdings Δ / Sector Δ (P2):** implement one adapter in etl/sources/amc_portfolio.py
  (your AMC's monthly portfolio XLS) and etl/sources/us_etf.py (your ETF issuer's
  holdings CSV). See SPEC.md §7-8. Until then, use the manual-import fallback.
- **Alerts to your phone (P3):** create a Telegram bot via @BotFather, get the token
  and your chat_id, add them as GitHub repo secrets TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID,
  set notify.telegram: true in config/settings.yml, then build etl/alerts.py + notify.py.
- **Better US data (optional):** add a TIINGO_TOKEN secret to replace the Stooq fallback.

Edit holdings anytime in config/portfolio.yml, then `python -m etl.run` (local) or push.
