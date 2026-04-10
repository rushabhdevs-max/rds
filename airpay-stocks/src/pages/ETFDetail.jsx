// Screen 10: ETF Detail from Holdings + Screen 11: ETF Detail from Search — Owner: Airpay
// Data source 1 (Holdings API): holdings.quantity, holdings.averagePrice, transactableQuantity
// Data source 2 (Bhavcopy ETF): SYMBOL, SECURITY, UNDERLYING (replaces IND_SEC), OHLC, 52W, volume
// No IND_SEC, No CORP_IND for ETFs. Has UNDERLYING field.

import { useParams, useSearchParams, useNavigate } from "react-router-dom";
import BottomNav from "../components/BottomNav";
import DataTag from "../components/DataTag";
import { holdingsResponse } from "../data/mockHoldings";
import { getBhavcopyBySymbol } from "../data/mockBhavcopy";

export default function ETFDetail() {
  const { symbol } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const fromHoldings = searchParams.get("from") === "holdings";

  const bv = getBhavcopyBySymbol(symbol);
  const security = holdingsResponse.data.securities.find((s) => s.nseTicker === symbol);
  const hasHoldings = fromHoldings && security;

  if (!bv) {
    return (
      <div className="page">
        <div className="page__content">
          <header className="page-header">
            <button className="back-btn" onClick={() => navigate(-1)}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="15 18 9 12 15 6"/></svg>
            </button>
            <h1 className="page-header__title">Not Found</h1>
          </header>
          <p style={{ padding: 16 }}>ETF "{symbol}" not found in Bhavcopy data.</p>
        </div>
        <BottomNav />
      </div>
    );
  }

  const closePrice = bv.CLOSE_PRICE;
  const prevClose = bv.PREV_CL_PR;
  const dayChange = closePrice - prevClose;
  const dayChangePct = prevClose ? (dayChange / prevClose) * 100 : 0;
  const isPositive = dayChange >= 0;
  const fmt = (v) => "\u20B9" + v.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  return (
    <div className="page">
      <div className="page__content">
        <header className="page-header">
          <button className="back-btn" onClick={() => navigate(-1)}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="15 18 9 12 15 6"/></svg>
          </button>
          <h1 className="page-header__title">{symbol}</h1>
        </header>

        {/* ETF Header */}
        <div className="detail-header">
          <div className="detail-header__top">
            <div>
              <h2 className="detail-header__symbol">{bv.SYMBOL}</h2>
              <p className="detail-header__name">{bv.SECURITY}</p>
            </div>
            <div className="detail-header__tags">
              <span className="type-badge type-badge--etf">ETF · MF</span>
              <DataTag type="BV" />
            </div>
          </div>
          {bv.UNDERLYING && (
            <span className="sector-tag sector-tag--etf">Tracks: {bv.UNDERLYING}</span>
          )}
          <div className="detail-header__price">
            <span className="detail-header__close">{fmt(closePrice)}</span>
            <span className={`detail-header__change ${isPositive ? "text-green" : "text-red"}`}>
              {isPositive ? "+" : ""}{fmt(dayChange)} ({isPositive ? "+" : ""}{dayChangePct.toFixed(2)}%)
            </span>
          </div>
        </div>

        {/* Your Holdings card */}
        {hasHoldings && (
          <div className="holdings-card">
            <h3 className="holdings-card__title">Your Holdings <DataTag type="WH" /></h3>
            <div className="holdings-card__grid">
              <div className="holdings-card__item">
                <span className="holdings-card__label">Quantity</span>
                <span className="holdings-card__val">{security.holdings.quantity}</span>
              </div>
              <div className="holdings-card__item">
                <span className="holdings-card__label">Avg Price</span>
                <span className="holdings-card__val">{fmt(security.holdings.averagePrice)}</span>
              </div>
              <div className="holdings-card__item">
                <span className="holdings-card__label">Transactable</span>
                <span className="holdings-card__val">{security.transactableQuantity}</span>
              </div>
              <div className="holdings-card__item">
                <span className="holdings-card__label">Current Value</span>
                <span className="holdings-card__val">{fmt(security.holdings.quantity * closePrice)}</span>
              </div>
              <div className="holdings-card__item">
                <span className="holdings-card__label">P&L</span>
                {(() => {
                  const pnl = security.holdings.quantity * (closePrice - security.holdings.averagePrice);
                  return <span className={`holdings-card__val ${pnl >= 0 ? "text-green" : "text-red"}`}>{pnl >= 0 ? "+" : ""}{fmt(pnl)}</span>;
                })()}
              </div>
            </div>
          </div>
        )}

        {!hasHoldings && (
          <div className="not-held-card">
            <span>Not in your holdings</span>
            <button className="btn btn--outline btn--sm">Add to Watchlist</button>
          </div>
        )}

        {/* Market Data */}
        <div className="market-data">
          <h3 className="market-data__title">Market Data <DataTag type="BV" /></h3>
          <div className="market-data__grid">
            <div className="market-data__item"><span>Open</span><span>{fmt(bv.OPEN_PRICE)}</span></div>
            <div className="market-data__item"><span>High</span><span>{fmt(bv.HIGH_PRICE)}</span></div>
            <div className="market-data__item"><span>Low</span><span>{fmt(bv.LOW_PRICE)}</span></div>
            <div className="market-data__item"><span>Prev Close</span><span>{fmt(prevClose)}</span></div>
            <div className="market-data__item"><span>52W High</span><span>{fmt(bv.HI_52_WK)}</span></div>
            <div className="market-data__item"><span>52W Low</span><span>{fmt(bv.LO_52_WK)}</span></div>
            <div className="market-data__item"><span>Volume</span><span>{bv.NET_TRDQTY?.toLocaleString("en-IN")}</span></div>
            <div className="market-data__item"><span>Trades</span><span>{bv.TRADES?.toLocaleString("en-IN")}</span></div>
          </div>
        </div>

        {/* 52-Week Range */}
        <div className="range-bar">
          <span className="range-bar__label">{fmt(bv.LO_52_WK)}</span>
          <div className="range-bar__track">
            <div
              className="range-bar__marker"
              style={{ left: `${((closePrice - bv.LO_52_WK) / (bv.HI_52_WK - bv.LO_52_WK)) * 100}%` }}
            />
          </div>
          <span className="range-bar__label">{fmt(bv.HI_52_WK)}</span>
        </div>

        {/* Disclaimer */}
        <p className="disclaimer">
          ETF prices reflect yesterday's EOD. For live prices, refer to live markets.
        </p>

        {/* CTAs */}
        <div className="detail-ctas">
          <button className="btn btn--buy" onClick={() => navigate(`/buy/${symbol}`)}>BUY</button>
          {hasHoldings && (
            <button className="btn btn--sell" onClick={() => navigate(`/sell/${symbol}`)}>SELL</button>
          )}
        </div>
      </div>
      <BottomNav />
    </div>
  );
}
