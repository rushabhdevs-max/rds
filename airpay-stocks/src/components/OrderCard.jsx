import DataTag from "./DataTag";
import { formatBrokerName, getStatusColor, getOrderDisplayStatus } from "../data/mockOrders";

function formatTime(ts) {
  if (!ts) return "";
  const d = new Date(ts);
  return d.toLocaleString("en-IN", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", hour12: true });
}

function formatPrice(val) {
  if (!val) return null;
  return "\u20B9" + val.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function OrderLeg({ leg, isUnplaced }) {
  const isBuy = leg.transactionType === "BUY";
  const showAvgPrice = leg.status === "COMPLETE" && leg.averagePrice > 0;
  const showErrorCode = (leg.status === "ERROR" || leg.status === "UNPLACED") && leg.errorCode;

  return (
    <div className="order-leg">
      <div className="order-leg__row">
        <span className={`txn-tag txn-tag--${isBuy ? "buy" : "sell"}`}>
          {leg.transactionType}
        </span>
        <span className="order-leg__ticker">{leg.tradingsymbol}</span>
        <span className="order-leg__qty">Qty {leg.quantity}</span>
        <span className="order-leg__type">{leg.orderType}</span>
      </div>
      <div className="order-leg__details">
        {leg.orderType === "LIMIT" && leg.price > 0 && (
          <span>Price: {formatPrice(leg.price)}</span>
        )}
        {leg.orderType === "SL" && (
          <>
            <span>Price: {formatPrice(leg.price)}</span>
            <span>Trigger: {formatPrice(leg.triggerPrice)}</span>
          </>
        )}
        {leg.orderType === "SLM" && leg.triggerPrice > 0 && (
          <span>Trigger: {formatPrice(leg.triggerPrice)}</span>
        )}
        {showAvgPrice && (
          <span className="text-green">Filled {leg.filledQuantity} @ {formatPrice(leg.averagePrice)}</span>
        )}
        {leg.status === "PARTIAL" && leg.filledQuantity > 0 && (
          <span className="text-orange">Filled {leg.filledQuantity}/{leg.quantity}</span>
        )}
        {showErrorCode && (
          <span className="text-red">Error: {leg.errorCode}</span>
        )}
        {(leg.status === "CANCELLED" || leg.status === "CANCELLED AMO") && (
          <span className="text-red">{leg.status === "CANCELLED AMO" ? "AMO Cancelled" : "Cancelled"}</span>
        )}
      </div>
    </div>
  );
}

export default function OrderCard({ order }) {
  const displayStatus = getOrderDisplayStatus(order);
  const statusColor = getStatusColor(order.status);
  const broker = formatBrokerName(order.broker);
  const isInferred = order._inferred;
  const isUnplaced = order.status === "UNPLACED";
  const legs = isUnplaced ? order.unplaced : order.orders;

  return (
    <div className="order-card">
      <div className="order-card__header">
        <div className="order-card__header-left">
          <span className="order-card__status" style={{ color: statusColor, borderColor: statusColor }}>
            {displayStatus}
          </span>
          {order.variety === "amo" && displayStatus !== "AMO · Placed" && (
            <span className="order-card__amo">AMO</span>
          )}
          <DataTag type={isInferred ? "INF" : "WH"} />
        </div>
        <span className="order-card__time">{formatTime(order.timestamp)}</span>
      </div>

      <div className="order-card__meta">
        <span>{broker}</span>
        <span>{order.variety}</span>
        <span>{legs[0]?.exchange || "NSE"}</span>
        <span>{legs[0]?.product || "CNC"}</span>
      </div>

      {isUnplaced && (
        <div className="order-card__error-banner">
          Orders could not be placed with broker
        </div>
      )}

      {order.variety === "amo" && order.status === "PLACED" && (
        <div className="order-card__amo-banner">
          Queued for next market open
        </div>
      )}

      <div className="order-card__legs">
        {legs.map((leg, i) => (
          <OrderLeg key={i} leg={leg} isUnplaced={isUnplaced} />
        ))}
      </div>

      <div className="order-card__footer">
        <span>Total: {order.quantity} · Filled: {order.filled}</span>
        {order.status === "COMPLETED" && (
          <div className="order-card__amounts">
            {order.sellAmount > 0 && <span className="text-red">Sold: {formatPrice(order.sellAmount)}</span>}
            {order.buyAmount > 0 && <span className="text-green">Bought: {formatPrice(order.buyAmount)}</span>}
            {order.buyAmount > 0 && order.sellAmount > 0 && (
              <span className="order-card__net">
                Net: {formatPrice(order.buyAmount - order.sellAmount)}
              </span>
            )}
          </div>
        )}
        {order.status === "PARTIAL" && (
          <div className="order-card__progress">
            <div className="progress-bar">
              <div
                className="progress-bar__fill"
                style={{ width: `${(order.filled / order.quantity) * 100}%` }}
              />
            </div>
            <span>{order.filled}/{order.quantity} filled</span>
          </div>
        )}
      </div>
    </div>
  );
}
