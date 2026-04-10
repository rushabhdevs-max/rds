import { Routes, Route } from "react-router-dom";

// Airpay-owned screens
import Home from "./pages/Home";
import Landing from "./pages/Landing";
import Portfolio from "./pages/Portfolio";
import StockDetail from "./pages/StockDetail";
import ETFDetail from "./pages/ETFDetail";
import Orders from "./pages/Orders";
import Search from "./pages/Search";
import Watchlist from "./pages/Watchlist";
import More from "./pages/More";

// SDK-simulated screens
import BrokerChooser from "./pages/BrokerChooser";
import BrokerAuth from "./pages/BrokerAuth";
import HoldingsLoading from "./pages/HoldingsLoading";
import BuyOrder from "./pages/BuyOrder";
import SellOrder from "./pages/SellOrder";
import OrderReview from "./pages/OrderReview";

export default function App() {
  return (
    <div className="app-shell">
      <Routes>
        {/* Screen 1: Home */}
        <Route path="/" element={<Home />} />

        {/* Screen 2: Landing */}
        <Route path="/landing" element={<Landing />} />

        {/* Screen 3: Broker Chooser (SDK) */}
        <Route path="/broker-chooser" element={<BrokerChooser />} />

        {/* Screen 4: Broker Auth (SDK) */}
        <Route path="/broker-auth" element={<BrokerAuth />} />

        {/* Screen 5: Holdings Fetch Loading (SDK) */}
        <Route path="/holdings-loading" element={<HoldingsLoading />} />

        {/* Screen 6 + 7: Portfolio Summary / Holdings Detail */}
        <Route path="/portfolio" element={<Portfolio />} />

        {/* Screen 8 + 9: Stock Detail (from holdings or search) */}
        <Route path="/stock/:symbol" element={<StockDetail />} />

        {/* Screen 10 + 11: ETF Detail (from holdings or search) */}
        <Route path="/etf/:symbol" element={<ETFDetail />} />

        {/* Screen 12: Buy Order (SDK) */}
        <Route path="/buy/:symbol" element={<BuyOrder />} />

        {/* Screen 13: Sell Order (SDK) */}
        <Route path="/sell/:symbol" element={<SellOrder />} />

        {/* Screen 14: Order Review (SDK) */}
        <Route path="/order-review/:symbol" element={<OrderReview />} />

        {/* Screens 15-22: Orders Tab */}
        <Route path="/orders" element={<Orders />} />

        {/* Screen 23: Search */}
        <Route path="/search" element={<Search />} />

        {/* Watchlist */}
        <Route path="/watchlist" element={<Watchlist />} />

        {/* More */}
        <Route path="/more" element={<More />} />
      </Routes>
    </div>
  );
}
