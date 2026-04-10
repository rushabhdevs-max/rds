// Screen 6: Portfolio Summary + Screen 7: Holdings Detail — Owner: Airpay
// Tabs: Holdings (active) | Orders
// Data: Fetch Holdings API v2 + Bhavcopy CLOSE_PRICE for P&L
// P&L = (holdings.quantity × Bhavcopy CLOSE_PRICE) − (holdings.quantity × holdings.averagePrice)

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import BottomNav from "../components/BottomNav";
import TabBar from "../components/TabBar";
import FilterChips from "../components/FilterChips";
import HoldingCard from "../components/HoldingCard";
import DataTag from "../components/DataTag";
import { holdingsResponse } from "../data/mockHoldings";
import { getBhavcopyBySymbol } from "../data/mockBhavcopy";

export default function Portfolio() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState("Holdings");
  const [filter, setFilter] = useState("All");

  const securities = holdingsResponse.data.securities;

  // Enrich each security with bhavcopy data
  const enriched = securities.map((sec) => {
    const bv = getBhavcopyBySymbol(sec.nseTicker);
    const closePrice = bv?.CLOSE_PRICE || 0;
    const currentValue = sec.holdings.quantity * closePrice;
    const invested = sec.holdings.quantity * sec.holdings.averagePrice;
    return { ...sec, bhavcopy: bv, currentValue, invested, pnl: currentValue - invested };
  });

  // Filter
  const filtered = enriched.filter((s) => {
    if (filter === "Stocks") return s.bhavcopy?.type === "EQ";
    if (filter === "ETFs") return s.bhavcopy?.type === "MF";
    return true;
  });

  // Totals
  const totalCurrent = enriched.reduce((sum, s) => sum + s.currentValue, 0);
  const totalInvested = enriched.reduce((sum, s) => sum + s.invested, 0);
  const totalPnl = totalCurrent - totalInvested;
  const totalPnlPct = totalInvested > 0 ? (totalPnl / totalInvested) * 100 : 0;

  // Today's change (CLOSE - PREV_CL_PR) × quantity for each holding
  const todayChange = enriched.reduce((sum, s) => {
    if (!s.bhavcopy) return sum;
    const dayDiff = s.bhavcopy.CLOSE_PRICE - (s.bhavcopy.PREV_CL_PR || s.bhavcopy.CLOSE_PRICE);
    return sum + dayDiff * s.holdings.quantity;
  }, 0);

  function handleTabChange(tab) {
    if (tab === "Orders") navigate("/orders");
    else setActiveTab(tab);
  }

  const fmt = (v) => "\u20B9" + v.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  return (
    <div className="page">
      <div className="page__content">
        <header className="page-header">
          <button className="back-btn" onClick={() => navigate("/")}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="15 18 9 12 15 6"/></svg>
          </button>
          <h1 className="page-header__title">Portfolio</h1>
        </header>

        <TabBar active={activeTab} onChange={handleTabChange} />

        {/* Summary Card */}
        <div className="summary-card">
          <div className="summary-card__row">
            <div className="summary-card__item">
              <span className="summary-card__label">Current Value <DataTag type="BV" /></span>
              <span className="summary-card__value">{fmt(totalCurrent)}</span>
            </div>
            <div className="summary-card__item">
              <span className="summary-card__label">Invested <DataTag type="WH" /></span>
              <span className="summary-card__value">{fmt(totalInvested)}</span>
            </div>
          </div>
          <div className="summary-card__row">
            <div className="summary-card__item">
              <span className="summary-card__label">Total P&L</span>
              <span className={`summary-card__value ${totalPnl >= 0 ? "text-green" : "text-red"}`}>
                {totalPnl >= 0 ? "+" : ""}{fmt(totalPnl)} ({totalPnlPct >= 0 ? "+" : ""}{totalPnlPct.toFixed(2)}%)
              </span>
            </div>
            <div className="summary-card__item">
              <span className="summary-card__label">Today</span>
              <span className={`summary-card__value ${todayChange >= 0 ? "text-green" : "text-red"}`}>
                {todayChange >= 0 ? "+" : ""}{fmt(todayChange)}
              </span>
            </div>
          </div>
          <div className="summary-card__updated">
            Updated: Just now
          </div>
        </div>

        {/* Filter Chips */}
        <FilterChips options={["All", "Stocks", "ETFs"]} active={filter} onChange={setFilter} />

        {/* Holdings List */}
        <div className="holdings-list">
          {filtered.map((sec) => (
            <HoldingCard key={sec.nseTicker} security={sec} bhavcopy={sec.bhavcopy} />
          ))}
        </div>

        {/* Refresh Holdings */}
        <button className="refresh-btn" onClick={() => navigate("/holdings-loading")}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 11-2.12-9.36L23 10"/></svg>
          Refresh Holdings
        </button>
      </div>
      <BottomNav />
    </div>
  );
}
