"""
WhatsApp Stock & ETF Scanner
Sends price updates every N minutes via Twilio WhatsApp API.
"""

import json
import os
import signal
import sys
from datetime import datetime, timezone, timedelta

import schedule
import time
import yfinance as yf
from dotenv import load_dotenv
from twilio.rest import Client

IST = timezone(timedelta(hours=5, minutes=30))
MARKET_OPEN = (9, 15)
MARKET_CLOSE = (15, 30)

load_dotenv()

# Twilio config
TWILIO_SID = os.environ["TWILIO_ACCOUNT_SID"]
TWILIO_TOKEN = os.environ["TWILIO_AUTH_TOKEN"]
TWILIO_FROM = os.environ["TWILIO_WHATSAPP_FROM"]
WHATSAPP_TO = os.environ["WHATSAPP_TO"]
SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL_MINUTES", "15"))

twilio_client = Client(TWILIO_SID, TWILIO_TOKEN)

# Previous prices for change tracking
prev_prices: dict[str, float] = {}


def load_watchlist() -> dict:
    with open("watchlist.json") as f:
        return json.load(f)


def fetch_prices(symbols: list[str]) -> dict[str, dict]:
    """Fetch current prices for a list of symbols."""
    results = {}
    tickers = yf.Tickers(" ".join(symbols))
    for symbol in symbols:
        try:
            ticker = tickers.tickers[symbol]
            info = ticker.fast_info
            price = info.last_price
            prev_close = info.previous_close
            day_change = ((price - prev_close) / prev_close) * 100 if prev_close else 0
            results[symbol] = {
                "price": round(price, 2),
                "prev_close": round(prev_close, 2),
                "day_change": round(day_change, 2),
            }
        except Exception as e:
            print(f"[WARN] Failed to fetch {symbol}: {e}")
    return results


def format_line(symbol: str, data: dict) -> str:
    """Format a single ticker line with change indicators."""
    price = data["price"]
    day_chg = data["day_change"]
    arrow = "+" if day_chg >= 0 else ""

    # 15-min change vs previous scan
    scan_chg_str = ""
    if symbol in prev_prices:
        diff = ((price - prev_prices[symbol]) / prev_prices[symbol]) * 100
        scan_arrow = "+" if diff >= 0 else ""
        scan_chg_str = f" | scan: {scan_arrow}{diff:.2f}%"

    return f"{symbol}: Rs.{price:.2f} ({arrow}{day_chg:.2f}% day){scan_chg_str}"


def build_message(stock_data: dict, etf_data: dict) -> str:
    """Build the full WhatsApp message."""
    now = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST")
    lines = [f"--- Stock & ETF Scanner ---", f"Time: {now}", ""]

    if stock_data:
        lines.append("STOCKS:")
        for sym, data in stock_data.items():
            lines.append(f"  {format_line(sym, data)}")
        lines.append("")

    if etf_data:
        lines.append("ETFs:")
        for sym, data in etf_data.items():
            lines.append(f"  {format_line(sym, data)}")

    return "\n".join(lines)


def send_whatsapp(message: str):
    """Send a message via Twilio WhatsApp."""
    msg = twilio_client.messages.create(
        body=message,
        from_=TWILIO_FROM,
        to=WHATSAPP_TO,
    )
    print(f"[OK] Message sent (SID: {msg.sid})")


def is_market_open() -> bool:
    now = datetime.now(IST)
    if now.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    t = (now.hour, now.minute)
    return MARKET_OPEN <= t <= MARKET_CLOSE


def scan_and_send():
    """Main scan cycle: fetch prices, build message, send."""
    if not is_market_open():
        now_ist = datetime.now(IST).strftime("%H:%M IST, %A")
        print(f"[SKIP] {now_ist} - Market closed, sleeping until next check.")
        return

    print(f"\n[SCAN] {datetime.now(IST).strftime('%H:%M:%S IST')} - Fetching prices...")
    watchlist = load_watchlist()

    stock_data = fetch_prices(watchlist.get("stocks", []))
    etf_data = fetch_prices(watchlist.get("etfs", []))

    if not stock_data and not etf_data:
        print("[WARN] No data fetched, skipping send.")
        return

    message = build_message(stock_data, etf_data)
    print(message)

    try:
        send_whatsapp(message)
    except Exception as e:
        print(f"[ERROR] Failed to send WhatsApp message: {e}")

    # Update previous prices for next scan comparison
    for sym, data in {**stock_data, **etf_data}.items():
        prev_prices[sym] = data["price"]


def main():
    print(f"WhatsApp Stock Scanner started.")
    print(f"Scanning every {SCAN_INTERVAL} minutes.")
    print(f"Market hours: {MARKET_OPEN[0]}:{MARKET_OPEN[1]:02d} - {MARKET_CLOSE[0]}:{MARKET_CLOSE[1]:02d} IST (Mon-Fri)")
    print(f"Sending to: {WHATSAPP_TO}")
    print(f"Watchlist: {load_watchlist()}")
    print("-" * 40)

    # Run immediately on start
    scan_and_send()

    # Schedule recurring scans
    schedule.every(SCAN_INTERVAL).minutes.do(scan_and_send)

    # Graceful shutdown
    def handle_exit(sig, frame):
        print("\nShutting down scanner.")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    main()
