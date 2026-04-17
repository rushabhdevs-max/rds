# WhatsApp Stock & ETF Scanner

Sends stock and ETF price updates to your WhatsApp every 15 minutes using Twilio and Yahoo Finance.

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Set up Twilio WhatsApp
1. Create a free account at [twilio.com](https://www.twilio.com)
2. Go to **Messaging > Try it out > Send a WhatsApp message**
3. Follow the sandbox instructions — send the join code from your phone to the Twilio sandbox number
4. Copy your Account SID and Auth Token from the [Twilio Console](https://console.twilio.com)

### 3. Configure environment
```bash
cp .env.example .env
```
Edit `.env` with your Twilio credentials and WhatsApp number:
```
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
WHATSAPP_TO=whatsapp:+919876543210
SCAN_INTERVAL_MINUTES=15
```

### 4. Customize your watchlist
Edit `watchlist.json` to add/remove stocks and ETFs:
```json
{
  "stocks": ["AAPL", "GOOGL", "TSLA"],
  "etfs": ["SPY", "QQQ", "VOO"]
}
```

### 5. Run
```bash
python scanner.py
```

## Sample Message
```
--- Stock & ETF Scanner ---
Time: 2026-04-17 10:30:00

STOCKS:
  RELIANCE.NS: Rs.2890.50 (+1.23% day) | scan: +0.15%
  TCS.NS: Rs.3845.30 (-0.87% day) | scan: -0.32%

ETFs:
  NIFTYBEES.NS: Rs.252.10 (+0.45% day)
  BANKBEES.NS: Rs.478.80 (+0.67% day)
```

**Note:** NSE tickers use the `.NS` suffix (e.g. `RELIANCE.NS`). For BSE use `.BO`.

## Running as a background service

```bash
nohup python scanner.py > scanner.log 2>&1 &
```

Or use `systemd`, `pm2`, or `screen`/`tmux` for long-running execution.
