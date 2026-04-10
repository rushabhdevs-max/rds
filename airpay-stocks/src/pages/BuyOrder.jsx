// Screen 12: Buy Order Form — Owner: Smallcase SDK
// Backend creates transactionId with intent TRANSACTION + orderConfig
// Frontend: triggerTransaction({ transactionId }) — passes ONLY transactionId
// SDK renders: order form with BUY/SELL toggle, order type, quantity, price
// Order types: MARKET (price=0), LIMIT (price set), SL (price+trigger), SLM (trigger only)
// AMO: After 3:30 PM IST, variety becomes "amo"
// No bottom nav (SDK screen)

import { useParams, useNavigate } from "react-router-dom";
import SDKScreen from "../components/SDKScreen";
import { getBhavcopyBySymbol } from "../data/mockBhavcopy";

export default function BuyOrder() {
  const { symbol } = useParams();
  const navigate = useNavigate();
  const bv = getBhavcopyBySymbol(symbol);
  const fmt = (v) => "\u20B9" + (v || 0).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  function handleReview() {
    navigate(`/order-review/${symbol}?type=BUY`);
  }

  return (
    <SDKScreen title={`Buy ${symbol}`} onContinue={handleReview} continueLabel="Review Order">
      <p className="sdk-desc">
        <code>triggerTransaction({"{"} transactionId {"}"})</code> — SDK renders this order form.
      </p>

      <div className="order-form-sim">
        <div className="order-form-sim__header">
          <span className="order-form-sim__symbol">{symbol}</span>
          <span className="order-form-sim__price">LTP: {bv ? fmt(bv.CLOSE_PRICE) : "—"}</span>
        </div>

        <div className="order-form-sim__toggle">
          <button className="toggle-btn toggle-btn--active toggle-btn--buy">BUY</button>
          <button className="toggle-btn">SELL</button>
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
          <label>Quantity</label>
          <div className="qty-input">
            <button className="qty-btn">−</button>
            <span className="qty-value">1</span>
            <button className="qty-btn">+</button>
          </div>
        </div>

        <div className="order-form-sim__field">
          <label>Price</label>
          <span className="order-form-sim__hint">Market order — price determined at execution</span>
        </div>

        <div className="order-form-sim__summary">
          <div className="order-form-sim__row">
            <span>Exchange</span><span>NSE</span>
          </div>
          <div className="order-form-sim__row">
            <span>Product</span><span>CNC (Delivery)</span>
          </div>
          <div className="order-form-sim__row">
            <span>Estimated Cost</span><span>{bv ? fmt(bv.CLOSE_PRICE) : "—"}</span>
          </div>
        </div>

        <div className="order-form-sim__api-note">
          <strong>Backend creates:</strong>
          <pre>{JSON.stringify({
            intent: "TRANSACTION",
            orderConfig: [{
              tradingsymbol: symbol,
              transactionType: "BUY",
              quantity: 1,
              orderType: "MARKET",
              exchange: "NSE",
              product: "CNC",
              price: 0,
              triggerPrice: 0
            }]
          }, null, 2)}</pre>
        </div>
      </div>
    </SDKScreen>
  );
}
