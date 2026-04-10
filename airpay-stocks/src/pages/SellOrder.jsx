// Screen 13: Sell Order Form — Owner: Smallcase SDK
// Same flow as Screen 12 but transactionType: "SELL"
// Max quantity capped by transactableQuantity from Holdings API
// CDSL TPIN: SDK redirects to CDSL for TPIN + OTP authorization (30-60s friction)
// T+1 settlement: Sale proceeds credited next trading day
// No bottom nav (SDK screen)

import { useParams, useNavigate } from "react-router-dom";
import SDKScreen from "../components/SDKScreen";
import { holdingsResponse } from "../data/mockHoldings";
import { getBhavcopyBySymbol } from "../data/mockBhavcopy";

export default function SellOrder() {
  const { symbol } = useParams();
  const navigate = useNavigate();
  const bv = getBhavcopyBySymbol(symbol);
  const security = holdingsResponse.data.securities.find((s) => s.nseTicker === symbol);
  const maxQty = security?.transactableQuantity || 0;
  const fmt = (v) => "\u20B9" + (v || 0).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  function handleReview() {
    navigate(`/order-review/${symbol}?type=SELL`);
  }

  return (
    <SDKScreen title={`Sell ${symbol}`} onContinue={handleReview} continueLabel="Review Order">
      <p className="sdk-desc">
        <code>triggerTransaction({"{"} transactionId {"}"})</code> — SDK renders sell order form.
      </p>

      <div className="order-form-sim">
        <div className="order-form-sim__header">
          <span className="order-form-sim__symbol">{symbol}</span>
          <span className="order-form-sim__price">LTP: {bv ? fmt(bv.CLOSE_PRICE) : "—"}</span>
        </div>

        <div className="order-form-sim__toggle">
          <button className="toggle-btn">BUY</button>
          <button className="toggle-btn toggle-btn--active toggle-btn--sell">SELL</button>
        </div>

        <div className="order-form-sim__field">
          <label>Order Type</label>
          <div className="order-type-chips">
            <span className="order-type-chip order-type-chip--active">MARKET</span>
            <span className="order-type-chip">LIMIT</span>
            <span className="order-type-chip">SL</span>
            <span className="order-type-chip">SLM</span>
          </div>
        </div>

        <div className="order-form-sim__field">
          <label>Quantity <span className="field-hint">(max: {maxQty})</span></label>
          <div className="qty-input">
            <button className="qty-btn">−</button>
            <span className="qty-value">1</span>
            <button className="qty-btn">+</button>
          </div>
        </div>

        <div className="order-form-sim__summary">
          <div className="order-form-sim__row">
            <span>Exchange</span><span>NSE</span>
          </div>
          <div className="order-form-sim__row">
            <span>Product</span><span>CNC (Delivery)</span>
          </div>
          <div className="order-form-sim__row">
            <span>Estimated Proceeds</span><span>{bv ? fmt(bv.CLOSE_PRICE) : "—"}</span>
          </div>
        </div>

        <div className="cdsl-warning">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#D85A30" strokeWidth="2"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
          <div>
            <strong>CDSL TPIN Authorization Required</strong>
            <p>All delivery sells require CDSL TPIN + OTP verification. This adds 30-60 seconds. Airpay cannot skip this step.</p>
          </div>
        </div>

        <div className="settlement-note">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#378ADD" strokeWidth="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
          <span>T+1 Settlement: Sale proceeds credited next trading day</span>
        </div>
      </div>
    </SDKScreen>
  );
}
