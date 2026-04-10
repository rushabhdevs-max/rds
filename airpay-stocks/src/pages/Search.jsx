// Screen 23: Search — Owner: Airpay
// Data source: Bhavcopy files (local search)
// Search fields: SYMBOL + SECURITY for text matching
// Filter chips: All | Stocks | ETFs | Watchlist
// Per result: Ticker, name, type tag, sector/underlying, CLOSE_PRICE, day change
// Tap stock → Screen 9 (StockDetail from Search). Tap ETF → Screen 11 (ETFDetail from Search).

import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import BottomNav from "../components/BottomNav";
import FilterChips from "../components/FilterChips";
import DataTag from "../components/DataTag";
import { getAllBhavcopy } from "../data/mockBhavcopy";

export default function Search() {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("All");

  const allData = useMemo(() => getAllBhavcopy(), []);

  const results = useMemo(() => {
    let data = allData;
    // Filter by type
    if (filter === "Stocks") data = data.filter((d) => d.type === "EQ");
    else if (filter === "ETFs") data = data.filter((d) => d.type === "MF");
    else if (filter === "Watchlist") data = []; // Empty for now

    // Search by symbol + name
    if (query.trim()) {
      const q = query.trim().toUpperCase();
      data = data.filter(
        (d) => d.SYMBOL.toUpperCase().includes(q) || d.SECURITY.toUpperCase().includes(q)
      );
    }
    return data;
  }, [allData, query, filter]);

  function handleTap(item) {
    if (item.type === "MF") {
      navigate(`/etf/${item.SYMBOL}?from=search`);
    } else {
      navigate(`/stock/${item.SYMBOL}?from=search`);
    }
  }

  const fmt = (v) => "\u20B9" + v.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  return (
    <div className="page">
      <div className="page__content">
        <header className="page-header">
          <h1 className="page-header__title">Search</h1>
        </header>

        <div className="search-bar">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#999" strokeWidth="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          <input
            type="text"
            placeholder="Search stocks & ETFs..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="search-bar__input"
          />
          {query && (
            <button className="search-bar__clear" onClick={() => setQuery("")}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#999" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
          )}
        </div>

        <FilterChips options={["All", "Stocks", "ETFs", "Watchlist"]} active={filter} onChange={setFilter} />

        <div className="search-results">
          {results.length === 0 ? (
            <div className="empty-state">
              <p className="empty-state__sub">
                {filter === "Watchlist" ? "Your watchlist is empty" : "No results found"}
              </p>
            </div>
          ) : (
            results.map((item) => {
              const dayChange = item.CLOSE_PRICE - item.PREV_CL_PR;
              const dayChangePct = item.PREV_CL_PR ? (dayChange / item.PREV_CL_PR) * 100 : 0;
              const isPositive = dayChange >= 0;
              const isETF = item.type === "MF";

              return (
                <div key={item.SYMBOL} className="search-result" onClick={() => handleTap(item)}>
                  <div className="search-result__left">
                    <div className="search-result__ticker-row">
                      <span className="search-result__ticker">{item.SYMBOL}</span>
                      <span className={`type-badge type-badge--${isETF ? "etf" : "eq"}`}>
                        {isETF ? "ETF" : "EQ"}
                      </span>
                      <DataTag type="BV" />
                    </div>
                    <span className="search-result__name">{item.SECURITY}</span>
                    <span className="search-result__sector">
                      {isETF ? item.UNDERLYING : item.IND_SEC}
                    </span>
                  </div>
                  <div className="search-result__right">
                    <span className="search-result__price">{fmt(item.CLOSE_PRICE)}</span>
                    <span className={`search-result__change ${isPositive ? "text-green" : "text-red"}`}>
                      {isPositive ? "+" : ""}{dayChangePct.toFixed(2)}%
                    </span>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
      <BottomNav />
    </div>
  );
}
