// Screens 15-22: Orders Tab — Owner: Airpay (custom UI)
// NOT showOrders() — that renders SDK's native UI
// Data: Stored webhook data (preferred) or Fetch Order Details API
// Filter chips: All | Placed | Completed | Failed
// Tabs: Holdings | Orders (active)

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import BottomNav from "../components/BottomNav";
import TabBar from "../components/TabBar";
import FilterChips from "../components/FilterChips";
import OrderCard from "../components/OrderCard";
import { allOrders, getOrderDisplayStatus } from "../data/mockOrders";

export default function Orders() {
  const navigate = useNavigate();
  const [filter, setFilter] = useState("All");

  function handleTabChange(tab) {
    if (tab === "Holdings") navigate("/portfolio");
  }

  const filtered = allOrders.filter((order) => {
    if (filter === "All") return true;
    const status = getOrderDisplayStatus(order);
    if (filter === "Placed") return status.includes("Placed") || status === "AMO · Placed";
    if (filter === "Completed") return status === "Completed";
    if (filter === "Failed") return status === "Failed" || status === "Cancelled";
    if (filter === "Partial") return status === "Partial";
    return true;
  });

  const isEmpty = allOrders.length === 0;

  return (
    <div className="page">
      <div className="page__content">
        <header className="page-header">
          <button className="back-btn" onClick={() => navigate("/")}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="15 18 9 12 15 6"/></svg>
          </button>
          <h1 className="page-header__title">Portfolio</h1>
        </header>

        <TabBar active="Orders" onChange={handleTabChange} />
        <FilterChips options={["All", "Placed", "Completed", "Failed", "Partial"]} active={filter} onChange={setFilter} />

        {isEmpty ? (
          /* Screen 22: Empty State */
          <div className="empty-state">
            <div className="empty-state__circle">0</div>
            <h3 className="empty-state__title">No orders yet</h3>
            <p className="empty-state__sub">Place your first stock or ETF order</p>
            <button className="btn btn--primary" onClick={() => navigate("/search")}>
              Start Trading
            </button>
          </div>
        ) : (
          <div className="orders-list">
            {filtered.length === 0 ? (
              <div className="empty-state">
                <p className="empty-state__sub">No {filter.toLowerCase()} orders</p>
              </div>
            ) : (
              filtered.map((order, i) => <OrderCard key={order.batchId + i} order={order} />)
            )}
          </div>
        )}
      </div>
      <BottomNav />
    </div>
  );
}
