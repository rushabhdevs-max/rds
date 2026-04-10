// Watchlist page — placeholder
import { useNavigate } from "react-router-dom";
import BottomNav from "../components/BottomNav";

export default function Watchlist() {
  const navigate = useNavigate();
  return (
    <div className="page">
      <div className="page__content">
        <header className="page-header">
          <h1 className="page-header__title">Watchlist</h1>
        </header>
        <div className="empty-state">
          <div className="empty-state__circle">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#ccc" strokeWidth="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
          </div>
          <h3 className="empty-state__title">Your watchlist is empty</h3>
          <p className="empty-state__sub">Search for stocks & ETFs and add them here</p>
          <button className="btn btn--primary" onClick={() => navigate("/search")}>Search</button>
        </div>
      </div>
      <BottomNav />
    </div>
  );
}
