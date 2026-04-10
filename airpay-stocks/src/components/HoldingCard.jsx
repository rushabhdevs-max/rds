import { useNavigate } from "react-router-dom";
import DataTag from "./DataTag";

export default function HoldingCard({ security, bhavcopy }) {
  const navigate = useNavigate();
  const { nseTicker, name, holdings } = security;
  const closePrice = bhavcopy?.CLOSE_PRICE || 0;
  const currentValue = holdings.quantity * closePrice;
  const invested = holdings.quantity * holdings.averagePrice;
  const pnl = currentValue - invested;
  const pnlPct = invested > 0 ? (pnl / invested) * 100 : 0;
  const isPositive = pnl >= 0;
  const type = bhavcopy?.type || "EQ";
  const isETF = type === "MF";

  function handleClick() {
    if (isETF) {
      navigate(`/etf/${nseTicker}?from=holdings`);
    } else {
      navigate(`/stock/${nseTicker}?from=holdings`);
    }
  }

  return (
    <div className="holding-card" onClick={handleClick}>
      <div className="holding-card__header">
        <div className="holding-card__left">
          <div className="holding-card__ticker-row">
            <span className="holding-card__ticker">{nseTicker}</span>
            <span className={`type-badge type-badge--${isETF ? "etf" : "eq"}`}>
              {isETF ? "ETF" : "EQ"}
            </span>
            <DataTag type="WH" />
          </div>
          <span className="holding-card__name">{name}</span>
        </div>
        <div className="holding-card__right">
          <span className="holding-card__value">
            {"\u20B9"}{currentValue.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </span>
          <span className={`holding-card__pnl ${isPositive ? "text-green" : "text-red"}`}>
            {isPositive ? "+" : ""}{pnlPct.toFixed(2)}%
          </span>
        </div>
      </div>
      <div className="holding-card__meta">
        <span>Qty: {holdings.quantity}</span>
        <span>Avg: {"\u20B9"}{holdings.averagePrice.toFixed(2)}</span>
        <span>LTP: {"\u20B9"}{closePrice.toFixed(2)} <DataTag type="BV" /></span>
      </div>
    </div>
  );
}
