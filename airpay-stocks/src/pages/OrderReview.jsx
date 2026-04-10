// Screen 14: Order Review / Confirmation — Owner: Smallcase SDK
// Continuation of triggerTransaction() — SDK renders final review
// On confirm: Broker OMS → NSE exchange execution
// SDK onSuccess returns: transactionId, broker, smallcaseAuthToken, orderBatches[]
// Webhook fires async with same structure
// No bottom nav (SDK screen)

import { useParams, useSearchParams, useNavigate } from "react-router-dom";
import SDKScreen from "../components/SDKScreen";
import { getBhavcopyBySymbol } from "../data/mockBhavcopy";

export default function OrderReview() {
  const { symbol } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const type = searchParams.get("type") || "BUY";
  const bv = getBhavcopyBySymbol(symbol);
  const isBuy = type === "BUY";
  const fmt = (v) => "\u20B9" + (v || 0).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  function handleConfirm() {
    navigate("/orders", { replace: true });
  }

  return (
    <SDKScreen title="Review Order" onContinue={handleConfirm} continueLabel="Confirm Order">
      <p className="sdk-desc">
        <code>triggerTransaction()</code> continuation — final review before execution.
      </p>

      <div className="review-sim">
        <div className="review-sim__card">
          <div className="review-sim__row">
            <span className={`txn-tag txn-tag--${isBuy ? "buy" : "sell"}`}>{type}</span>
            <span className="review-sim__symbol">{symbol}</span>
          </div>
          <div className="review-sim__details">
            <div className="review-sim__detail">
              <span>Order Type</span><span>MARKET</span>
            </div>
            <div className="review-sim__detail">
              <span>Quantity</span><span>1</span>
            </div>
            <div className="review-sim__detail">
              <span>Exchange</span><span>NSE</span>
            </div>
            <div className="review-sim__detail">
              <span>Product</span><span>CNC (Delivery)</span>
            </div>
            <div className="review-sim__detail">
              <span>Indicative Price</span><span>{bv ? fmt(bv.CLOSE_PRICE) : "—"}</span>
            </div>
          </div>
        </div>

        <div className="review-sim__callback">
          <strong>SDK onSuccess callback will return:</strong>
          <pre>{JSON.stringify({
            transactionId: "TRX_xxx...",
            broker: "kite-leprechaun",
            smallcaseAuthToken: "new_JWT",
            orderBatches: [{
              batchId: "63afcadb...",
              status: "PLACED",
              variety: "regular",
              quantity: 1,
              filled: 0,
              orders: [{
                tradingsymbol: symbol,
                transactionType: type,
                status: "PLACED",
                quantity: 1,
                orderType: "MARKET",
                product: "CNC",
                exchange: "NSE"
              }]
            }]
          }, null, 2)}</pre>
        </div>

        <div className="review-sim__webhook-note">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#378ADD" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
          <span>Webhook fires async to backend. Verify checksum = SHA256(timestamp + smallcaseAuthId) signed with API_SECRET.</span>
        </div>
      </div>
    </SDKScreen>
  );
}
